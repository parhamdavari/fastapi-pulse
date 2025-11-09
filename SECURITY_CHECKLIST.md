# 🔒 Security Checklist

**Purpose:** Systematic security verification to prevent vulnerabilities in production code.

---

## 🎯 How to Use This Checklist

1. **Before security-sensitive changes:** Read this entire document
2. **During development:** Reference relevant sections
3. **Before commit:** Verify ALL applicable items
4. **Before deployment:** Run security scan tools

**⚠️ If ANY security item fails: STOP and FIX immediately**

---

## 📋 Quick Security Scan

**Run these tools before every commit involving:**
- Authentication/Authorization
- User input handling
- Data storage
- External API calls
- Configuration changes

```bash
# Security vulnerability scanner
bandit -r src/ -f json -o bandit-report.json

# Dependency vulnerability check
safety check --json

# Static analysis
pylint src/ --disable=all --enable=security

# Secret detection
git secrets --scan

# All must pass with zero critical/high severity issues
```

---

## 🔐 Section 1: Authentication

### 1.1 Password Security

```
[ ] Passwords never stored in plaintext
[ ] Using strong hashing (bcrypt, argon2, scrypt)
[ ] Salt generated per-password
[ ] Minimum password requirements enforced
[ ] Password complexity validated
[ ] Common passwords rejected
[ ] Rate limiting on login attempts
[ ] Account lockout after failed attempts
```

**Verify:**
```python
# ✅ GOOD
import bcrypt

def hash_password(password: str) -> str:
    # Validate strength first
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    if not re.search(r'[A-Z]', password):
        raise ValueError("Password must contain uppercase")
    if not re.search(r'[a-z]', password):
        raise ValueError("Password must contain lowercase")
    if not re.search(r'[0-9]', password):
        raise ValueError("Password must contain numbers")

    # Hash with strong algorithm
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()

# ❌ BAD
def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()  # Weak!
```

### 1.2 Session Management

```
[ ] Secure session tokens (cryptographically random)
[ ] Tokens have expiration
[ ] Tokens invalidated on logout
[ ] Session fixation prevented
[ ] HttpOnly cookies for session tokens
[ ] Secure flag on cookies (HTTPS only)
[ ] SameSite cookie attribute set
[ ] CSRF tokens implemented
```

**Verify:**
```python
# ✅ GOOD
import secrets
from datetime import datetime, timedelta

def create_session_token() -> str:
    return secrets.token_urlsafe(32)  # 256-bit entropy

def create_session(user_id: int) -> Session:
    token = create_session_token()
    expires = datetime.utcnow() + timedelta(hours=24)

    session = Session(
        token=token,
        user_id=user_id,
        expires_at=expires,
        csrf_token=secrets.token_urlsafe(32)
    )
    db.session.add(session)
    db.session.commit()
    return session

# Set secure cookie
response.set_cookie(
    "session",
    session.token,
    httponly=True,
    secure=True,  # HTTPS only
    samesite="strict",
    max_age=86400
)

# ❌ BAD
def create_session(user_id):
    token = str(user_id) + str(time.time())  # Predictable!
    return Session(token=token, user_id=user_id)
```

### 1.3 JWT Tokens

```
[ ] JWT secret is strong and random
[ ] JWT secret stored securely (env var)
[ ] Token expiration set
[ ] Token signature verified
[ ] Refresh tokens implemented
[ ] Refresh tokens rotated
[ ] Revocation list implemented (if needed)
[ ] Algorithm not set to "none"
```

**Verify:**
```python
# ✅ GOOD
import jwt
from datetime import datetime, timedelta

JWT_SECRET = os.getenv("JWT_SECRET")  # From environment
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise ValueError("JWT_SECRET must be set and >= 32 chars")

JWT_ALGORITHM = "HS256"  # Never "none"!

def create_access_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(minutes=15),
        "iat": datetime.utcnow(),
        "type": "access"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]  # Explicit algorithm
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthError("Token expired")
    except jwt.InvalidTokenError:
        raise AuthError("Invalid token")

# ❌ BAD
def create_token(user_id):
    return jwt.encode({"user_id": user_id}, "hardcoded-secret")
```

---

## 🚪 Section 2: Authorization

### 2.1 Access Control

```
[ ] Authorization checks on ALL protected endpoints
[ ] Principle of least privilege followed
[ ] Role-based access control (RBAC) implemented
[ ] Resource ownership verified
[ ] Default deny policy
[ ] No privilege escalation possible
[ ] Authorization failures logged
```

**Verify:**
```python
# ✅ GOOD
from functools import wraps

def require_permission(permission: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user()

            if not user.has_permission(permission):
                logger.warning(
                    "Authorization failed",
                    user_id=user.id,
                    permission=permission,
                    endpoint=func.__name__
                )
                raise PermissionDenied(f"Missing permission: {permission}")

            return func(*args, **kwargs)
        return wrapper
    return decorator

@router.delete("/users/{user_id}")
@require_auth
@require_permission("users.delete")
def delete_user(user_id: int):
    user = get_current_user()

    # Verify ownership or admin
    if user.id != user_id and not user.is_admin:
        raise PermissionDenied("Cannot delete other users")

    User.delete(user_id)

# ❌ BAD
@router.delete("/users/{user_id}")
def delete_user(user_id: int):
    User.delete(user_id)  # No authorization!
```

### 2.2 API Security

```
[ ] API authentication required
[ ] API rate limiting implemented
[ ] API keys properly validated
[ ] API keys rotatable
[ ] API versioning implemented
[ ] Deprecation notices for old APIs
[ ] Input validation on all endpoints
```

**Verify:**
```python
# ✅ GOOD
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/api/v1/orders")
@limiter.limit("10/minute")
@require_api_key
async def create_order(order: OrderCreate, api_key: str):
    # Validate API key
    if not is_valid_api_key(api_key):
        logger.warning("Invalid API key", key_prefix=api_key[:8])
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check rate limits
    if is_rate_limited(api_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Validate input
    validated_order = validate_order(order)

    return process_order(validated_order)

# ❌ BAD
@router.post("/api/orders")
def create_order(order: dict):
    return process_order(order)  # No auth, no validation!
```

---

## 🛡️ Section 3: Input Validation

### 3.1 Input Sanitization

```
[ ] All user inputs validated
[ ] Type validation enforced
[ ] Length limits enforced
[ ] Format validation (regex)
[ ] Whitelist validation (when possible)
[ ] Blacklist validation (as backup)
[ ] Special characters escaped
[ ] Unicode handling correct
```

**Verify:**
```python
# ✅ GOOD
import re
from pydantic import BaseModel, validator

class UserInput(BaseModel):
    email: str
    name: str
    age: int

    @validator('email')
    def validate_email(cls, v):
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(pattern, v):
            raise ValueError('Invalid email format')
        if len(v) > 255:
            raise ValueError('Email too long')
        return v.lower().strip()

    @validator('name')
    def validate_name(cls, v):
        if len(v) < 2 or len(v) > 100:
            raise ValueError('Name must be 2-100 characters')
        if not re.match(r'^[a-zA-Z\s\-]+$', v):
            raise ValueError('Name contains invalid characters')
        return v.strip()

    @validator('age')
    def validate_age(cls, v):
        if not 0 <= v <= 150:
            raise ValueError('Age must be between 0 and 150')
        return v

# ❌ BAD
def process_user_input(email, name, age):
    # No validation!
    return create_user(email, name, age)
```

### 3.2 SQL Injection Prevention

```
[ ] Parameterized queries used
[ ] ORM used correctly
[ ] No string concatenation in queries
[ ] Input validation before queries
[ ] Least privilege database user
[ ] Stored procedures used (when appropriate)
```

**Verify:**
```python
# ✅ GOOD - Using ORM
def get_user_by_email(email: str) -> User:
    # Validate input
    if not is_valid_email(email):
        raise ValueError("Invalid email")

    # Use parameterized query (ORM does this)
    return db.query(User).filter(User.email == email).first()

# ✅ GOOD - Raw SQL with parameters
def get_user_by_email(email: str) -> User:
    query = "SELECT * FROM users WHERE email = ?"
    result = db.execute(query, (email,))  # Parameterized
    return result.fetchone()

# ❌ BAD - SQL injection vulnerable
def get_user_by_email(email):
    query = f"SELECT * FROM users WHERE email = '{email}'"
    return db.execute(query)  # VULNERABLE!
```

### 3.3 XSS Prevention

```
[ ] All user content escaped
[ ] Content Security Policy (CSP) headers set
[ ] Output encoding appropriate for context
[ ] No innerHTML with user content
[ ] Template auto-escaping enabled
[ ] Sanitize HTML input (if allowing HTML)
```

**Verify:**
```python
# ✅ GOOD
from markupsafe import escape
import bleach

def render_user_comment(comment: str) -> str:
    # Escape all HTML
    safe_comment = escape(comment)
    return f"<div class='comment'>{safe_comment}</div>"

def render_rich_content(content: str) -> str:
    # If HTML is allowed, sanitize it
    allowed_tags = ['b', 'i', 'u', 'p', 'br']
    allowed_attrs = {}
    clean_content = bleach.clean(
        content,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True
    )
    return clean_content

# Set CSP headers
@app.after_request
def set_csp(response):
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.example.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:;"
    )
    return response

# ❌ BAD
def render_comment(comment):
    return f"<div>{comment}</div>"  # XSS vulnerable!
```

### 3.4 Path Traversal Prevention

```
[ ] File paths validated
[ ] No ../ in paths
[ ] Paths normalized
[ ] Whitelist of allowed directories
[ ] Symbolic links resolved safely
[ ] Filename sanitization
```

**Verify:**
```python
# ✅ GOOD
from pathlib import Path

UPLOAD_DIR = Path("/var/app/uploads").resolve()

def save_upload(filename: str, content: bytes):
    # Sanitize filename
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
    if not safe_name or safe_name.startswith('.'):
        raise ValueError("Invalid filename")

    # Resolve full path
    file_path = (UPLOAD_DIR / safe_name).resolve()

    # Verify still within upload directory
    if not file_path.is_relative_to(UPLOAD_DIR):
        raise ValueError("Path traversal detected")

    # Save file
    with open(file_path, 'wb') as f:
        f.write(content)

# ❌ BAD
def save_upload(filename, content):
    path = f"/var/app/uploads/{filename}"  # No validation!
    with open(path, 'wb') as f:
        f.write(content)
```

---

## 🔑 Section 4: Secrets Management

### 4.1 Secret Storage

```
[ ] No secrets in code
[ ] No secrets in version control
[ ] Secrets in environment variables
[ ] Secrets in secure vault (production)
[ ] Secrets rotated regularly
[ ] Access to secrets logged
[ ] Secrets encrypted at rest
```

**Verify:**
```python
# ✅ GOOD
import os

# Load from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not configured")

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise ValueError("JWT_SECRET must be >= 32 characters")

# Or use secrets manager
from secretsmanager import get_secret

API_KEY = get_secret("api/external/key")

# ❌ BAD
DATABASE_URL = "postgresql://user:password@localhost/db"  # Hardcoded!
JWT_SECRET = "my-secret-key"  # In code!
```

### 4.2 Environment Configuration

```
[ ] Separate configs for dev/staging/prod
[ ] Production secrets not in dev
[ ] .env files in .gitignore
[ ] .env.example provided (no secrets)
[ ] Environment validation on startup
[ ] Configuration documented
```

**Verify:**
```python
# ✅ GOOD
# .env.example (in git)
DATABASE_URL=postgresql://localhost/mydb
JWT_SECRET=<generate-strong-secret-here>
ENVIRONMENT=development

# .env (in .gitignore, never committed)
DATABASE_URL=postgresql://user:pass@prod-db/db
JWT_SECRET=<actual-production-secret>
ENVIRONMENT=production

# config.py
import os

class Config:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        self.jwt_secret = os.getenv("JWT_SECRET")
        self.environment = os.getenv("ENVIRONMENT", "development")

        # Validate
        self._validate()

    def _validate(self):
        if not self.database_url:
            raise ValueError("DATABASE_URL required")
        if not self.jwt_secret or len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be >= 32 chars")
        if self.environment not in ["development", "staging", "production"]:
            raise ValueError("Invalid ENVIRONMENT")

        # Production checks
        if self.environment == "production":
            if "localhost" in self.database_url:
                raise ValueError("Cannot use localhost in production")

# ❌ BAD
DATABASE_URL = "postgresql://localhost/db"  # Same for all environments!
```

---

## 🌐 Section 5: Network Security

### 5.1 HTTPS/TLS

```
[ ] HTTPS enforced in production
[ ] TLS 1.2+ only
[ ] Strong cipher suites
[ ] HSTS header set
[ ] Certificate validation
[ ] No mixed content
[ ] Secure redirect (HTTP -> HTTPS)
```

**Verify:**
```python
# ✅ GOOD
@app.before_request
def enforce_https():
    if not request.is_secure and os.getenv("ENVIRONMENT") == "production":
        url = request.url.replace("http://", "https://", 1)
        return redirect(url, code=301)

@app.after_request
def set_security_headers(response):
    # HSTS
    response.headers['Strict-Transport-Security'] = (
        'max-age=31536000; includeSubDomains'
    )
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    # Prevent MIME sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # XSS protection
    response.headers['X-XSS-Protection'] = '1; mode=block'

    return response

# ❌ BAD
# No HTTPS enforcement, no security headers
```

### 5.2 CORS Configuration

```
[ ] CORS origins explicitly listed
[ ] No wildcard origins with credentials
[ ] Methods restricted appropriately
[ ] Headers restricted appropriately
[ ] Preflight requests handled
[ ] Credentials flag configured correctly
```

**Verify:**
```python
# ✅ GOOD
from fastapi.middleware.cors import CORSMiddleware

allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
if not allowed_origins or allowed_origins == [""]:
    if os.getenv("ENVIRONMENT") == "production":
        raise ValueError("ALLOWED_ORIGINS must be set in production")
    allowed_origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,  # Safer default
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600
)

# ❌ BAD
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Wildcard!
    allow_credentials=True,  # With credentials = CSRF risk!
    allow_methods=["*"],
    allow_headers=["*"]
)
```

### 5.3 Rate Limiting

```
[ ] Rate limits on authentication endpoints
[ ] Rate limits on expensive operations
[ ] Rate limits on public APIs
[ ] Different limits for authenticated users
[ ] Rate limit info in response headers
[ ] 429 status code returned
[ ] Distributed rate limiting (if multi-server)
```

**Verify:**
```python
# ✅ GOOD
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/hour"]
)

@app.route("/auth/login")
@limiter.limit("5/minute")  # Strict limit on login
def login():
    pass

@app.route("/api/expensive-operation")
@limiter.limit("10/hour")
def expensive_op():
    pass

@app.route("/api/data")
@limiter.limit("1000/hour")  # Higher for normal ops
def get_data():
    pass

# Return rate limit headers
@app.after_request
def add_rate_limit_headers(response):
    response.headers['X-RateLimit-Limit'] = limiter.current_limit
    response.headers['X-RateLimit-Remaining'] = limiter.current_limit - limiter.current_usage
    response.headers['X-RateLimit-Reset'] = limiter.reset_time
    return response

# ❌ BAD
@app.route("/auth/login")
def login():
    pass  # No rate limiting - brute force possible!
```

---

## 📊 Section 6: Data Protection

### 6.1 PII Handling

```
[ ] PII identified and classified
[ ] PII encrypted at rest
[ ] PII encrypted in transit
[ ] PII masked in logs
[ ] PII not in URLs
[ ] PII retention policy
[ ] PII deletion process
[ ] Data minimization practiced
```

**Verify:**
```python
# ✅ GOOD
import re
from cryptography.fernet import Fernet

# Load encryption key from secure location
ENCRYPTION_KEY = os.getenv("DATA_ENCRYPTION_KEY").encode()
cipher = Fernet(ENCRYPTION_KEY)

def mask_pii(value: str, mask_type: str = "email") -> str:
    """Mask PII for logging."""
    if mask_type == "email":
        parts = value.split("@")
        return f"{parts[0][:2]}***@{parts[1]}"
    elif mask_type == "phone":
        return f"***-***-{value[-4:]}"
    elif mask_type == "ssn":
        return f"***-**-{value[-4:]}"
    return "***"

def encrypt_pii(data: str) -> bytes:
    """Encrypt PII for storage."""
    return cipher.encrypt(data.encode())

def decrypt_pii(encrypted: bytes) -> str:
    """Decrypt PII for use."""
    return cipher.decrypt(encrypted).decode()

# Use in logging
logger.info(
    "User logged in",
    user_id=user.id,
    email=mask_pii(user.email, "email")  # Masked
)

# Store encrypted
user.ssn_encrypted = encrypt_pii(ssn)

# ❌ BAD
logger.info(f"User {user.email} logged in with SSN {user.ssn}")  # PII leak!
```

### 6.2 Data Validation

```
[ ] Data types validated
[ ] Data ranges validated
[ ] Business rules enforced
[ ] Referential integrity maintained
[ ] Transactions used appropriately
[ ] Data backup verified
[ ] Data recovery tested
```

**Verify:**
```python
# ✅ GOOD
from pydantic import BaseModel, validator
from datetime import date

class UserCreate(BaseModel):
    email: str
    age: int
    birth_date: date

    @validator('email')
    def validate_email(cls, v):
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v):
            raise ValueError('Invalid email')
        return v

    @validator('age')
    def validate_age(cls, v):
        if not 13 <= v <= 120:
            raise ValueError('Age must be 13-120')
        return v

    @validator('birth_date')
    def validate_birth_date(cls, v, values):
        # Cross-field validation
        if 'age' in values:
            years_ago = date.today().year - v.year
            if abs(years_ago - values['age']) > 1:
                raise ValueError('Age and birth date do not match')
        return v

# ❌ BAD
def create_user(email, age, birth_date):
    user = User(email=email, age=age, birth_date=birth_date)
    db.session.add(user)  # No validation!
```

---

## 🔍 Section 7: Logging & Monitoring

### 7.1 Security Logging

```
[ ] Authentication events logged
[ ] Authorization failures logged
[ ] Input validation failures logged
[ ] Unusual patterns detected
[ ] Logs include correlation IDs
[ ] Logs exclude sensitive data
[ ] Logs tamper-proof
[ ] Logs retained appropriately
```

**Verify:**
```python
# ✅ GOOD
import structlog
import uuid

logger = structlog.get_logger()

def authenticate(email: str, password: str) -> User:
    correlation_id = str(uuid.uuid4())

    logger.info(
        "Authentication attempt",
        correlation_id=correlation_id,
        email=mask_pii(email, "email"),
        ip_address=get_client_ip()
    )

    user = get_user_by_email(email)
    if not user:
        logger.warning(
            "Authentication failed: user not found",
            correlation_id=correlation_id,
            email=mask_pii(email, "email")
        )
        raise AuthError("Invalid credentials")

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        db.session.commit()

        logger.warning(
            "Authentication failed: invalid password",
            correlation_id=correlation_id,
            user_id=user.id,
            failed_attempts=user.failed_login_attempts
        )
        raise AuthError("Invalid credentials")

    user.failed_login_attempts = 0
    user.last_login = datetime.utcnow()
    db.session.commit()

    logger.info(
        "Authentication successful",
        correlation_id=correlation_id,
        user_id=user.id
    )
    return user

# ❌ BAD
def authenticate(email, password):
    user = get_user_by_email(email)
    if verify_password(password, user.password_hash):
        return user
    raise AuthError("Invalid")  # No logging!
```

### 7.2 Monitoring

```
[ ] Failed authentication monitored
[ ] Rate limit violations monitored
[ ] Error rates monitored
[ ] Response times monitored
[ ] Resource usage monitored
[ ] Security alerts configured
[ ] Incident response plan exists
```

---

## ✅ Security Checklist Summary

**Before EVERY commit:**

```
Authentication:
[ ] Passwords properly hashed
[ ] Session management secure
[ ] JWT properly implemented

Authorization:
[ ] Access control on all endpoints
[ ] Ownership verification
[ ] Rate limiting implemented

Input Validation:
[ ] All inputs validated
[ ] SQL injection prevented
[ ] XSS prevented
[ ] Path traversal prevented

Secrets:
[ ] No secrets in code
[ ] Environment variables used
[ ] Production secrets separate

Network:
[ ] HTTPS enforced (production)
[ ] CORS configured properly
[ ] Security headers set
[ ] Rate limiting active

Data Protection:
[ ] PII encrypted
[ ] PII masked in logs
[ ] Data validation enforced

Logging:
[ ] Security events logged
[ ] No sensitive data in logs
[ ] Correlation IDs included
```

**Run security tools:**

```bash
# Must all pass
bandit -r src/
safety check
pylint --disable=all --enable=security src/
```

**Sign off:**

```
✅ All security items verified
✅ Security tools passed
✅ No vulnerabilities introduced
✅ Security logging added
✅ Ready for security review

Reviewed by: [Your Name]
Date: [YYYY-MM-DD]
Commit: [commit hash]
```

---

**Last Updated:** 2025-11-09
**Version:** 1.0
**Maintained By:** Project QA Team
