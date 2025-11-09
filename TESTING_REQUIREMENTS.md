# 🧪 Testing Requirements

**Purpose:** Establish comprehensive testing standards to ensure code reliability and prevent regressions.

---

## 🎯 Testing Philosophy

```
1. Tests are documentation
2. Tests enable refactoring
3. Tests catch regressions
4. Tests define contracts
5. Tests build confidence
```

---

## 📊 Coverage Requirements

### Minimum Standards

```
Overall Coverage:     ≥ 90%
New Code Coverage:    100%
Critical Paths:       100%
Security Code:        100%
```

### Coverage by Type

```python
Unit Tests:           ≥ 85%
Integration Tests:    ≥ 80%
E2E Tests:           ≥ 60%
Security Tests:       100% (for auth/validation)
Performance Tests:    Critical paths only
```

### Measure Coverage

```bash
# Run with coverage
pytest --cov=fastapi_pulse --cov-report=term-missing --cov-report=html

# View report
open htmlcov/index.html

# Fail if below threshold
pytest --cov=fastapi_pulse --cov-fail-under=90
```

---

## 🧩 Test Types

### 1. Unit Tests

**Purpose:** Test individual functions/methods in isolation

**Requirements:**
```
✅ Test one thing at a time
✅ Fast (< 100ms per test)
✅ No external dependencies
✅ Use mocks/stubs for dependencies
✅ Test all code paths
✅ Test edge cases
```

**Example:**
```python
import pytest
from mymodule import calculate_discount

def test_calculate_discount_valid():
    """Test discount calculation with valid input."""
    assert calculate_discount(100, 20) == 80.0
    assert calculate_discount(50, 10) == 45.0

def test_calculate_discount_zero():
    """Test discount calculation with zero."""
    assert calculate_discount(100, 0) == 100.0

def test_calculate_discount_full():
    """Test discount calculation with 100%."""
    assert calculate_discount(100, 100) == 0.0

def test_calculate_discount_invalid_negative():
    """Test error handling for negative discount."""
    with pytest.raises(ValueError, match="must be between 0 and 100"):
        calculate_discount(100, -10)

def test_calculate_discount_invalid_over_100():
    """Test error handling for discount > 100%."""
    with pytest.raises(ValueError, match="must be between 0 and 100"):
        calculate_discount(100, 150)

def test_calculate_discount_invalid_price():
    """Test error handling for negative price."""
    with pytest.raises(ValueError, match="price must be positive"):
        calculate_discount(-100, 20)
```

**Naming Convention:**
```python
test_[function]_[scenario]_[expected_result]

Examples:
- test_login_valid_credentials_returns_token
- test_login_invalid_password_raises_error
- test_login_locked_account_returns_403
```

---

### 2. Integration Tests

**Purpose:** Test multiple components working together

**Requirements:**
```
✅ Test component interactions
✅ Use real databases (test DB)
✅ Test API endpoints
✅ Verify data flow
✅ Test transactions
```

**Example:**
```python
import pytest
from fastapi.testclient import TestClient

def test_create_user_endpoint(client: TestClient, db):
    """Test user creation through API."""
    response = client.post(
        "/users",
        json={
            "email": "test@example.com",
            "password": "SecurePass123!",
            "name": "Test User"
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "password" not in data  # Never return password!
    assert data["id"] is not None

    # Verify in database
    user = db.query(User).filter_by(email="test@example.com").first()
    assert user is not None
    assert user.name == "Test User"
    assert user.password_hash != "SecurePass123!"  # Should be hashed

def test_create_user_duplicate_email(client: TestClient, db):
    """Test that duplicate emails are rejected."""
    # Create first user
    client.post("/users", json={
        "email": "test@example.com",
        "password": "Pass1",
        "name": "User 1"
    })

    # Try to create duplicate
    response = client.post("/users", json={
        "email": "test@example.com",
        "password": "Pass2",
        "name": "User 2"
    })

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()
```

---

### 3. End-to-End Tests

**Purpose:** Test complete user workflows

**Requirements:**
```
✅ Test realistic scenarios
✅ Multiple steps
✅ Test user journeys
✅ Cross-service interactions
✅ Use test accounts
```

**Example:**
```python
def test_complete_order_flow(client: TestClient):
    """Test complete e-commerce order flow."""
    # 1. Register user
    register_response = client.post("/auth/register", json={
        "email": "buyer@example.com",
        "password": "SecurePass123!"
    })
    assert register_response.status_code == 201
    token = register_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Browse products
    products_response = client.get("/products")
    assert products_response.status_code == 200
    product = products_response.json()[0]

    # 3. Add to cart
    cart_response = client.post(
        "/cart/items",
        headers=headers,
        json={"product_id": product["id"], "quantity": 2}
    )
    assert cart_response.status_code == 201

    # 4. Place order
    order_response = client.post(
        "/orders",
        headers=headers,
        json={"payment_method": "credit_card"}
    )
    assert order_response.status_code == 201
    order_id = order_response.json()["id"]

    # 5. Verify order status
    status_response = client.get(f"/orders/{order_id}", headers=headers)
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "pending"

    # 6. Verify inventory updated
    product_response = client.get(f"/products/{product['id']}")
    assert product_response.json()["stock"] == product["stock"] - 2
```

---

### 4. Security Tests

**Purpose:** Verify security controls are effective

**Requirements:**
```
✅ Test authentication
✅ Test authorization
✅ Test input validation
✅ Test injection prevention
✅ Test rate limiting
✅ Test CORS/CSRF
```

**Example:**
```python
def test_sql_injection_prevention(client: TestClient):
    """Verify SQL injection is prevented."""
    malicious_input = "1' OR '1'='1"

    response = client.get(f"/users/{malicious_input}")

    # Should return 404 or 400, not expose database
    assert response.status_code in [400, 404]
    assert "SQL" not in response.text
    assert "syntax error" not in response.text.lower()

def test_xss_prevention(client: TestClient):
    """Verify XSS attacks are prevented."""
    xss_payload = "<script>alert('xss')</script>"

    response = client.post("/comments", json={
        "text": xss_payload
    })

    assert response.status_code == 201

    # Retrieve comment
    comment_response = client.get("/comments")
    comment_text = comment_response.json()[0]["text"]

    # Script should be escaped
    assert "<script>" not in comment_text
    assert "&lt;script&gt;" in comment_text

def test_authentication_required(client: TestClient):
    """Verify authentication is required for protected endpoints."""
    protected_endpoints = [
        ("/users/me", "GET"),
        ("/users/me", "PUT"),
        ("/orders", "GET"),
        ("/orders", "POST"),
    ]

    for path, method in protected_endpoints:
        response = client.request(method, path)
        assert response.status_code == 401, f"{method} {path} should require auth"

def test_authorization_enforced(client: TestClient, user_token, admin_token):
    """Verify users can only access their own data."""
    # User tries to access another user's data
    response = client.get(
        "/users/999",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403

    # Admin can access any user's data
    response = client.get(
        "/users/999",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code in [200, 404]  # Authorized, even if not found

def test_rate_limiting(client: TestClient):
    """Verify rate limiting is enforced."""
    # Make requests rapidly
    responses = []
    for _ in range(100):
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "wrong"
        })
        responses.append(response.status_code)

    # Should get rate limited
    assert 429 in responses, "Rate limiting not enforced"
```

---

### 5. Performance Tests

**Purpose:** Verify performance requirements are met

**Requirements:**
```
✅ Test response times
✅ Test concurrent load
✅ Test memory usage
✅ Test database performance
✅ Test caching effectiveness
```

**Example:**
```python
import pytest

@pytest.mark.benchmark
def test_api_response_time(client, benchmark):
    """Verify API responds within SLA."""
    def make_request():
        return client.get("/api/users")

    result = benchmark(make_request)

    # Response time requirements
    assert result.stats.mean < 0.1  # < 100ms mean
    assert result.stats.max < 0.2   # < 200ms max

@pytest.mark.benchmark
def test_database_query_performance(db, benchmark):
    """Verify database queries are optimized."""
    def query_users():
        return db.query(User).options(
            joinedload(User.posts)
        ).all()

    result = benchmark(query_users)

    # Query time requirements
    assert result.stats.mean < 0.05  # < 50ms mean
    # Verify no N+1 queries occurred
    assert db.query_count < 2

@pytest.mark.load
def test_concurrent_requests(client):
    """Test behavior under concurrent load."""
    import concurrent.futures

    def make_request():
        return client.get("/api/users")

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(make_request) for _ in range(1000)]
        results = [f.result() for f in futures]

    # All requests should succeed
    success_count = sum(1 for r in results if r.status_code == 200)
    assert success_count / len(results) > 0.95  # 95% success rate
```

---

## 🛠️ Test Fixtures

### Fixture Scopes

```python
# Function scope (default) - new instance for each test
@pytest.fixture(scope="function")
def user():
    return create_user()

# Class scope - shared within test class
@pytest.fixture(scope="class")
def db_connection():
    conn = create_connection()
    yield conn
    conn.close()

# Module scope - shared within module
@pytest.fixture(scope="module")
def app():
    return create_app()

# Session scope - shared across entire test session
@pytest.fixture(scope="session")
def docker_compose():
    subprocess.run(["docker-compose", "up", "-d"])
    yield
    subprocess.run(["docker-compose", "down"])
```

### Common Fixtures

```python
# conftest.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="function")
def db():
    """Provide a test database that resets after each test."""
    engine = create_engine("postgresql://localhost/test_db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="function")
def client(db):
    """Provide a test client with database."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def auth_headers(client):
    """Provide authentication headers."""
    response = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "TestPass123!"
    })
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="function")
def sample_user(db):
    """Create a sample user for testing."""
    user = User(
        email="test@example.com",
        name="Test User",
        password_hash=hash_password("TestPass123!")
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
```

---

## 📋 Test Organization

### Directory Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
│   ├── test_models.py
│   ├── test_services.py
│   └── test_utils.py
├── integration/             # Integration tests
│   ├── test_api.py
│   ├── test_database.py
│   └── test_auth.py
├── e2e/                     # End-to-end tests
│   ├── test_user_flows.py
│   └── test_order_flows.py
├── security/                # Security tests
│   ├── test_auth.py
│   ├── test_validation.py
│   └── test_injection.py
├── performance/             # Performance tests
│   ├── test_api_performance.py
│   └── test_database_performance.py
└── fixtures/                # Test data
    ├── users.json
    └── products.json
```

### File Naming

```
test_*.py                    # Test files start with test_
*_test.py                    # Alternative: end with _test

Test class names:
class TestUserModel         # Start with Test
class TestAuthService

Test function names:
def test_*                  # Start with test_
```

---

## 🎯 Test Best Practices

### 1. AAA Pattern (Arrange, Act, Assert)

```python
def test_user_creation():
    # Arrange - Set up test data
    email = "test@example.com"
    password = "SecurePass123!"

    # Act - Perform the action
    user = create_user(email, password)

    # Assert - Verify the result
    assert user.email == email
    assert user.password_hash != password  # Should be hashed
    assert user.id is not None
```

### 2. Test One Thing

```python
# ✅ GOOD - Each test focuses on one behavior
def test_user_email_validation():
    with pytest.raises(ValueError, match="Invalid email"):
        create_user("invalid-email", "pass")

def test_user_password_validation():
    with pytest.raises(ValueError, match="Password too weak"):
        create_user("test@example.com", "123")

# ❌ BAD - Testing multiple things
def test_user_validation():
    with pytest.raises(ValueError):
        create_user("invalid-email", "pass")
    with pytest.raises(ValueError):
        create_user("test@example.com", "123")
```

### 3. Use Descriptive Names

```python
# ✅ GOOD - Clear what's being tested
def test_login_with_invalid_password_returns_401():
    pass

def test_order_total_includes_tax_and_shipping():
    pass

# ❌ BAD - Unclear what's being tested
def test_login():
    pass

def test_order():
    pass
```

### 4. Independent Tests

```python
# ✅ GOOD - Tests are independent
def test_create_user(db):
    user = create_user("test@example.com")
    assert user.id is not None

def test_find_user(db, sample_user):
    found = find_user(sample_user.id)
    assert found.id == sample_user.id

# ❌ BAD - Tests depend on each other
def test_create_user(db):
    global user_id
    user = create_user("test@example.com")
    user_id = user.id

def test_find_user(db):
    found = find_user(user_id)  # Depends on previous test!
```

### 5. Fast Tests

```python
# ✅ GOOD - Use mocks for external dependencies
@patch('requests.get')
def test_fetch_user_data(mock_get):
    mock_get.return_value = Mock(json=lambda: {"id": 1})
    data = fetch_user_data(1)
    assert data["id"] == 1

# ❌ BAD - Making real HTTP calls
def test_fetch_user_data():
    data = fetch_user_data(1)  # Makes real HTTP call!
    assert data["id"] == 1
```

---

## 🔧 Testing Tools

### Required Tools

```bash
# Testing framework
pip install pytest pytest-asyncio pytest-cov

# Mocking
pip install pytest-mock

# Test data
pip install faker factory-boy

# Performance testing
pip install pytest-benchmark locust

# Security testing
pip install safety bandit
```

### pytest.ini Configuration

```ini
[pytest]
# Test discovery
testpaths = tests
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*

# Coverage
addopts =
    --cov=fastapi_pulse
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=90
    --strict-markers
    -v

# Markers
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: integration tests
    security: security tests
    benchmark: performance benchmarks
    skip_ci: skip in CI environment

# Async support
asyncio_mode = auto
```

---

## 🚨 Common Testing Mistakes

### 1. Not Testing Error Cases

```python
# ❌ BAD - Only testing happy path
def test_divide():
    assert divide(10, 2) == 5

# ✅ GOOD - Testing error cases
def test_divide_by_zero():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)
```

### 2. Testing Implementation Instead of Behavior

```python
# ❌ BAD - Testing implementation details
def test_user_repository_uses_cache():
    repo = UserRepository()
    repo.find(1)
    assert repo._cache.get.called  # Implementation detail!

# ✅ GOOD - Testing behavior
def test_user_repository_returns_user():
    repo = UserRepository()
    user = repo.find(1)
    assert user.id == 1
```

### 3. Fragile Tests

```python
# ❌ BAD - Fragile, depends on order
def test_get_users():
    users = get_users()
    assert users[0].name == "Alice"  # Breaks if order changes!

# ✅ GOOD - Robust
def test_get_users():
    users = get_users()
    names = [u.name for u in users]
    assert "Alice" in names
```

### 4. Slow Tests

```python
# ❌ BAD - Sleeps in tests
def test_async_operation():
    start_operation()
    time.sleep(5)  # Don't do this!
    assert operation_complete()

# ✅ GOOD - Use proper async testing
async def test_async_operation():
    task = asyncio.create_task(async_operation())
    result = await asyncio.wait_for(task, timeout=1.0)
    assert result == expected
```

---

## ✅ Testing Checklist

**Before marking code as done:**

```
Unit Tests:
[ ] All functions have tests
[ ] Happy path tested
[ ] Error cases tested
[ ] Edge cases tested
[ ] Mocks used for dependencies

Integration Tests:
[ ] API endpoints tested
[ ] Database interactions tested
[ ] Authentication tested
[ ] Authorization tested
[ ] Error responses tested

Security Tests:
[ ] Input validation tested
[ ] Authentication tested
[ ] Authorization tested
[ ] Injection prevention tested
[ ] Rate limiting tested

Performance Tests:
[ ] Response times measured
[ ] Resource usage acceptable
[ ] No N+1 queries
[ ] Caching working

Coverage:
[ ] Overall coverage >= 90%
[ ] New code coverage = 100%
[ ] Critical paths = 100%
[ ] No untested error handlers

Quality:
[ ] Tests are fast (< 1s each)
[ ] Tests are independent
[ ] Tests are repeatable
[ ] Test names are descriptive
[ ] No flaky tests
```

---

**Last Updated:** 2025-11-09
**Version:** 1.0
**Maintained By:** Project QA Team
