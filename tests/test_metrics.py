"""
Tests for the core PulseMetrics collector.
"""

import pytest
import numpy as np
from fastapi_pulse.metrics import PulseMetrics, RollingWindowDigest

def test_initial_state():
    """Verify that a new PulseMetrics instance is empty."""
    metrics = PulseMetrics()
    summary = metrics.get_metrics()
    assert summary["summary"]["total_requests"] == 0
    assert "p95_response_time" not in summary["summary"]

@pytest.mark.parametrize(
    "status_code, success_count, error_count",
    [
        (200, 1, 0),  # Standard success
        (204, 1, 0),  # Another success
        (302, 1, 0),  # Redirects are successes
        (404, 0, 1),  # Client error
        (500, 0, 1),  # Server error
    ],
)
def test_record_request_increments_counts(status_code, success_count, error_count):
    """Verify that record_request correctly increments success and error counts."""
    metrics = PulseMetrics()
    metrics.record_request(
        endpoint="/test", method="GET", status_code=status_code, duration_ms=100
    )
    
    endpoint_metrics = metrics.get_metrics()["endpoint_metrics"]["GET /test"]
    
    assert endpoint_metrics["total_requests"] == 1
    assert endpoint_metrics["success_count"] == success_count
    assert endpoint_metrics["error_count"] == error_count

def test_p95_calculation_is_correct():
    """
    Verify the P95 percentile calculation against numpy's implementation
    to ensure mathematical correctness.
    """
    metrics = PulseMetrics()
    durations = list(range(1, 21))  # A simple list [1, 2, 3, ..., 20]

    for d in durations:
        metrics.record_request(endpoint="/", method="GET", status_code=200, duration_ms=d)

    # Calculate the expected value using a trusted library
    expected_p95 = np.percentile(durations, 95, method="linear")

    # Get the calculated value from our implementation
    summary = metrics.get_metrics()["summary"]
    calculated_p95 = summary["p95_response_time"]

    assert calculated_p95 == pytest.approx(expected_p95, rel=0.05)

def test_percentile_with_few_datapoints():
    """Ensure percentile calculation works with minimal data (>= 2 points)."""
    metrics = PulseMetrics()
    durations = [10, 20]

    for d in durations:
        metrics.record_request(endpoint="/", method="GET", status_code=200, duration_ms=d)
    
    expected_p95 = np.percentile(durations, 95, method="linear")
    summary = metrics.get_metrics()["summary"]
    calculated_p95 = summary["p95_response_time"]

    assert "p95_response_time" in summary
    assert calculated_p95 == pytest.approx(expected_p95, rel=0.05)

def test_percentile_with_insufficient_data():
    """Ensure p95 is not calculated for a single data point."""
    metrics = PulseMetrics()
    metrics.record_request(endpoint="/", method="GET", status_code=200, duration_ms=10)
    
    summary = metrics.get_metrics()["summary"]
    assert "p95_response_time" not in summary


def test_rolling_window_total_and_trim(monkeypatch):
    digest = RollingWindowDigest(window_seconds=1, bucket_seconds=1)
    now = 1_000_000.0
    digest.add(5.0, timestamp=now - 5)
    digest.add(10.0, timestamp=now)
    monkeypatch.setattr("fastapi_pulse.metrics.time.time", lambda: now)
    assert digest.total() == 10.0
    assert digest.count() == 1


def test_rolling_window_percentile_handles_sparse_data(monkeypatch):
    class FakeTDigest:
        def __init__(self, *args, **kwargs):
            self.n = 0

        def update(self, value):
            self.n += 1

        def __add__(self, other):
            new = FakeTDigest()
            new.n = 1
            return new

        def percentile(self, _):
            return 42.0

        def compress(self):
            pass

    monkeypatch.setattr("fastapi_pulse.metrics.TDigest", FakeTDigest)
    digest = RollingWindowDigest()
    digest.add(1.0)
    digest.add(2.0)
    assert digest.percentile(95) is None


def test_record_request_enforces_max_endpoints():
    metrics = PulseMetrics(max_endpoints=1)
    metrics.record_request(endpoint="/old", method="GET", status_code=200, duration_ms=5.0)
    metrics.record_request(endpoint="/new", method="GET", status_code=500, duration_ms=5.0)
    stored_keys = metrics.request_counts.keys()
    assert "GET /new" in stored_keys
    assert "GET /old" not in stored_keys
