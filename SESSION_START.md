# 🚀 AI Agent Session Start Protocol

**MANDATORY: Read and acknowledge ALL files below before starting ANY work**

---

## ⚡ Quick Start (30 seconds)

```bash
# At the start of EVERY session, execute:
1. Read SESSION_START.md (this file)
2. Read AI_AGENT_RULES.md
3. Read CODE_REVIEW_CHECKLIST.md
4. Acknowledge: "Session start protocol acknowledged. All QA requirements loaded."
```

---

## 📋 Core Requirements (MUST READ)

### 1. **AI Agent Development Rules**
**File:** `AI_AGENT_RULES.md`

**Key Points:**
- ✅ Design before code (create design doc first)
- ✅ Max 400 LOC per commit
- ✅ Test at each step
- ✅ Resource cleanup mandatory
- ✅ Error handling required everywhere

**Action:** Read `AI_AGENT_RULES.md` now

---

### 2. **Code Review Checklist**
**File:** `CODE_REVIEW_CHECKLIST.md`

**Key Points:**
- ✅ Memory leak prevention
- ✅ Race condition checks
- ✅ Error handling verification
- ✅ Security validation
- ✅ Performance considerations

**Action:** Read `CODE_REVIEW_CHECKLIST.md` now

---

### 3. **Testing Requirements**
**File:** `TESTING_REQUIREMENTS.md`

**Key Points:**
- ✅ Unit tests for all new code
- ✅ Integration tests for APIs
- ✅ Security tests for auth/validation
- ✅ 90%+ coverage maintained
- ✅ Test failures block commits

**Action:** Read `TESTING_REQUIREMENTS.md` now

---

### 4. **Security Checklist**
**File:** `SECURITY_CHECKLIST.md`

**Key Points:**
- ✅ Input validation everywhere
- ✅ No hardcoded secrets
- ✅ CORS configured properly
- ✅ Rate limiting on public endpoints
- ✅ SQL injection prevention

**Action:** Read `SECURITY_CHECKLIST.md` now

---

## 🎯 Session Workflow

### Phase 1: Understanding (5-10 minutes)
```
1. ✅ Read all QA documentation files
2. ✅ Review existing codebase structure
3. ✅ Check recent commits for context
4. ✅ Identify any known issues or TODOs
5. ✅ Ask clarifying questions BEFORE coding
```

### Phase 2: Design (10-15 minutes)
```
1. ✅ Create design document (DESIGN_*.md)
2. ✅ Identify affected components
3. ✅ List potential risks
4. ✅ Define success criteria
5. ✅ Get user approval on design
```

### Phase 3: Implementation (Iterative)
```
For each feature/fix:
1. ✅ Write failing tests first (TDD)
2. ✅ Implement minimal code to pass tests
3. ✅ Run full test suite
4. ✅ Review against CODE_REVIEW_CHECKLIST.md
5. ✅ Commit with clear message
6. ✅ Repeat until feature complete
```

### Phase 4: Quality Assurance (Before Push)
```
1. ✅ Run CODE_REVIEW_CHECKLIST.md point-by-point
2. ✅ Run SECURITY_CHECKLIST.md verification
3. ✅ Verify all tests pass (pytest --cov)
4. ✅ Check coverage >= 90%
5. ✅ Review commit messages for clarity
6. ✅ Update documentation if needed
```

---

## 🚨 Critical Rules (NEVER SKIP)

### Rule #1: NO CODE WITHOUT TESTS
```python
# ❌ WRONG: Writing code first
def new_feature():
    # implementation
    pass

# ✅ CORRECT: Write test first
def test_new_feature():
    result = new_feature()
    assert result == expected
```

### Rule #2: ALWAYS HANDLE ERRORS
```python
# ❌ WRONG: Unhandled exceptions
def process_data(data):
    return data.parse()  # Can crash

# ✅ CORRECT: Graceful error handling
def process_data(data):
    try:
        return data.parse()
    except ParseError as e:
        logger.error("Failed to parse data", extra={"error": str(e)})
        raise ValidationError(f"Invalid data format: {e}")
```

### Rule #3: VALIDATE ALL INPUTS
```python
# ❌ WRONG: Trusting user input
def save_file(filename, content):
    with open(filename, 'w') as f:
        f.write(content)

# ✅ CORRECT: Validate and sanitize
def save_file(filename, content):
    if not re.match(r'^[a-zA-Z0-9_-]+\.txt$', filename):
        raise ValueError("Invalid filename")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("Content too large")
    safe_path = UPLOAD_DIR / filename
    with open(safe_path, 'w') as f:
        f.write(content)
```

### Rule #4: CLEAN UP RESOURCES
```python
# ❌ WRONG: Resource leaks
def process_file(path):
    f = open(path)
    data = f.read()
    return process(data)  # File never closed

# ✅ CORRECT: Use context managers
def process_file(path):
    with open(path) as f:
        data = f.read()
    return process(data)
```

### Rule #5: THREAD-SAFETY FOR SHARED STATE
```python
# ❌ WRONG: Race conditions
class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1  # Not atomic!

# ✅ CORRECT: Use locks
class Counter:
    def __init__(self):
        self.count = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:
            self.count += 1
```

---

## 📊 Pre-Commit Checklist

**Before EVERY commit, verify:**

```
🔍 Code Quality:
[ ] No commented-out code
[ ] No debug print statements
[ ] No TODO comments without tickets
[ ] No hardcoded values (use config)
[ ] Type hints on all functions
[ ] Docstrings on public APIs

🔒 Security:
[ ] All inputs validated
[ ] No SQL injection vectors
[ ] No XSS vulnerabilities
[ ] CSRF protection enabled
[ ] Rate limiting on endpoints
[ ] Secrets in environment variables

🧪 Testing:
[ ] All new code has tests
[ ] All tests pass (pytest)
[ ] Coverage >= 90% (pytest --cov)
[ ] No test skips without reason
[ ] Integration tests updated

📚 Documentation:
[ ] README updated if needed
[ ] API docs updated
[ ] CHANGELOG entry added
[ ] Migration guide if breaking

🚀 Performance:
[ ] No N+1 queries
[ ] No unbounded loops
[ ] No memory leaks
[ ] No blocking I/O in async code
[ ] Appropriate indexes on queries
```

---

## 🎓 Learning Resources

### Internal Documentation
- `BACKEND_ENGINEERING_REVIEW.md` - Past issues and fixes
- `SECURITY_IMPROVEMENTS.md` - Security history
- `CONTRIBUTING.md` - Development guidelines

### External Resources
- [OWASP Top 10](https://owasp.org/www-project-top-ten/) - Security
- [Python Best Practices](https://docs.python-guide.org/) - Code quality
- [FastAPI Docs](https://fastapi.tiangolo.com/) - Framework

---

## 🐛 Common Pitfalls (AVOID THESE)

### 1. Race Conditions
```python
# Problem: Time-of-check-time-of-use (TOCTOU)
if key not in cache:  # Check
    cache[key] = expensive_operation()  # Use
# Another thread could insert between check and use!

# Solution: Atomic operations
cache.setdefault(key, expensive_operation())
```

### 2. SQL Injection
```python
# Problem: String concatenation
query = f"SELECT * FROM users WHERE id = {user_id}"

# Solution: Parameterized queries
query = "SELECT * FROM users WHERE id = ?"
cursor.execute(query, (user_id,))
```

### 3. Memory Leaks
```python
# Problem: Circular references
class Node:
    def __init__(self):
        self.children = []

    def add_child(self, child):
        self.children.append(child)
        child.parent = self  # Circular reference!

# Solution: Weak references
import weakref

class Node:
    def __init__(self):
        self.children = []
        self._parent = None

    @property
    def parent(self):
        return self._parent() if self._parent else None

    @parent.setter
    def parent(self, value):
        self._parent = weakref.ref(value) if value else None
```

### 4. Async/Await Mistakes
```python
# Problem: Blocking in async function
async def process():
    result = requests.get(url)  # Blocks event loop!
    return result

# Solution: Use async HTTP client
async def process():
    async with httpx.AsyncClient() as client:
        result = await client.get(url)
    return result
```

### 5. Exception Swallowing
```python
# Problem: Hiding errors
try:
    risky_operation()
except:
    pass  # Silent failure!

# Solution: Handle specifically
try:
    risky_operation()
except KnownError as e:
    logger.error("Operation failed", extra={"error": str(e)})
    raise
except Exception as e:
    logger.exception("Unexpected error")
    raise
```

---

## 🎯 Quality Gates (MUST PASS)

### Gate 1: Static Analysis
```bash
# Run before committing
black src/  # Code formatting
isort src/  # Import sorting
flake8 src/  # Linting
mypy src/  # Type checking
```

### Gate 2: Security Scan
```bash
# Run on security-sensitive changes
bandit -r src/  # Security issues
safety check  # Dependency vulnerabilities
```

### Gate 3: Testing
```bash
# Run before every commit
pytest --cov=fastapi_pulse --cov-report=term-missing --cov-fail-under=90
```

### Gate 4: Performance
```bash
# Run on performance-critical changes
pytest tests/benchmarks/  # Performance tests
```

---

## 📞 When to Ask for Help

**ASK IMMEDIATELY if you encounter:**
- ❓ Ambiguous requirements
- ❓ Multiple valid approaches (architecture decisions)
- ❓ Security-sensitive code changes
- ❓ Breaking API changes
- ❓ Performance degradation
- ❓ Test failures you can't explain
- ❓ Dependencies with known vulnerabilities

**DO NOT:**
- ❌ Make assumptions about security requirements
- ❌ Guess at edge case handling
- ❌ Skip tests "because it's simple"
- ❌ Ignore linter warnings
- ❌ Commit failing tests

---

## 🔄 Session End Protocol

**Before ending the session:**

```
1. ✅ All commits pushed to remote branch
2. ✅ All tests passing in CI
3. ✅ Documentation updated
4. ✅ No unfinished work in working directory
5. ✅ Session summary provided to user
6. ✅ TODO items documented if work continues

Session Summary Template:
========================
**Completed:**
- [List all completed tasks]

**Tests:**
- [Test results summary]

**Next Steps:**
- [What should be done next]

**Known Issues:**
- [Any blockers or concerns]
```

---

## ✅ Acknowledgment

**To confirm you've read and understood:**

Reply with:
```
✅ Session Start Protocol Acknowledged

I have read and will follow:
- AI_AGENT_RULES.md
- CODE_REVIEW_CHECKLIST.md
- TESTING_REQUIREMENTS.md
- SECURITY_CHECKLIST.md

I understand:
- Test-first development is mandatory
- All inputs must be validated
- Resource cleanup is required
- Error handling is non-negotiable
- Code review checklist must pass before commit

Ready to begin work with quality assurance in mind.
```

---

**Last Updated:** 2025-11-09
**Version:** 1.0
**Maintained By:** Project QA Team
