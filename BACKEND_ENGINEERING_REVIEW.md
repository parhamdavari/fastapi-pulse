# Backend Engineering Review: FastAPI Pulse

**Reviewer Role:** Principal Backend Engineer
**Review Date:** 2025-11-09
**Codebase Version:** 0.2.0
**Lines of Code:** ~1,523 (main source) + 1,136 (tests)

---

## Executive Summary

FastAPI Pulse is a **well-architected, production-ready monitoring library** with strong fundamentals. The code demonstrates professional practices including thread-safety, rolling window metrics, comprehensive testing (90%+ coverage), and excellent documentation. However, there are several areas requiring attention to enhance security, scalability, observability, and developer experience.

**Overall Assessment:** 7.5/10 (Production-Ready with Improvements Needed)

---

## 🔴 MANDATORY IMPROVEMENTS

### 1. Security Vulnerabilities

#### 1.1 **CRITICAL: Insecure CORS Configuration**
**Location:** `src/fastapi_pulse/__init__.py:66-73`

```python
allow_origins=["*"],  # In production, specify your domain
allow_credentials=True,
allow_headers=["*"],
```

**Issue:** This is a **critical security vulnerability**. Allowing all origins (`*`) with credentials enabled (`allow_credentials=True`) creates a major CSRF and credential leakage risk. This configuration allows any website to make authenticated requests to your API.

**Impact:**
- Cross-Site Request Forgery (CSRF) attacks
- Session hijacking
- Credential theft
- Data exfiltration

**Fix:**
```python
# Option 1: Make CORS optional with safe defaults
if enable_cors:
    allowed_origins = os.getenv("PULSE_ALLOWED_ORIGINS", "").split(",")
    if not allowed_origins or allowed_origins == [""]:
        logger.warning(
            "CORS enabled without PULSE_ALLOWED_ORIGINS. "
            "Using restrictive defaults. Set PULSE_ALLOWED_ORIGINS env var."
        )
        allowed_origins = ["http://localhost:3000"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,  # Disable unless absolutely necessary
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Correlation-ID"],
    )

# Option 2: Document that users should add their own CORS
# Remove CORS middleware entirely and document in README
```

**Priority:** P0 - Fix immediately before any production use

---

#### 1.2 **HIGH: Payload Storage Without Sanitization**
**Location:** `src/fastapi_pulse/payload_store.py:42-47`

**Issue:** User-provided payloads are stored to disk without validation or size limits. This enables:
- Disk space exhaustion attacks
- Path traversal attacks (if endpoint_id is not sanitized)
- Arbitrary file writes

**Fix:**
```python
# Add validation in PulsePayloadStore.__init__
MAX_PAYLOAD_SIZE = 1024 * 1024  # 1MB
MAX_TOTAL_SIZE = 10 * 1024 * 1024  # 10MB

def set(self, endpoint_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    # Validate endpoint_id to prevent path traversal
    if not re.match(r'^[A-Z]+ /[a-zA-Z0-9/_-]+$', endpoint_id):
        raise ValueError(f"Invalid endpoint_id format: {endpoint_id}")

    # Validate payload size
    payload_json = json.dumps(payload)
    if len(payload_json) > self.MAX_PAYLOAD_SIZE:
        raise ValueError(f"Payload too large: {len(payload_json)} bytes")

    # Check total storage size
    if self.file_path.exists():
        total_size = self.file_path.stat().st_size
        if total_size > self.MAX_TOTAL_SIZE:
            raise ValueError("Payload storage limit exceeded")

    cleaned = self._sanitize_payload(payload)
    # ... rest of implementation
```

**Priority:** P0 - Critical security issue

---

#### 1.3 **MEDIUM: No Rate Limiting on Probe Endpoints**
**Location:** `src/fastapi_pulse/router.py:231-248`

**Issue:** The `/health/pulse/probe` endpoint can be called unlimited times, potentially:
- Causing resource exhaustion
- Creating a self-DDoS scenario
- Overwhelming downstream services

**Fix:**
```python
# Add rate limiting middleware or decorator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/pulse/probe")
@limiter.limit("5/minute")  # Max 5 probe jobs per minute
async def trigger_probe(...):
    # existing implementation
```

**Alternative:** Add a cooldown mechanism in `PulseProbeManager`:
```python
class PulseProbeManager:
    def __init__(self, ...):
        self._last_probe_time: Optional[float] = None
        self._min_probe_interval = 30.0  # 30 seconds

    def start_probe(self, endpoints: List[EndpointInfo]) -> str:
        now = time.time()
        if self._last_probe_time and (now - self._last_probe_time) < self._min_probe_interval:
            raise RuntimeError(
                f"Probe cooldown active. Wait {self._min_probe_interval - (now - self._last_probe_time):.1f}s"
            )
        self._last_probe_time = now
        # ... rest
```

**Priority:** P1 - Important for production stability

---

### 2. Reliability & Error Handling

#### 2.1 **CRITICAL: Unbounded Memory Growth in Metrics**
**Location:** `src/fastapi_pulse/metrics.py:136-151`

**Issue:** The `endpoint_metrics`, `request_counts`, `error_counts`, and `status_codes` dictionaries grow unbounded. In high-cardinality scenarios (dynamic URLs, many endpoints), this causes memory leaks.

**Scenario:**
```python
# If path normalization fails or is bypassed:
GET /users/123456/profile
GET /users/234567/profile
# ... thousands of unique paths
# Memory grows infinitely
```

**Fix:**
```python
class PulseMetrics:
    def __init__(self, ..., max_endpoints: int = 1000):
        self.max_endpoints = max_endpoints
        self._endpoint_access_times: Dict[str, float] = {}

    def record_request(self, endpoint: str, method: str, ...):
        with self._lock:
            key = f"{method} {endpoint}"

            # Enforce max endpoints with LRU eviction
            if key not in self.request_counts:
                if len(self.request_counts) >= self.max_endpoints:
                    # Evict least recently used endpoint
                    oldest_key = min(
                        self._endpoint_access_times.items(),
                        key=lambda x: x[1]
                    )[0]
                    self._evict_endpoint(oldest_key)

            self._endpoint_access_times[key] = time.time()
            # ... rest of implementation

    def _evict_endpoint(self, key: str):
        self.request_counts.pop(key, None)
        self.error_counts.pop(key, None)
        self.status_codes.pop(key, None)
        self.endpoint_metrics.pop(key, None)
        self._latency_trackers.pop(key, None)
        self._endpoint_access_times.pop(key, None)
        logger.info(f"Evicted endpoint metrics: {key}")
```

**Priority:** P0 - Can cause production outages

---

#### 2.2 **HIGH: Probe Manager Lacks Concurrent Job Limit**
**Location:** `src/fastapi_pulse/probe.py:92-115`

**Issue:** Multiple probe jobs can run simultaneously without limit, causing resource exhaustion.

**Fix:**
```python
class PulseProbeManager:
    def __init__(self, ..., max_concurrent_jobs: int = 3):
        self._jobs: Dict[str, ProbeJob] = {}
        self._max_concurrent_jobs = max_concurrent_jobs

    def start_probe(self, endpoints: List[EndpointInfo]) -> str:
        # Check running jobs
        running = sum(1 for job in self._jobs.values() if job.status == "running")
        if running >= self._max_concurrent_jobs:
            raise RuntimeError(
                f"Too many concurrent probe jobs ({running}/{self._max_concurrent_jobs}). "
                "Wait for existing jobs to complete."
            )
        # ... rest
```

**Priority:** P1 - Production stability

---

#### 2.3 **HIGH: No Timeout on Probe Jobs**
**Location:** `src/fastapi_pulse/probe.py:133-147`

**Issue:** Probe jobs can hang indefinitely if endpoints are slow or unresponsive.

**Fix:**
```python
async def _run_job(self, job: ProbeJob, endpoints: List[EndpointInfo]) -> None:
    job.status = "running"
    job.started_at = time.time()

    try:
        # Add overall job timeout (10 minutes)
        async with asyncio.timeout(600):
            async with httpx.AsyncClient(...) as client:
                tasks = [...]
                await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.TimeoutError:
        job.status = "timeout"
        logger.error(f"Probe job {job.job_id} timed out after 600s")
    else:
        job.status = "completed"
    finally:
        job.completed_at = time.time()
        if job._future and not job._future.done():
            job._future.set_result(job)
```

**Priority:** P1 - Prevents resource leaks

---

#### 2.4 **MEDIUM: Missing Error Recovery in Middleware**
**Location:** `src/fastapi_pulse/middleware.py:78-135`

**Issue:** If `metrics.record_request()` raises an exception, the middleware crashes the entire request.

**Fix:**
```python
finally:
    duration_ms = self._ensure_duration(duration_ms, start_time)
    final_status = status_code if not request_failed else 500

    if track_metrics:
        try:
            self.metrics.record_request(...)
        except Exception as e:
            # Never let metrics collection crash user requests
            logger.exception(
                "Failed to record metrics (non-fatal)",
                extra={"error": str(e), "endpoint": endpoint_path}
            )

        try:
            if self.enable_detailed_logging and (...):
                self._log_performance_alert(...)
        except Exception as e:
            logger.exception("Failed to log performance alert", extra={"error": str(e)})

        try:
            self._check_sla_violation(...)
        except Exception as e:
            logger.exception("Failed to check SLA violation", extra={"error": str(e)})
```

**Priority:** P1 - Reliability

---

### 3. Performance & Scalability

#### 3.1 **HIGH: Synchronous File I/O in Request Path**
**Location:** `src/fastapi_pulse/payload_store.py:32-37`

**Issue:** The `_flush()` method performs synchronous file I/O while holding a lock. This blocks all requests that trigger metrics recording.

**Fix:**
```python
import aiofiles

class PulsePayloadStore:
    async def _flush_async(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.file_path.with_suffix(".tmp")

        async with aiofiles.open(tmp_path, "w", encoding="utf-8") as handle:
            await handle.write(
                json.dumps(self._payloads, indent=2, ensure_ascii=False)
            )

        # Atomic rename (still synchronous, but fast)
        tmp_path.replace(self.file_path)

    async def set_async(self, endpoint_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = self._sanitize_payload(payload)
        with self._lock:
            self._payloads[endpoint_id] = cleaned
        await self._flush_async()  # Don't hold lock during I/O
        return cleaned
```

**Alternative:** Use a background task queue:
```python
def set(self, endpoint_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = self._sanitize_payload(payload)
    with self._lock:
        self._payloads[endpoint_id] = cleaned
        self._dirty = True

    # Flush in background (debounced)
    self._schedule_flush()
    return cleaned
```

**Priority:** P1 - Performance bottleneck

---

#### 3.2 **MEDIUM: Lock Contention in Metrics Collection**
**Location:** `src/fastapi_pulse/metrics.py:159-193`

**Issue:** A single global lock protects all metrics. Under high load, this creates contention.

**Fix:** Use lock-free data structures or per-endpoint locks:
```python
from collections.abc import defaultdict
import threading

class PulseMetrics:
    def __init__(self, ...):
        # Use a striped lock pattern
        self._lock_count = 16
        self._locks = [threading.Lock() for _ in range(self._lock_count)]

    def _get_lock(self, key: str) -> threading.Lock:
        # Hash-based lock selection
        lock_idx = hash(key) % self._lock_count
        return self._locks[lock_idx]

    def record_request(self, endpoint: str, method: str, ...):
        key = f"{method} {endpoint}"
        with self._get_lock(key):
            # Update only this endpoint's metrics
            tracker = self._latency_trackers[key]
            # ...
```

**Priority:** P2 - Optimization for high-throughput scenarios

---

### 4. Code Quality & Maintainability

#### 4.1 **MEDIUM: Missing Type Hints**
**Location:** Multiple files

**Issue:** Several functions lack return type annotations:
- `middleware.py:142` - `_log_performance_alert` returns None implicitly
- `probe.py:255` - `_format_path` is static but could be clearer
- Several async functions missing `-> None` annotations

**Fix:**
```python
def _log_performance_alert(
    self, method: str, path: str, status_code: int,
    duration_ms: float, correlation_id: str
) -> None:
    # ...

@staticmethod
def _format_path(path: str, path_params: Dict[str, Any]) -> str:
    # ...
```

**Priority:** P2 - Code quality

---

#### 4.2 **LOW: Inconsistent Error Messages**
**Location:** Multiple files

**Issue:** Error messages use different formats:
- `router.py:39` - "Did you call add_pulse()?"
- `probe.py:217` - "# pragma: no cover - network issues"
- Some use f-strings, others use `%s` formatting

**Fix:** Establish consistent error message format:
```python
# Standard format: "<Component>: <Error description>. <Suggestion>"
raise RuntimeError(
    "PulseEndpointRegistry: Registry not initialized. "
    "Ensure add_pulse() was called during app startup."
)
```

**Priority:** P3 - Polish

---

## 🟡 OPTIONAL IMPROVEMENTS

### 5. Architecture & Design

#### 5.1 **Add Metrics Export Support**
**Impact:** Enable integration with Prometheus, Datadog, New Relic

**Suggestion:**
```python
# New file: src/fastapi_pulse/exporters.py
class PrometheusExporter:
    """Export metrics in Prometheus format."""

    def export(self, metrics: PulseMetrics) -> str:
        data = metrics.get_metrics()
        lines = []

        # Counter metrics
        lines.append("# HELP http_requests_total Total HTTP requests")
        lines.append("# TYPE http_requests_total counter")
        for endpoint, count in data["request_counts"].items():
            method, path = endpoint.split(" ", 1)
            lines.append(
                f'http_requests_total{{method="{method}",path="{path}"}} {count}'
            )

        # Histogram metrics for latency
        lines.append("# HELP http_request_duration_ms HTTP request latency")
        lines.append("# TYPE http_request_duration_ms histogram")
        # ... convert percentiles to histogram buckets

        return "\n".join(lines)

# In router.py
@router.get("/metrics")
def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    exporter = PrometheusExporter()
    return Response(
        content=exporter.export(metrics),
        media_type="text/plain; version=0.0.4"
    )
```

**Priority:** P2 - High value for production use

---

#### 5.2 **Add Health Check Levels**
**Impact:** Enable Kubernetes liveness/readiness probes

**Suggestion:**
```python
@router.get("/pulse/live")
def liveness():
    """Kubernetes liveness probe - basic app health."""
    return {"status": "alive", "timestamp": time.time()}

@router.get("/pulse/ready")
def readiness():
    """Kubernetes readiness probe - app ready to serve traffic."""
    # Check if critical dependencies are healthy
    summary = metrics.get_metrics()["summary"]
    error_rate = summary.get("error_rate", 0)

    if error_rate > 50:  # More than 50% errors
        raise HTTPException(
            status_code=503,
            detail="Service degraded: high error rate"
        )

    return {
        "status": "ready",
        "error_rate": error_rate,
        "timestamp": time.time()
    }
```

**Priority:** P2 - Essential for Kubernetes deployments

---

#### 5.3 **Add Metrics Persistence**
**Impact:** Survive restarts, historical analysis

**Suggestion:**
```python
class PulseMetrics:
    def __init__(self, ..., persistence_path: Optional[Path] = None):
        self.persistence_path = persistence_path
        if persistence_path:
            self._load_state()

    def _load_state(self):
        """Load persisted metrics on startup."""
        if self.persistence_path and self.persistence_path.exists():
            with self.persistence_path.open("r") as f:
                state = json.load(f)
                # Restore counters (not time-based metrics)
                self.request_counts = defaultdict(int, state.get("request_counts", {}))
                self.error_counts = defaultdict(int, state.get("error_counts", {}))

    def persist(self):
        """Periodically save state to disk."""
        if not self.persistence_path:
            return

        state = {
            "request_counts": dict(self.request_counts),
            "error_counts": dict(self.error_counts),
            "timestamp": time.time()
        }

        with self.persistence_path.open("w") as f:
            json.dump(state, f)
```

**Priority:** P3 - Nice to have

---

### 6. Testing Improvements

#### 6.1 **Add Load Testing**
**Impact:** Verify performance under stress

**Suggestion:**
```python
# tests/test_performance.py
import pytest
import asyncio
from locust import HttpUser, task, between

class PulseLoadTest(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def check_endpoint(self):
        self.client.get("/test/success")

    @task(2)  # Higher weight
    def check_metrics(self):
        self.client.get("/health/pulse")

# Run: locust -f tests/test_performance.py --host http://localhost:8000
```

**Priority:** P2 - Important for production readiness

---

#### 6.2 **Add Property-Based Testing**
**Impact:** Find edge cases automatically

**Suggestion:**
```python
# tests/test_properties.py
from hypothesis import given, strategies as st

@given(
    status_code=st.integers(min_value=100, max_value=599),
    duration_ms=st.floats(min_value=0.1, max_value=10000.0),
    endpoint=st.text(min_size=1, max_size=100)
)
def test_metrics_handles_all_inputs(status_code, duration_ms, endpoint):
    """Metrics should never crash regardless of input."""
    metrics = PulseMetrics()

    # Should not raise any exception
    metrics.record_request(
        endpoint=endpoint,
        method="GET",
        status_code=status_code,
        duration_ms=duration_ms
    )

    result = metrics.get_metrics()
    assert isinstance(result, dict)
```

**Priority:** P3 - Quality improvement

---

#### 6.3 **Add Chaos Engineering Tests**
**Impact:** Verify resilience under failures

**Suggestion:**
```python
# tests/test_chaos.py
async def test_middleware_survives_metrics_failure(test_app):
    """Middleware should not crash if metrics collector fails."""

    # Inject failure into metrics
    original_record = test_app.state.pulse.record_request
    def failing_record(*args, **kwargs):
        raise RuntimeError("Simulated metrics failure")

    test_app.state.pulse.record_request = failing_record

    # Request should still succeed
    client = TestClient(test_app)
    response = client.get("/test/success")
    assert response.status_code == 200

    # Restore
    test_app.state.pulse.record_request = original_record
```

**Priority:** P2 - Important for reliability

---

### 7. Documentation Improvements

#### 7.1 **Add Architecture Decision Records (ADRs)**
**Impact:** Document design choices for future maintainers

**Suggestion:**
```markdown
# docs/adr/0001-use-tdigest-for-percentiles.md

## Status: Accepted

## Context
We need to calculate P95/P99 latency percentiles efficiently with bounded memory.

## Decision
Use TDigest algorithm for streaming percentile estimation.

## Consequences
**Positive:**
- O(1) space complexity
- Accurate percentiles (error < 1%)
- No sorting required

**Negative:**
- Approximate, not exact
- Additional dependency
- Learning curve for contributors
```

**Priority:** P3 - Long-term maintainability

---

#### 7.2 **Add API Documentation**
**Impact:** Better developer experience

**Suggestion:**
```python
# Add OpenAPI metadata
@router.get(
    "/pulse/endpoints",
    summary="List All Endpoints",
    description="""
    Returns all discovered API endpoints with their metrics and probe status.

    **Use Cases:**
    - Dashboard data source
    - CI/CD health checks
    - Automated testing discovery

    **Response includes:**
    - Endpoint metadata (method, path, tags)
    - Performance metrics (latency, error rate)
    - Last probe result
    - Auto-generated payload samples
    """,
    response_model=EndpointListResponse,
    tags=["Monitoring"]
)
def list_endpoints(request: Request):
    # ...
```

**Priority:** P3 - Developer experience

---

### 8. Observability Enhancements

#### 8.1 **Add Structured Logging**
**Impact:** Better log parsing and alerting

**Suggestion:**
```python
import structlog

logger = structlog.get_logger(__name__)

# In middleware.py
logger.warning(
    "performance_alert",
    alert_type="slow_request",
    method=method,
    path=path,
    status_code=status_code,
    duration_ms=duration_ms,
    correlation_id=correlation_id,
    threshold_ms=SLOW_REQUEST_THRESHOLD_MS
)
```

**Priority:** P2 - Production observability

---

#### 8.2 **Add Distributed Tracing Support**
**Impact:** Debug microservices issues

**Suggestion:**
```python
from opentelemetry import trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer(__name__)

async def _probe_endpoint(self, job, client, endpoint):
    with tracer.start_as_current_span(
        f"probe.{endpoint.method}.{endpoint.path}",
        kind=SpanKind.CLIENT
    ) as span:
        span.set_attribute("endpoint.id", endpoint.id)
        span.set_attribute("endpoint.method", endpoint.method)

        # Existing probe logic
        # ...

        span.set_attribute("probe.status", result.status)
        span.set_attribute("probe.latency_ms", result.latency_ms)
```

**Priority:** P3 - Advanced observability

---

### 9. Developer Experience

#### 9.1 **Add Pre-commit Hooks**
**Impact:** Catch issues before commit

**Suggestion:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=100]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

**Priority:** P2 - Code quality

---

#### 9.2 **Add Docker Compose for Development**
**Impact:** Easier local testing

**Suggestion:**
```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    environment:
      - PULSE_ALLOWED_ORIGINS=http://localhost:3000
    command: uvicorn test_app:app --host 0.0.0.0 --reload

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

**Priority:** P3 - Developer experience

---

### 10. CI/CD Improvements

#### 10.1 **Add Security Scanning**
**Impact:** Catch vulnerabilities early

**Suggestion:**
```yaml
# .github/workflows/security.yml
name: Security Scan

on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Bandit
        run: |
          pip install bandit
          bandit -r src/ -f json -o bandit-report.json

      - name: Run Safety
        run: |
          pip install safety
          safety check --json

      - name: Run Snyk
        uses: snyk/actions/python@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
```

**Priority:** P1 - Security

---

#### 10.2 **Add Benchmarking in CI**
**Impact:** Catch performance regressions

**Suggestion:**
```yaml
# .github/workflows/benchmark.yml
name: Performance Benchmarks

on: [pull_request]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run benchmarks
        run: |
          pip install pytest-benchmark
          pytest tests/benchmarks/ --benchmark-json=output.json

      - name: Compare with main
        run: |
          # Download baseline from main branch
          # Compare and fail if regression > 10%
          python scripts/compare_benchmarks.py
```

**Priority:** P2 - Performance assurance

---

## Summary of Priorities

### P0 (Critical - Fix Immediately)
1. CORS security vulnerability (`__init__.py:69`)
2. Payload storage without sanitization (`payload_store.py`)
3. Unbounded memory growth in metrics (`metrics.py:136`)

### P1 (High - Fix Before Production)
4. No rate limiting on probe endpoints (`router.py:231`)
5. Probe manager lacks concurrent job limit (`probe.py:92`)
6. No timeout on probe jobs (`probe.py:133`)
7. Missing error recovery in middleware (`middleware.py:110`)
8. Synchronous file I/O in request path (`payload_store.py:32`)
9. Add security scanning to CI

### P2 (Medium - Important Improvements)
10. Lock contention in metrics collection (`metrics.py:159`)
11. Add Prometheus/OpenTelemetry export
12. Add health check levels (liveness/readiness)
13. Add load testing
14. Add chaos engineering tests
15. Add structured logging
16. Add pre-commit hooks
17. Add benchmarking in CI

### P3 (Low - Nice to Have)
18. Missing type hints (various files)
19. Inconsistent error messages
20. Add metrics persistence
21. Add property-based testing
22. Add Architecture Decision Records
23. Add Docker Compose for development
24. Add distributed tracing support

---

## Positive Highlights

1. **Excellent Test Coverage:** 90%+ with comprehensive integration tests
2. **Thread-Safety:** Proper locking throughout
3. **Production-Ready Metrics:** TDigest for accurate percentiles
4. **Clean Architecture:** Well-separated concerns
5. **Great Documentation:** Clear README and inline docs
6. **Professional CI/CD:** Multi-version testing, codecov integration
7. **Smart Path Normalization:** Groups similar endpoints correctly
8. **Async-First Design:** Proper use of asyncio patterns

---

## Recommended Next Steps

1. **Week 1:** Fix P0 security issues (CORS, payload validation, memory bounds)
2. **Week 2:** Add rate limiting, job limits, timeouts (P1 reliability)
3. **Week 3:** Add Prometheus export and health checks (P2 observability)
4. **Week 4:** Add security scanning and benchmarking to CI (P1/P2 quality)
5. **Month 2:** Address remaining P2/P3 items based on user feedback

---

**End of Review**
