# ✅ Code Review Checklist

**Purpose:** Systematic verification of code quality before commit. Go through EVERY item before pushing code.

---

## 🎯 How to Use This Checklist

1. **Before starting work:** Read this entire document
2. **During development:** Reference relevant sections
3. **Before commit:** Go through ALL items systematically
4. **Mark each item:** ✅ Pass / ❌ Fail / ➖ N/A

**If ANY item fails: FIX before committing**

---

## 🔍 Section 1: Resource Management

### 1.1 File Handles
```
[ ] All file opens have corresponding closes
[ ] Using context managers (with statement)
[ ] No file descriptors leaked
[ ] Temp files cleaned up properly
[ ] File paths validated against traversal
```

**Verify:**
```python
# ✅ Good
with open(path, 'r') as f:
    data = f.read()

# ❌ Bad
f = open(path, 'r')
data = f.read()  # Never closed!
```

### 1.2 Database Connections
```
[ ] Connections closed after use
[ ] Using connection pools
[ ] Transactions properly committed/rolled back
[ ] No connection leaks
[ ] Timeouts configured
```

**Verify:**
```python
# ✅ Good
with db.get_connection() as conn:
    conn.execute(query)
    conn.commit()

# ❌ Bad
conn = db.get_connection()
conn.execute(query)  # Never closed!
```

### 1.3 Network Resources
```
[ ] HTTP clients properly closed
[ ] Websocket connections terminated
[ ] Timeouts configured
[ ] Connection limits enforced
[ ] No socket leaks
```

**Verify:**
```python
# ✅ Good
async with httpx.AsyncClient() as client:
    response = await client.get(url)

# ❌ Bad
client = httpx.AsyncClient()
response = await client.get(url)  # Never closed!
```

### 1.4 Threading/Async Resources
```
[ ] Locks released properly
[ ] Semaphores cleaned up
[ ] Thread pools shutdown
[ ] Async tasks cancelled properly
[ ] No deadlocks possible
```

**Verify:**
```python
# ✅ Good
with self._lock:
    self.data = new_value

# ❌ Bad
self._lock.acquire()
self.data = new_value
# Forgot to release!
```

### 1.5 Memory Management
```
[ ] No circular references
[ ] Large objects cleaned up
[ ] Caches have size limits
[ ] No unbounded collections
[ ] Weak references used appropriately
```

**Verify:**
```python
# ✅ Good
cache = LRUCache(max_size=1000)

# ❌ Bad
cache = {}  # Grows forever!
```

---

## 🛡️ Section 2: Error Handling

### 2.1 Exception Handling
```
[ ] All exceptions caught appropriately
[ ] Specific exceptions (not bare except:)
[ ] Exceptions logged with context
[ ] Re-raising when appropriate
[ ] Custom exceptions for business logic
```

**Verify:**
```python
# ✅ Good
try:
    risky_operation()
except ValueError as e:
    logger.error("Invalid input", extra={"error": str(e)})
    raise ValidationError(f"Bad data: {e}")
except Exception as e:
    logger.exception("Unexpected error")
    raise

# ❌ Bad
try:
    risky_operation()
except:
    pass  # Swallows all errors!
```

### 2.2 Error Messages
```
[ ] Error messages are clear and actionable
[ ] No sensitive data in error messages
[ ] Error codes/types consistent
[ ] Stack traces not exposed to users
[ ] Logging includes correlation IDs
```

**Verify:**
```python
# ✅ Good
raise ValueError(
    "Invalid user_id format. Expected numeric string, "
    f"got: {type(user_id).__name__}"
)

# ❌ Bad
raise ValueError("Bad input")  # Not helpful!
```

### 2.3 Error Recovery
```
[ ] Graceful degradation implemented
[ ] Retry logic with backoff (when appropriate)
[ ] Circuit breakers for external services
[ ] Fallback values provided
[ ] User-friendly error responses
```

**Verify:**
```python
# ✅ Good
def fetch_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            return fetch(url)
        except TemporaryError:
            if attempt == max_retries - 1:
                raise
            sleep(2 ** attempt)

# ❌ Bad
def fetch(url):
    return requests.get(url)  # No retry!
```

### 2.4 Async Error Handling
```
[ ] Async exceptions properly caught
[ ] Tasks cancelled on errors
[ ] Timeouts enforced
[ ] Background tasks don't crash silently
[ ] Error propagation works correctly
```

**Verify:**
```python
# ✅ Good
async def safe_background_task():
    try:
        await long_running_task()
    except Exception as e:
        logger.exception("Background task failed")
        await notify_admin(e)

# ❌ Bad
async def unsafe_background_task():
    await long_running_task()  # Crashes disappear!
```

---

## 🔐 Section 3: Security

### 3.1 Input Validation
```
[ ] All user inputs validated
[ ] Length limits enforced
[ ] Format validation (regex)
[ ] Type checking
[ ] Range validation
[ ] Whitelist validation
[ ] Path traversal prevented
[ ] SQL injection prevented
[ ] XSS prevented
[ ] Command injection prevented
```

**Verify:**
```python
# ✅ Good
def process_user_id(user_id: str):
    if not user_id:
        raise ValueError("user_id required")
    if not re.match(r'^\d+$', user_id):
        raise ValueError("user_id must be numeric")
    if len(user_id) > 20:
        raise ValueError("user_id too long")
    return get_user(int(user_id))

# ❌ Bad
def process_user_id(user_id):
    return get_user(int(user_id))  # No validation!
```

### 3.2 Authentication & Authorization
```
[ ] Authentication required where needed
[ ] Authorization checks before operations
[ ] Session management secure
[ ] Password handling secure (hashed)
[ ] JWT tokens validated properly
[ ] API keys not in code
```

**Verify:**
```python
# ✅ Good
@require_auth
@require_permission("admin")
def delete_user(user_id):
    # Check ownership
    if not current_user.can_delete(user_id):
        raise PermissionDenied()
    User.delete(user_id)

# ❌ Bad
def delete_user(user_id):
    User.delete(user_id)  # No checks!
```

### 3.3 Data Protection
```
[ ] Sensitive data encrypted at rest
[ ] Sensitive data encrypted in transit (HTTPS)
[ ] PII properly masked in logs
[ ] Secrets in environment variables
[ ] No hardcoded passwords/keys
[ ] Secure random numbers used
```

**Verify:**
```python
# ✅ Good
import secrets

token = secrets.token_urlsafe(32)
logger.info("User logged in", user_id=mask_pii(user_email))

# ❌ Bad
import random

token = str(random.randint(1, 1000000))  # Predictable!
logger.info(f"User {user_email} logged in")  # PII leaked!
```

### 3.4 CORS & CSRF
```
[ ] CORS origins explicitly configured
[ ] No wildcard origins with credentials
[ ] CSRF protection enabled
[ ] SameSite cookies configured
[ ] Referer checking (when appropriate)
```

**Verify:**
```python
# ✅ Good
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=False,
)

# ❌ Bad
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
)
```

### 3.5 Rate Limiting
```
[ ] Rate limits on public endpoints
[ ] Rate limits on authentication
[ ] Rate limits on expensive operations
[ ] Appropriate limits configured
[ ] 429 responses returned
```

**Verify:**
```python
# ✅ Good
@limiter.limit("5/minute")
def login(credentials):
    return authenticate(credentials)

# ❌ Bad
def login(credentials):
    return authenticate(credentials)  # Brute force possible!
```

---

## ⚡ Section 4: Performance

### 4.1 Database Performance
```
[ ] No N+1 queries
[ ] Appropriate indexes exist
[ ] Queries use LIMIT/OFFSET
[ ] Batch operations instead of loops
[ ] Connection pooling configured
[ ] Query timeouts set
```

**Verify:**
```python
# ✅ Good
users = User.query.options(joinedload(User.posts)).all()

# ❌ Bad
users = User.query.all()
for user in users:
    posts = Post.query.filter_by(user_id=user.id).all()  # N+1!
```

### 4.2 Caching
```
[ ] Appropriate cache keys
[ ] Cache invalidation strategy
[ ] Cache TTL configured
[ ] Cache size limits
[ ] No cache stampede
```

**Verify:**
```python
# ✅ Good
@cache.memoize(timeout=300, unless=lambda: random.random() < 0.1)
def expensive_operation():
    return compute()

# ❌ Bad
result = expensive_operation()  # No caching!
```

### 4.3 Async/Await
```
[ ] Async functions truly async
[ ] No blocking I/O in async code
[ ] Appropriate use of gather()
[ ] No sync code in event loop
[ ] Timeouts on async operations
```

**Verify:**
```python
# ✅ Good
async def fetch_all(urls):
    async with httpx.AsyncClient() as client:
        tasks = [client.get(url) for url in urls]
        return await asyncio.gather(*tasks)

# ❌ Bad
async def fetch_all(urls):
    results = []
    for url in urls:
        results.append(requests.get(url))  # Blocking!
    return results
```

### 4.4 Memory Efficiency
```
[ ] No memory leaks
[ ] Appropriate data structures
[ ] Streaming large data
[ ] Generators for large sequences
[ ] No unbounded caches
```

**Verify:**
```python
# ✅ Good
def process_large_file(path):
    with open(path) as f:
        for line in f:  # Streaming
            yield process(line)

# ❌ Bad
def process_large_file(path):
    with open(path) as f:
        lines = f.readlines()  # Loads entire file!
    return [process(line) for line in lines]
```

### 4.5 Response Times
```
[ ] API responses < 200ms (P95)
[ ] Database queries < 100ms
[ ] No blocking operations
[ ] Background tasks for slow operations
[ ] Appropriate timeouts set
```

---

## 🧵 Section 5: Concurrency

### 5.1 Thread Safety
```
[ ] Shared state protected by locks
[ ] No race conditions
[ ] Deadlocks prevented
[ ] Lock ordering consistent
[ ] Lock-free when possible
```

**Verify:**
```python
# ✅ Good
class ThreadSafeCounter:
    def __init__(self):
        self._count = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:
            self._count += 1

# ❌ Bad
class UnsafeCounter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1  # Race condition!
```

### 5.2 Async Safety
```
[ ] No shared mutable state in async code
[ ] Async locks used correctly
[ ] No blocking calls in async functions
[ ] Proper task cancellation
[ ] Semaphores for concurrency limits
```

**Verify:**
```python
# ✅ Good
semaphore = asyncio.Semaphore(10)

async def limited_operation():
    async with semaphore:
        await expensive_call()

# ❌ Bad
async def unlimited_operation():
    await expensive_call()  # No limit!
```

### 5.3 Transaction Safety
```
[ ] Database transactions atomic
[ ] Proper isolation levels
[ ] Rollback on errors
[ ] No partial updates
[ ] Idempotent operations
```

**Verify:**
```python
# ✅ Good
with db.transaction():
    user.update(data)
    log.create(entry)
# Commits or rolls back together

# ❌ Bad
user.update(data)
log.create(entry)  # Can fail after user updated!
```

---

## 🧪 Section 6: Testing

### 6.1 Test Coverage
```
[ ] New code has tests
[ ] Happy path tested
[ ] Error cases tested
[ ] Edge cases tested
[ ] Coverage >= 90%
```

**Verify:**
```bash
pytest --cov=module --cov-report=term-missing
# Check: Coverage >= 90%
```

### 6.2 Test Quality
```
[ ] Tests are independent
[ ] Tests are repeatable
[ ] Tests are fast (< 1s each)
[ ] No flaky tests
[ ] Clear test names
[ ] Tests document behavior
```

**Verify:**
```python
# ✅ Good
def test_user_creation_with_valid_email():
    """User can be created with valid email."""
    user = create_user(email="test@example.com")
    assert user.email == "test@example.com"

# ❌ Bad
def test_1():
    u = create_user("test@example.com")
    assert u  # What does this test?
```

### 6.3 Test Isolation
```
[ ] Tests don't depend on each other
[ ] Tests clean up after themselves
[ ] Fixtures properly scoped
[ ] No shared mutable state
[ ] Database reset between tests
```

**Verify:**
```python
# ✅ Good
@pytest.fixture(scope="function")
def db():
    connection = create_test_db()
    yield connection
    connection.drop_all()

# ❌ Bad
db = create_test_db()  # Shared across all tests!
```

### 6.4 Integration Testing
```
[ ] API endpoints tested
[ ] Database integration tested
[ ] External service mocking
[ ] Error scenarios tested
[ ] Authentication tested
```

**Verify:**
```python
# ✅ Good
def test_api_with_authentication(client, auth_headers):
    response = client.get("/api/resource", headers=auth_headers)
    assert response.status_code == 200

def test_api_without_authentication(client):
    response = client.get("/api/resource")
    assert response.status_code == 401

# ❌ Bad
def test_api(client):
    response = client.get("/api/resource")
    assert response.status_code == 200  # Didn't test auth!
```

---

## 📝 Section 7: Code Quality

### 7.1 Readability
```
[ ] Variable names descriptive
[ ] Function names clear
[ ] No magic numbers
[ ] Comments explain why, not what
[ ] Code is self-documenting
```

**Verify:**
```python
# ✅ Good
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

def retry_with_exponential_backoff(operation, max_retries=MAX_RETRIES):
    """Retry operation with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return operation()
        except TemporaryError:
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY_SECONDS ** attempt)

# ❌ Bad
def retry(op, n=3):
    for i in range(n):
        try:
            return op()
        except:
            time.sleep(2 ** i)
```

### 7.2 Complexity
```
[ ] Functions < 50 lines
[ ] Classes < 500 lines
[ ] Cyclomatic complexity < 10
[ ] No deep nesting (< 4 levels)
[ ] Single Responsibility Principle
```

**Verify:**
```python
# ✅ Good - Simple, focused functions
def validate_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)

def validate_user_data(data):
    if not validate_email(data['email']):
        raise ValueError("Invalid email")

# ❌ Bad - Complex, multi-responsibility
def process_user(data):
    # 100 lines of validation
    # 50 lines of processing
    # 30 lines of database operations
    # 40 lines of email sending
    pass
```

### 7.3 Type Hints
```
[ ] All function parameters typed
[ ] Return types specified
[ ] Optional/Union used correctly
[ ] Type hints for class attributes
[ ] Mypy passing
```

**Verify:**
```python
# ✅ Good
from typing import Optional, List

def find_user(user_id: int) -> Optional[User]:
    """Find user by ID."""
    return User.query.get(user_id)

def get_users(limit: int = 10) -> List[User]:
    """Get list of users."""
    return User.query.limit(limit).all()

# ❌ Bad
def find_user(user_id):  # No types!
    return User.query.get(user_id)
```

### 7.4 Documentation
```
[ ] Public functions have docstrings
[ ] Complex logic explained
[ ] Examples in docstrings
[ ] README updated (if needed)
[ ] API docs updated (if needed)
```

**Verify:**
```python
# ✅ Good
def calculate_discount(price: float, discount_percent: float) -> float:
    """
    Calculate discounted price.

    Args:
        price: Original price in USD
        discount_percent: Discount percentage (0-100)

    Returns:
        Discounted price in USD

    Raises:
        ValueError: If discount is invalid

    Example:
        >>> calculate_discount(100.0, 20.0)
        80.0
    """
    if not 0 <= discount_percent <= 100:
        raise ValueError("Discount must be between 0 and 100")
    return price * (1 - discount_percent / 100)

# ❌ Bad
def calculate_discount(price, discount):
    return price * (1 - discount / 100)
```

### 7.5 Maintainability
```
[ ] No code duplication (DRY)
[ ] Appropriate abstraction level
[ ] Clear separation of concerns
[ ] Configuration externalized
[ ] Dependencies minimized
```

---

## 🗂️ Section 8: Git & Commits

### 8.1 Commit Quality
```
[ ] Clear, descriptive commit message
[ ] Follows conventional commits format
[ ] References issue/ticket
[ ] Atomic commits (one logical change)
[ ] Commit size appropriate (< 400 LOC)
```

**Verify:**
```bash
# ✅ Good
feat(auth): add JWT token refresh endpoint

Implements token refresh functionality to extend user sessions
without requiring re-authentication. Includes rate limiting to
prevent abuse.

Closes #123

# ❌ Bad
Update code
```

### 8.2 Branch Management
```
[ ] Working on feature branch
[ ] Branch name descriptive
[ ] No merge conflicts
[ ] Branch up to date with main
[ ] No uncommitted changes
```

### 8.3 Code Review Ready
```
[ ] All tests passing
[ ] Coverage requirements met
[ ] Linter passing
[ ] No TODO comments (or ticketed)
[ ] Documentation updated
```

---

## 🚀 Section 9: Deployment

### 9.1 Configuration
```
[ ] Environment variables used
[ ] No hardcoded configs
[ ] Secrets properly managed
[ ] Different configs for dev/prod
[ ] Configuration validated on startup
```

**Verify:**
```python
# ✅ Good
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not configured")

# ❌ Bad
DATABASE_URL = "postgresql://localhost/db"  # Hardcoded!
```

### 9.2 Monitoring
```
[ ] Appropriate logging added
[ ] Metrics tracked
[ ] Errors reported to monitoring
[ ] Health checks updated
[ ] Alerts configured (if needed)
```

### 9.3 Backward Compatibility
```
[ ] No breaking API changes (or documented)
[ ] Database migrations included
[ ] Deprecation warnings added
[ ] Migration guide provided
[ ] Rollback plan exists
```

---

## ✅ Final Checklist

**Before committing, verify ALL sections:**

```
Section 1: Resource Management        [ ]
Section 2: Error Handling              [ ]
Section 3: Security                    [ ]
Section 4: Performance                 [ ]
Section 5: Concurrency                 [ ]
Section 6: Testing                     [ ]
Section 7: Code Quality                [ ]
Section 8: Git & Commits               [ ]
Section 9: Deployment                  [ ]
```

**Run these commands:**

```bash
# Formatting
black src/
isort src/

# Linting
flake8 src/
pylint src/

# Type checking
mypy src/

# Security
bandit -r src/

# Tests
pytest --cov=src --cov-report=term-missing --cov-fail-under=90

# All checks must pass!
```

**Sign off:**

```
✅ I have reviewed all sections of this checklist
✅ All checks pass or are documented as N/A
✅ All tests pass with >= 90% coverage
✅ Code is ready for review
✅ I understand the changes and their impact

Reviewed by: [Your Name]
Date: [YYYY-MM-DD]
Commit: [commit hash]
```

---

**Last Updated:** 2025-11-09
**Version:** 1.0
**Maintained By:** Project QA Team
