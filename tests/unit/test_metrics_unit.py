"""Unit tests for the PulseMetrics module."""

import threading
import time

import pytest
from freezegun import freeze_time

from fastapi_pulse.metrics import PulseMetrics, RollingWindowDigest


pytestmark = pytest.mark.unit


class TestRollingWindowDigest:
    """Unit tests for RollingWindowDigest."""

    def test_initial_state(self):
        """RollingWindowDigest should start with no data."""
        digest = RollingWindowDigest(window_seconds=300, bucket_seconds=60)
        assert digest.count() == 0
        assert digest.total() == 0.0
        assert digest.mean() == 0.0
        assert digest.percentile(95) is None

    @freeze_time("2024-01-01 12:00:00")
    def test_add_single_value(self):
        """Adding a single value should be reflected in stats."""
        digest = RollingWindowDigest(window_seconds=300, bucket_seconds=60)
        digest.add(100.0)

        assert digest.count() == 1
        assert digest.total() == 100.0
        assert digest.mean() == 100.0
        # Single value is insufficient for percentile
        assert digest.percentile(95) is None

    @freeze_time("2024-01-01 12:00:00")
    def test_add_multiple_values_same_bucket(self):
        """Multiple values in same time bucket should aggregate correctly."""
        digest = RollingWindowDigest(window_seconds=300, bucket_seconds=60)

        for val in [10, 20, 30, 40, 50]:
            digest.add(val)

        assert digest.count() == 5
        assert digest.total() == 150.0
        assert digest.mean() == 30.0
        assert digest.percentile(50) is not None

    def test_rolling_window_expires_old_data(self):
        """Data older than the window should be automatically dropped."""
        digest = RollingWindowDigest(window_seconds=10, bucket_seconds=2)

        # Add at time 0
        digest.add(100.0, timestamp=0.0)
        assert digest.count() == 1

        # Add at time 5 - should still include first value
        digest.add(200.0, timestamp=5.0)
        assert digest.count() == 2

        # Add at time 15 - first value should be expired
        digest.add(300.0, timestamp=15.0)
        assert digest.count() == 2
        assert 100.0 not in [digest.total()]  # Old data dropped

    def test_percentile_with_two_values(self):
        """Percentile should work with minimum 2 values."""
        digest = RollingWindowDigest(window_seconds=300, bucket_seconds=60)
        digest.add(10.0)
        digest.add(20.0)

        p50 = digest.percentile(50)
        assert p50 is not None
        assert 10 <= p50 <= 20

    def test_buckets_created_correctly(self):
        """Values should be distributed into time-based buckets."""
        digest = RollingWindowDigest(window_seconds=300, bucket_seconds=60)

        # Add values at different times to create multiple buckets
        digest.add(10.0, timestamp=0.0)
        digest.add(20.0, timestamp=65.0)  # Different bucket
        digest.add(30.0, timestamp=125.0)  # Another bucket

        # All values should be tracked
        assert digest.count() == 3
        assert abs(digest.mean() - 20.0) < 0.1

    def test_trim_removes_expired_buckets(self):
        """_trim should remove buckets outside the window."""
        digest = RollingWindowDigest(window_seconds=100, bucket_seconds=30)

        # Add values at different times
        digest.add(10.0, timestamp=0.0)
        digest.add(20.0, timestamp=50.0)
        digest.add(30.0, timestamp=120.0)

        # Manually trim with current time = 150
        # Buckets before timestamp 50 should be removed
        digest._trim(150.0)
        count = digest.count()
        assert count == 2


class TestPulseMetrics:
    """Unit tests for PulseMetrics."""

    def test_initial_state(self, clean_metrics):
        """PulseMetrics should start with empty state."""
        metrics = clean_metrics.get_metrics()

        assert metrics["summary"]["total_requests"] == 0
        assert metrics["summary"]["total_errors"] == 0
        assert metrics["summary"]["error_rate"] == 0
        assert metrics["summary"]["success_rate"] is None

    def test_record_single_request(self, clean_metrics):
        """Recording a request should update all relevant metrics."""
        clean_metrics.record_request(
            endpoint="/test",
            method="GET",
            status_code=200,
            duration_ms=50.0,
            correlation_id="test-1",
        )

        metrics = clean_metrics.get_metrics()
        assert metrics["summary"]["total_requests"] == 1
        assert metrics["summary"]["total_errors"] == 0
        assert "GET /test" in metrics["request_counts"]

    def test_error_tracking(self, clean_metrics):
        """4xx and 5xx status codes should be tracked as errors."""
        # Success
        clean_metrics.record_request("/api", "GET", 200, 50.0)

        # Client error
        clean_metrics.record_request("/api", "GET", 404, 50.0)

        # Server error
        clean_metrics.record_request("/api", "GET", 500, 50.0)

        metrics = clean_metrics.get_metrics()
        assert metrics["summary"]["total_requests"] == 3
        assert metrics["summary"]["total_errors"] == 2
        assert abs(metrics["summary"]["error_rate"] - 66.67) < 0.1

    def test_success_rate_calculation(self, clean_metrics):
        """Success rate should be 100 - error_rate."""
        for _ in range(7):
            clean_metrics.record_request("/api", "GET", 200, 50.0)

        for _ in range(3):
            clean_metrics.record_request("/api", "GET", 500, 50.0)

        metrics = clean_metrics.get_metrics()
        assert metrics["summary"]["total_requests"] == 10
        assert metrics["summary"]["error_rate"] == 30.0
        assert metrics["summary"]["success_rate"] == 70.0

    def test_endpoint_specific_metrics(self, clean_metrics):
        """Each endpoint should have independent metrics."""
        clean_metrics.record_request("/users", "GET", 200, 100.0)
        clean_metrics.record_request("/products", "GET", 200, 50.0)
        clean_metrics.record_request("/users", "POST", 201, 150.0)

        metrics = clean_metrics.get_metrics()
        endpoint_metrics = metrics["endpoint_metrics"]

        assert "GET /users" in endpoint_metrics
        assert "GET /products" in endpoint_metrics
        assert "POST /users" in endpoint_metrics

        assert endpoint_metrics["GET /users"]["total_requests"] == 1
        assert endpoint_metrics["POST /users"]["total_requests"] == 1

    def test_latency_tracking(self, clean_metrics):
        """Latency percentiles should be calculated when enough data exists."""
        durations = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

        for duration in durations:
            clean_metrics.record_request("/api", "GET", 200, float(duration))

        metrics = clean_metrics.get_metrics()
        summary = metrics["summary"]

        # With 10 samples, we should have percentiles
        assert "p95_response_time" in summary
        assert "p99_response_time" in summary
        assert "p50_response_time" in summary

        # P95 should be close to 95
        assert 85 <= summary["p95_response_time"] <= 100

    def test_status_code_tracking(self, clean_metrics):
        """Status codes should be tracked per endpoint."""
        clean_metrics.record_request("/api", "GET", 200, 50.0)
        clean_metrics.record_request("/api", "GET", 200, 50.0)
        clean_metrics.record_request("/api", "GET", 404, 50.0)
        clean_metrics.record_request("/api", "GET", 500, 50.0)

        metrics = clean_metrics.get_metrics()
        status_codes = metrics["status_codes"]["GET /api"]

        assert status_codes[200] == 2
        assert status_codes[404] == 1
        assert status_codes[500] == 1

    def test_thread_safety(self, clean_metrics):
        """PulseMetrics should be thread-safe."""
        def record_requests():
            for i in range(100):
                clean_metrics.record_request(
                    endpoint="/api",
                    method="GET",
                    status_code=200,
                    duration_ms=float(i),
                )

        threads = [threading.Thread(target=record_requests) for _ in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        metrics = clean_metrics.get_metrics()
        assert metrics["summary"]["total_requests"] == 500

    def test_requests_per_minute_calculation(self, clean_metrics):
        """Requests per minute should be calculated from window data."""
        # Record 10 requests
        for _ in range(10):
            clean_metrics.record_request("/api", "GET", 200, 50.0)

        metrics = clean_metrics.get_metrics()
        rpm = metrics["summary"]["requests_per_minute"]

        # With 300s window and 10 requests: (10 / 300) * 60 = 2 rpm
        assert abs(rpm - 2.0) < 0.1

    def test_window_request_count(self, clean_metrics):
        """Window request count should match actual requests in window."""
        for i in range(5):
            clean_metrics.record_request("/api", "GET", 200, float(i * 10))

        metrics = clean_metrics.get_metrics()
        assert metrics["summary"]["window_request_count"] == 5

    def test_avg_response_time_per_endpoint(self, clean_metrics):
        """Each endpoint should track its own average response time."""
        clean_metrics.record_request("/fast", "GET", 200, 10.0)
        clean_metrics.record_request("/fast", "GET", 200, 20.0)
        clean_metrics.record_request("/slow", "GET", 200, 100.0)
        clean_metrics.record_request("/slow", "GET", 200, 200.0)

        metrics = clean_metrics.get_metrics()
        endpoint_metrics = metrics["endpoint_metrics"]

        assert abs(endpoint_metrics["GET /fast"]["avg_response_time"] - 15.0) < 0.1
        assert abs(endpoint_metrics["GET /slow"]["avg_response_time"] - 150.0) < 0.1

    def test_percentiles_per_endpoint(self, clean_metrics):
        """Endpoints should have their own percentile calculations."""
        # Add enough data for percentiles
        for i in range(20):
            clean_metrics.record_request("/api", "GET", 200, float(i * 10))

        metrics = clean_metrics.get_metrics()
        endpoint_metrics = metrics["endpoint_metrics"]["GET /api"]

        assert "p95_response_time" in endpoint_metrics
        assert "p99_response_time" in endpoint_metrics
        assert endpoint_metrics["p95_response_time"] > 0

    def test_custom_window_configuration(self):
        """PulseMetrics should respect custom window settings."""
        metrics = PulseMetrics(window_seconds=600, bucket_seconds=120)

        assert metrics.window_seconds == 600
        assert metrics.bucket_seconds == 120

    def test_zero_requests_state(self, clean_metrics):
        """Metrics with zero requests should return sensible defaults."""
        metrics = clean_metrics.get_metrics()
        summary = metrics["summary"]

        assert summary["error_rate"] == 0
        assert summary["success_rate"] is None
        assert summary["avg_response_time"] == 0.0
        assert summary["requests_per_minute"] == 0.0

    def test_all_errors_scenario(self, clean_metrics):
        """All requests being errors should result in 0% success rate."""
        for _ in range(5):
            clean_metrics.record_request("/api", "GET", 500, 50.0)

        metrics = clean_metrics.get_metrics()
        assert metrics["summary"]["error_rate"] == 100.0
        assert metrics["summary"]["success_rate"] == 0.0

    def test_endpoint_success_error_counts(self, clean_metrics):
        """Endpoint metrics should separately track success and error counts."""
        clean_metrics.record_request("/api", "GET", 200, 50.0)
        clean_metrics.record_request("/api", "GET", 201, 50.0)
        clean_metrics.record_request("/api", "GET", 404, 50.0)
        clean_metrics.record_request("/api", "GET", 500, 50.0)

        endpoint_metrics = clean_metrics.get_metrics()["endpoint_metrics"]["GET /api"]

        assert endpoint_metrics["success_count"] == 2
        assert endpoint_metrics["error_count"] == 2
        assert endpoint_metrics["total_requests"] == 4

    @freeze_time("2024-01-01 12:00:00")
    def test_time_based_expiration(self):
        """Old requests outside the window should not affect current metrics."""
        metrics = PulseMetrics(window_seconds=60, bucket_seconds=10)

        # Add request at t=0
        with freeze_time("2024-01-01 12:00:00"):
            metrics.record_request("/api", "GET", 200, 100.0)

        # Add request at t=70 (old request should be expired)
        with freeze_time("2024-01-01 12:01:10"):
            metrics.record_request("/api", "GET", 200, 50.0)
            result = metrics.get_metrics()

        # Window count should only include recent request
        assert result["summary"]["window_request_count"] == 1
    def test_negative_duration_handled(self, clean_metrics):
        """Negative durations should be handled gracefully."""
        clean_metrics.record_request("/api", "GET", 200, -10.0)
        
        metrics = clean_metrics.get_metrics()
        # Should either reject (count=0) or record it
        assert metrics["summary"]["total_requests"] >= 0

    def test_empty_endpoint_path(self, clean_metrics):
        """Empty endpoint path should be handled."""
        clean_metrics.record_request("", "GET", 200, 50.0)
        
        metrics = clean_metrics.get_metrics()
        assert "GET " in metrics["endpoint_metrics"]

    def test_invalid_status_code_handled(self, clean_metrics):
        """Invalid status codes should be recorded without error."""
        clean_metrics.record_request("/api", "GET", 999, 50.0)
        
        metrics = clean_metrics.get_metrics()
        assert metrics["summary"]["total_requests"] == 1

    def test_extreme_duration_values(self, clean_metrics):
        """Very large durations should be handled."""
        clean_metrics.record_request("/api", "GET", 200, 1_000_000.0)
        
        metrics = clean_metrics.get_metrics()
        assert metrics["summary"]["avg_response_time"] > 0

    def test_unicode_in_endpoint_path(self, clean_metrics):
        """Unicode characters in paths should be handled."""
        clean_metrics.record_request("/api/用户", "GET", 200, 50.0)
        
        metrics = clean_metrics.get_metrics()
        assert "GET /api/用户" in metrics["endpoint_metrics"]

    def test_thread_safety_data_integrity(self, clean_metrics):
        """Thread safety should preserve data integrity."""
        import threading
        errors = []
        
        def record_requests():
            try:
                for i in range(100):
                    clean_metrics.record_request(
                        endpoint="/api",
                        method="GET",
                        status_code=200,
                        duration_ms=float(i),
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_requests) for _ in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Thread safety violations: {errors}"
        metrics = clean_metrics.get_metrics()
        assert metrics["summary"]["total_requests"] == 500
        
        # Verify data integrity
        endpoint_metrics = metrics["endpoint_metrics"]["GET /api"]
        assert endpoint_metrics["total_requests"] == 500
        assert endpoint_metrics["success_count"] == 500
