# 🤖 AI Agent Development Rules

**Purpose:** Establish systematic development standards to ensure high code quality, maintainability, and security when working with AI-assisted development.

---

## 🎯 Golden Rules (NEVER VIOLATE)

### Rule #1: Read the Checklist FIRST
```
At the start of EVERY session:
1. Read SESSION_START.md
2. Read this file (AI_AGENT_RULES.md)
3. Read CODE_REVIEW_CHECKLIST.md
4. Read SECURITY_CHECKLIST.md
5. Acknowledge you've read all files
```

### Rule #2: Design Before Code
```
NEVER write code without:
1. Understanding the problem fully
2. Creating a design document
3. Getting user approval on approach
4. Identifying risks and mitigation
```

### Rule #3: Test-Driven Development
```
ALWAYS follow this order:
1. Write failing test
2. Write minimal code to pass test
3. Refactor
4. Repeat
```

### Rule #4: Small, Incremental Changes
```
Maximum per commit:
- 400 lines of code (LOC)
- 1 feature or bug fix
- Related changes only
- Complete, working state
```

### Rule #5: Clean Up Resources
```
ALWAYS close/cleanup:
- File handles
- Database connections
- Network sockets
- Locks and semaphores
- Temporary files
```

---

## 📐 Design Phase (MANDATORY)

### Step 1: Problem Analysis (5 minutes)
```markdown
Create: DESIGN_[feature-name].md

## Problem Statement
[What problem are we solving?]

## Current Behavior
[How does it work now?]

## Desired Behavior
[How should it work?]

## Constraints
[What limitations exist?]

## Open Questions
[What needs clarification?]
```

**Example:**
```markdown
## Problem Statement
CORS is configured with wildcard origins, creating CSRF vulnerability.

## Current Behavior
allow_origins=["*"] allows any origin to make authenticated requests.

## Desired Behavior
Configurable origins with safe defaults and environment variable support.

## Constraints
- Must remain backward compatible
- Cannot break existing deployments
- Must log warnings for unsafe configs

## Open Questions
- What should the default origin be? (Answer: localhost:3000 with warning)
- Should we support regex patterns? (Answer: No, keep simple)
```

### Step 2: Design Document (10 minutes)
```markdown
## Proposed Solution
[High-level approach]

## API Changes
[New parameters, breaking changes]

## Implementation Plan
1. [Step by step plan]
2. [Each step should be small]
3. [And independently testable]

## Testing Strategy
[How will we verify it works?]

## Rollout Plan
[How to deploy safely?]

## Risks & Mitigation
[What could go wrong?]
```

### Step 3: User Approval (REQUIRED)
```
DO NOT CODE until user approves:
✅ Problem statement accurate?
✅ Solution approach acceptable?
✅ API changes acceptable?
✅ Risks acknowledged?
```

---

## 💻 Implementation Phase

### Workflow: Test → Code → Review → Commit

#### Step 1: Write Test First
```python
# tests/test_new_feature.py

import pytest

def test_new_feature_happy_path():
    """Test the main success scenario."""
    result = new_feature(valid_input)
    assert result == expected_output

def test_new_feature_invalid_input():
    """Test error handling."""
    with pytest.raises(ValueError):
        new_feature(invalid_input)

def test_new_feature_edge_case():
    """Test boundary conditions."""
    result = new_feature(edge_case_input)
    assert result is not None
```

**Run test (should FAIL):**
```bash
pytest tests/test_new_feature.py -v
# Expected: FAILED (function doesn't exist yet)
```

#### Step 2: Implement Minimal Code
```python
# src/module/new_feature.py

def new_feature(input_data):
    """
    Brief description of what this does.

    Args:
        input_data: Description of input

    Returns:
        Description of return value

    Raises:
        ValueError: When input is invalid
    """
    # Validate input
    if not input_data:
        raise ValueError("Input cannot be empty")

    # Minimal implementation to pass tests
    return process(input_data)
```

**Run test (should PASS):**
```bash
pytest tests/test_new_feature.py -v
# Expected: PASSED
```

#### Step 3: Review Against Checklist
```bash
# Open CODE_REVIEW_CHECKLIST.md
# Go through EVERY item
# Fix any issues found
```

#### Step 4: Commit
```bash
git add tests/test_new_feature.py src/module/new_feature.py
git commit -m "feat: add new_feature with input validation

- Implements new_feature() with error handling
- Validates input to prevent empty data
- Includes unit tests for happy path and error cases
- Coverage: 100% of new code

Tests: pytest tests/test_new_feature.py (all pass)
Related: #123"
```

---

## 🔍 Code Review Standards

### Every Code Change Must Have:

#### 1. Input Validation
```python
# ✅ GOOD
def process_user_id(user_id: str) -> User:
    if not user_id:
        raise ValueError("user_id cannot be empty")
    if not re.match(r'^\d+$', user_id):
        raise ValueError("user_id must be numeric")
    if len(user_id) > 20:
        raise ValueError("user_id too long")

    return get_user(int(user_id))

# ❌ BAD
def process_user_id(user_id):
    return get_user(int(user_id))  # No validation!
```

#### 2. Error Handling
```python
# ✅ GOOD
def fetch_data(url: str) -> dict:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.Timeout:
        logger.error("Request timeout", extra={"url": url})
        raise ServiceError("External service timeout")
    except requests.HTTPError as e:
        logger.error("HTTP error", extra={"status": e.response.status_code})
        raise ServiceError(f"Failed to fetch data: {e}")
    except ValueError as e:
        logger.error("Invalid JSON", extra={"error": str(e)})
        raise ServiceError("Invalid response format")

# ❌ BAD
def fetch_data(url):
    response = requests.get(url)
    return response.json()  # Can fail in many ways!
```

#### 3. Resource Cleanup
```python
# ✅ GOOD
async def process_file(path: Path) -> dict:
    async with aiofiles.open(path, 'r') as f:
        content = await f.read()

    result = await process_content(content)

    # Cleanup temp file
    if temp_file.exists():
        temp_file.unlink()

    return result

# ❌ BAD
async def process_file(path):
    f = await aiofiles.open(path, 'r')
    content = await f.read()
    return await process_content(content)  # File never closed!
```

#### 4. Thread Safety
```python
# ✅ GOOD
class SafeCounter:
    def __init__(self):
        self._count = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:
            self._count += 1
            return self._count

    def get(self):
        with self._lock:
            return self._count

# ❌ BAD
class UnsafeCounter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1  # Race condition!
        return self.count
```

#### 5. Logging
```python
# ✅ GOOD
import logging
import structlog

logger = structlog.get_logger(__name__)

def dangerous_operation(user_id: str):
    logger.info(
        "Starting operation",
        user_id=user_id,
        operation="dangerous_op"
    )

    try:
        result = perform_operation(user_id)
        logger.info(
            "Operation successful",
            user_id=user_id,
            result_size=len(result)
        )
        return result
    except Exception as e:
        logger.error(
            "Operation failed",
            user_id=user_id,
            error=str(e),
            exc_info=True
        )
        raise

# ❌ BAD
def dangerous_operation(user_id):
    print(f"Starting for {user_id}")  # Don't use print!
    result = perform_operation(user_id)
    return result  # No error logging!
```

---

## 📊 Commit Standards

### Commit Message Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types:
- `feat`: New feature
- `fix`: Bug fix
- `security`: Security fix
- `perf`: Performance improvement
- `refactor`: Code refactoring
- `test`: Adding/updating tests
- `docs`: Documentation changes
- `chore`: Maintenance tasks

### Example:
```
security(cors): fix wildcard origin vulnerability

- Replace allow_origins=["*"] with configurable origins
- Add PULSE_ALLOWED_ORIGINS environment variable
- Default to ["http://localhost:3000"] with warning
- Disable allow_credentials for safety

This fixes a critical CSRF vulnerability where any origin
could make authenticated requests to the API.

BREAKING CHANGE: Applications relying on wildcard CORS
must now configure origins explicitly.

Closes #42
Related: SECURITY_IMPROVEMENTS.md
```

### Commit Size Limits:
```
Maximum per commit:
- 400 lines of code (excluding tests)
- 800 lines total (including tests)
- 10 files changed
- 1 logical feature/fix

If larger:
- Split into multiple commits
- Create intermediate working states
- Each commit should build successfully
```

---

## 🧪 Testing Requirements

### Coverage Requirements:
```
Minimum coverage: 90%
Target coverage: 95%+
Critical paths: 100%
```

### Test Types Required:

#### 1. Unit Tests (ALWAYS)
```python
def test_function_with_valid_input():
    """Test normal operation."""
    result = function(valid_input)
    assert result == expected

def test_function_with_invalid_input():
    """Test error handling."""
    with pytest.raises(ValueError):
        function(invalid_input)

def test_function_edge_cases():
    """Test boundary conditions."""
    assert function("") is None
    assert function("a" * 10000) raises ValueError
```

#### 2. Integration Tests (for APIs)
```python
def test_api_endpoint_success(client):
    """Test successful API call."""
    response = client.post("/api/endpoint", json=valid_payload)
    assert response.status_code == 200
    assert response.json() == expected_response

def test_api_endpoint_validation(client):
    """Test input validation."""
    response = client.post("/api/endpoint", json=invalid_payload)
    assert response.status_code == 422
    assert "error" in response.json()
```

#### 3. Security Tests (for sensitive code)
```python
def test_sql_injection_prevention():
    """Ensure SQL injection is prevented."""
    malicious_input = "1'; DROP TABLE users; --"
    result = query_user(malicious_input)
    assert result is None  # Should not execute malicious SQL

def test_xss_prevention():
    """Ensure XSS is prevented."""
    malicious_input = "<script>alert('xss')</script>"
    result = render_comment(malicious_input)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
```

#### 4. Performance Tests (for critical paths)
```python
@pytest.mark.benchmark
def test_endpoint_performance(benchmark):
    """Ensure endpoint responds quickly."""
    result = benchmark(lambda: call_endpoint())
    assert result.stats.mean < 0.1  # Less than 100ms
```

---

## 🔒 Security Standards

### Input Validation Checklist:
```python
✅ Length checks (max/min)
✅ Format validation (regex)
✅ Type validation
✅ Range checks (numeric)
✅ Whitelist validation (enums)
✅ Encoding validation (UTF-8)
✅ Path traversal prevention
✅ SQL injection prevention
✅ XSS prevention
✅ Command injection prevention
```

### Example Validation Function:
```python
import re
from typing import Optional

def validate_user_input(
    value: str,
    max_length: int = 1000,
    pattern: Optional[str] = None,
    allow_empty: bool = False
) -> str:
    """
    Validate user input with security checks.

    Args:
        value: Input to validate
        max_length: Maximum allowed length
        pattern: Regex pattern to match (if any)
        allow_empty: Whether empty string is allowed

    Returns:
        Validated and sanitized input

    Raises:
        ValueError: If validation fails
    """
    # Check type
    if not isinstance(value, str):
        raise ValueError("Input must be a string")

    # Check empty
    if not allow_empty and not value:
        raise ValueError("Input cannot be empty")

    # Check length
    if len(value) > max_length:
        raise ValueError(f"Input too long (max {max_length} chars)")

    # Check pattern
    if pattern and not re.match(pattern, value):
        raise ValueError(f"Input doesn't match required format")

    # Remove dangerous characters
    sanitized = value.strip()

    # Check for path traversal
    if ".." in sanitized or "/" in sanitized:
        raise ValueError("Invalid characters detected")

    return sanitized
```

---

## 🚀 Performance Standards

### Response Time Requirements:
```
API Endpoints:
- P50: < 50ms
- P95: < 200ms
- P99: < 500ms

Database Queries:
- Simple: < 10ms
- Complex: < 100ms
- Aggregations: < 500ms

Background Jobs:
- Should not block requests
- Use task queues (Celery, RQ)
- Implement timeouts
```

### Performance Checklist:
```python
✅ No N+1 queries
✅ Appropriate database indexes
✅ Query result pagination
✅ Response caching (when appropriate)
✅ Connection pooling
✅ Async I/O for network calls
✅ Bulk operations instead of loops
✅ Memory-efficient data structures
```

### Example Optimization:
```python
# ❌ BAD: N+1 query problem
def get_users_with_posts():
    users = User.query.all()
    result = []
    for user in users:
        posts = Post.query.filter_by(user_id=user.id).all()  # N queries!
        result.append({"user": user, "posts": posts})
    return result

# ✅ GOOD: Single query with join
def get_users_with_posts():
    users = (
        User.query
        .options(joinedload(User.posts))  # Eager loading
        .all()
    )
    return [{"user": u, "posts": u.posts} for u in users]
```

---

## 📝 Documentation Standards

### Every Public Function Must Have:
```python
def function_name(arg1: Type1, arg2: Type2) -> ReturnType:
    """
    Brief one-line description.

    Longer description explaining what this function does,
    when it should be used, and any important considerations.

    Args:
        arg1: Description of first argument
        arg2: Description of second argument

    Returns:
        Description of return value

    Raises:
        ValueError: When input is invalid
        RuntimeError: When operation fails

    Example:
        >>> result = function_name("value1", 42)
        >>> print(result)
        "processed: value1 with 42"

    Note:
        Any important notes or warnings about usage.

    See Also:
        related_function: Related functionality
    """
```

### README Updates Required For:
```
✅ New features (usage examples)
✅ Breaking changes (migration guide)
✅ New configuration options
✅ New dependencies
✅ Security considerations
✅ Performance characteristics
```

---

## 🔄 Refactoring Rules

### When to Refactor:
```
✅ Duplicated code (DRY violation)
✅ Functions > 50 lines
✅ Classes > 500 lines
✅ Cyclomatic complexity > 10
✅ Test coverage < 80%
✅ Performance issues identified
✅ Security vulnerabilities found
```

### Refactoring Process:
```
1. Write tests for current behavior (if missing)
2. Ensure all tests pass
3. Make small, incremental changes
4. Run tests after EACH change
5. Commit after each successful refactoring
6. Never mix refactoring with feature work
```

### Example Refactoring:
```python
# BEFORE: Long function with multiple responsibilities
def process_order(order_data):
    # Validate (30 lines)
    if not order_data.get("id"):
        raise ValueError("Missing ID")
    # ... more validation

    # Calculate totals (20 lines)
    subtotal = 0
    for item in order_data["items"]:
        subtotal += item["price"] * item["quantity"]
    # ... more calculations

    # Save to database (25 lines)
    order = Order(...)
    db.session.add(order)
    # ... more database operations

    # Send notifications (20 lines)
    send_email(...)
    send_sms(...)
    # ... more notifications

    return order

# AFTER: Separated concerns
def process_order(order_data: dict) -> Order:
    """Process an order through the pipeline."""
    validated_data = validate_order(order_data)
    totals = calculate_order_totals(validated_data)
    order = save_order(validated_data, totals)
    notify_order_created(order)
    return order

def validate_order(data: dict) -> dict:
    """Validate order data."""
    # Single responsibility: validation

def calculate_order_totals(data: dict) -> dict:
    """Calculate order totals."""
    # Single responsibility: calculation

def save_order(data: dict, totals: dict) -> Order:
    """Save order to database."""
    # Single responsibility: persistence

def notify_order_created(order: Order) -> None:
    """Send notifications for new order."""
    # Single responsibility: notifications
```

---

## 🎯 Definition of Done

**A task is COMPLETE when:**

```
Code:
✅ Implements requirement fully
✅ Follows all coding standards
✅ Has appropriate error handling
✅ Has input validation
✅ Has resource cleanup
✅ Has logging
✅ Is thread-safe (if needed)
✅ Is performant (meets SLAs)

Tests:
✅ Unit tests written and passing
✅ Integration tests written and passing
✅ Security tests written (if applicable)
✅ Performance tests passing (if applicable)
✅ Coverage >= 90%
✅ No skipped tests without reason

Documentation:
✅ Docstrings complete
✅ README updated (if needed)
✅ API docs updated (if needed)
✅ Migration guide written (if breaking)
✅ CHANGELOG entry added

Quality:
✅ CODE_REVIEW_CHECKLIST.md passed
✅ SECURITY_CHECKLIST.md passed
✅ Linter passing (flake8/black/isort)
✅ Type checker passing (mypy)
✅ No security warnings (bandit)

Git:
✅ Clear commit message
✅ Appropriate commit size
✅ Branch pushed to remote
✅ All CI checks passing
✅ Ready for review/merge
```

---

## 🚫 Anti-Patterns (AVOID)

### 1. God Objects
```python
# ❌ BAD: Class doing too much
class Application:
    def __init__(self):
        self.db = Database()
        self.cache = Cache()
        self.queue = Queue()

    def handle_request(self): pass
    def send_email(self): pass
    def process_payment(self): pass
    def generate_report(self): pass
    # ... 50 more methods

# ✅ GOOD: Separated concerns
class RequestHandler: pass
class EmailService: pass
class PaymentProcessor: pass
class ReportGenerator: pass
```

### 2. Premature Optimization
```python
# ❌ BAD: Optimizing before measuring
def get_users():
    # Added complex caching before profiling
    cache_key = f"users:{hash(time.time())}"
    if cache_key in cache:
        return cache[cache_key]
    # ... complex cache invalidation logic

# ✅ GOOD: Simple first, optimize if needed
def get_users():
    return User.query.all()

# Then profile, and IF slow:
def get_users():
    return cache.get_or_set(
        "users",
        lambda: User.query.all(),
        timeout=60
    )
```

### 3. Copy-Paste Programming
```python
# ❌ BAD: Duplicated code
def process_user_order(order): ...
def process_admin_order(order): ...
def process_guest_order(order): ...
# All three have 90% identical code!

# ✅ GOOD: Extract common logic
def process_order(order, user_type):
    # Common logic
    if user_type == "admin":
        # Admin-specific logic
    # ... handle other types
```

---

**Last Updated:** 2025-11-09
**Version:** 1.0
**Maintained By:** Project QA Team
