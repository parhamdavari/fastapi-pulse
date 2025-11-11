Here’s a modern, end-to-end testing blueprint for a FastAPI project. It uses current Python tooling, async patterns, SQLAlchemy 2.x, Pydantic v2, and containerized infra. It also includes high-leverage prompts to keep test quality consistent when you use Claude (reference: docs.claude.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices).

# 1) Test strategy (scope and gates)

* Levels: unit → service/integration → API/e2e → contract → property/fuzz.
* Hard gates: 90% line + 80% branch coverage on app code, zero xfails, type-checked on CI, security scan passes.
* Speed targets: unit tests ≤ 1s each, full suite parallelized.
* Flake: forbid real network, clock, and global state in unit tests.

# 2) Canonical layout

```
project/
  app/
    __init__.py
    main.py
    api/
      routes.py
      deps.py
    core/
      config.py
    db/
      base.py
      session.py
      models/
      repositories/
    services/
    schemas/
  tests/
    unit/
    integration/
    api/
    contract/
    property/
    perf/
    conftest.py
    factories/
      __init__.py
      user.py
  migrations/        # Alembic
  pyproject.toml
  .env.example
  docker-compose.yml
  Makefile
```

# 3) Tooling

* pytest, pytest-asyncio, httpx, anyio, asgi-lifespan
* pytest-xdist (parallel), pytest-cov
* pytest-mock, freezegun
* factory_boy, faker
* hypothesis
* testcontainers-python (Postgres, Redis, etc.)
* SQLAlchemy 2.x, Alembic
* ruff, pyright or mypy, bandit, safety
* uv or pip-tools for reproducible deps

# 4) `pyproject.toml` essentials

```toml
[project]
name = "project"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.7",
  "sqlalchemy>=2.0",
  "alembic>=1.13",
  "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "pytest-xdist>=3",
  "pytest-cov>=5",
  "asgi-lifespan>=2.1",
  "freezegun>=1.5",
  "pytest-mock>=3.14",
  "hypothesis>=6",
  "factory_boy>=3.3",
  "faker>=30",
  "testcontainers[postgres]>=4",
  "ruff>=0.6",
  "pyright>=1.1",
  "bandit>=1.7",
  "safety>=3.2",
]

[tool.pytest.ini_options]
addopts = "-q -ra --strict-markers --strict-config --cov=app --cov-report=term-missing:skip-covered --cov-fail-under=90"
testpaths = ["tests"]
xfail_strict = true
markers = [
  "unit: fast unit tests",
  "integration: DB or external boundary",
  "e2e: full API flow",
  "contract: provider/consumer contracts",
]

[tool.coverage.run]
branch = true
omit = ["tests/*", "migrations/*"]

[tool.ruff]
line-length = 100
lint.select = ["E","F","I","UP","B","SIM","PL"]
```

# 5) Core test fixtures (`tests/conftest.py`)

```python
import asyncio
import os
import typing as t

import anyio
import pytest
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from fastapi import FastAPI

# Ensure test settings are loaded before app import
os.environ.setdefault("ENV", "test")

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="session")
def settings_overrides(monkeypatch):
    # Point to a test database; overridden again if using Testcontainers
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5433/testdb")
    monkeypatch.setenv("ENV", "test")

@pytest.fixture(scope="session")
def app(settings_overrides) -> FastAPI:
    from app.main import create_app  # prefer a factory in app.main
    return create_app()

@pytest.fixture(scope="session")
async def started_app(app: FastAPI):
    async with LifespanManager(app):
        yield app

@pytest.fixture
async def client(started_app: FastAPI):
    transport = ASGITransport(app=started_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

# 6) Database fixtures (async SQLAlchemy 2.x + Alembic + Testcontainers)

```python
# tests/conftest.py (continued)
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.postgres import PostgresContainer
import os
import alembic.config

@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16") as pg:
        pg.start()
        yield pg

@pytest.fixture(scope="session")
def test_db_url(pg_container) -> str:
    url = pg_container.get_connection_url()
    # SQLAlchemy async URL
    return url.replace("postgresql://", "postgresql+asyncpg://")

@pytest.fixture(scope="session")
async def engine(test_db_url) -> AsyncEngine:
    eng = create_async_engine(test_db_url, future=True)
    # Run migrations to get real schema
    os.environ["DATABASE_URL"] = test_db_url.replace("+asyncpg", "")
    alembic_args = ["-x", f"url={os.environ['DATABASE_URL']}", "upgrade", "head"]
    alembic.config.main(argv=alembic_args)
    yield eng
    await eng.dispose()

@pytest.fixture
async def db_session(engine: AsyncEngine):
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()
```

Use dependency overrides in tests to inject `db_session` into app routes/services:

```python
# tests/overrides.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

def override_get_db(session: AsyncSession):
    async def _get_db():
        yield session
    return _get_db
```

# 7) Example tests

**Unit**

```python
# tests/unit/test_service_example.py
import pytest
from app.services.user import hash_password

def test_hash_password_is_deterministic_for_same_salt():
    pw = "secret"
    salt = b"\x00" * 16
    assert hash_password(pw, salt) == hash_password(pw, salt)
```

**Integration (service + DB)**

```python
# tests/integration/test_user_repo.py
import pytest
from app.db.repositories.user import UserRepo
from app.db.models import User

@pytest.mark.integration
async def test_create_and_fetch_user(db_session):
    repo = UserRepo(db_session)
    u = await repo.create(email="a@b.com", name="A B")
    got = await repo.get(u.id)
    assert got.email == "a@b.com"
```

**API/E2E**

```python
# tests/api/test_users_api.py
import pytest
from tests.overrides import override_get_db

@pytest.mark.e2e
async def test_create_user_flow(client, db_session, started_app):
    # override dependency for this test
    started_app.dependency_overrides[YourGetDBDep] = override_get_db(db_session)
    resp = await client.post("/users", json={"email":"a@b.com","name":"A B"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"]
```

**Property-based**

```python
# tests/property/test_email_schema.py
from hypothesis import given, strategies as st
from app.schemas.user import UserCreate

@given(st.emails(), st.text(min_size=1, max_size=32))
def test_user_create_accepts_valid_email(email, name):
    obj = UserCreate(email=email, name=name)
    assert obj.email == email
```

# 8) FastAPI app factory pattern

```python
# app/main.py
from fastapi import FastAPI
from app.api.routes import router

def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app
```

# 9) Migrations in tests

* Use Alembic “offline” URL override via `-x url=...`.
* Run `upgrade head` in a session-scoped fixture before tests.
* For faster unit tests, use SQLite in-memory and bypass migrations where possible; reserve migrations for integration/e2e.

# 10) Parallelism and isolation

* `pytest -n auto` with xdist.
* Per-test DB isolation via transactions or per-function database schema reset. For Postgres, wrap each test in a SAVEPOINT or recreate schema with `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` for heavy tests.
* For Redis or brokers, use Testcontainers images or unique namespaces per test.

# 11) CI pipeline (GitHub Actions)

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
        ports: ["5432:5432"]
        options: >-
          --health-cmd="pg_isready -U postgres"
          --health-interval=5s --health-timeout=5s --health-retries=5
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv venv
      - run: uv pip install -e ".[dev]"
      - run: uv pip list
      - run: ruff check .
      - run: pyright
      - run: pytest -n auto
```

# 12) Makefile shortcuts

```makefile
.PHONY: test unit integration e2e cov lint type
test: ; pytest -n auto
unit: ; pytest -m unit -q
integration: ; pytest -m integration -q
e2e: ; pytest -m e2e -q
cov: ; pytest --cov=app --cov-report=xml
lint: ; ruff check .
type: ; pyright
```

# 13) Contract tests (optional but recommended)

* If you have consumers, publish OpenAPI and validate with `schemathesis` or Pact.
* Provider: run API against recorded consumer contracts on CI.
* Consumer: verify generated client against provider schema.

# 14) Performance and regression

* Add lightweight `perf/` with `pytest-benchmark` for hot paths.
* Fail builds on regression > N%.

# 15) Prompts to enforce standards with Claude

Use these with the linked best-practices. Keep them as saved prompts.

**“Test Author” prompt**

```
Role: Senior Python test engineer.
Goal: Write pytest tests for the given FastAPI code using async patterns and SQLAlchemy 2.0.

Requirements:
- Use pytest, pytest-asyncio, httpx.AsyncClient(ASGITransport), asgi-lifespan.
- Isolate unit tests from DB and clock; use pytest-mock and freezegun.
- For integration, use Testcontainers(Postgres) + Alembic upgrade head.
- Provide fixtures and dependency overrides; no real network.
- Provide property tests with Hypothesis where schemas allow.
- Enforce AAA structure, clear names, single assert per behavior block.
- Target coverage: 90% lines, 80% branches. No xfail.
- Return a diff: test files to add, updates to conftest, and commands to run.
Input: <paste code here>
Output: only code blocks and shell commands.
```

**“Test Review” prompt**

```
Role: Reviewer.
Task: Review the proposed tests for readability, isolation, flake, and coverage risk.

Checklist:
- Async correctness, no hidden event loops.
- No production DB or external services in unit tests.
- Deterministic seeds for Faker and Hypothesis.
- Clear factory objects, no fixture pyramids.
- Parallel-safe, idempotent.
- Coverage of error paths and edge cases.
- Contracts vs. implementation details: avoid brittle coupling.
Output: bullet findings + concrete patches.
```

# 16) Run commands

```bash
uv pip install -e ".[dev]"
pytest -n auto
pytest -m integration -q
pytest --cov=app --cov-report=term-missing
```

Adopt the app-factory pattern, async DB with Testcontainers, and strict CI gates. This gives you current, standard, and scalable testing across the whole FastAPI project.
