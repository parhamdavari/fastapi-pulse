"""Property-based tests for FastAPI Pulse using Hypothesis."""

import pytest
from hypothesis import given, strategies as st, assume, settings

from fastapi_pulse.metrics import PulseMetrics, RollingWindowDigest


pytestmark = pytest.mark.property


# Strategies for generating test data

@st.composite
def valid_duration_ms(draw):
    """Generate valid duration in milliseconds."""
    return draw(st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False))


@st.composite
def valid_status_code(draw):
    """Generate valid HTTP status codes."""
    return draw(st.integers(min_value=100, max_value=599))


@st.composite
def valid_endpoint_path(draw):
    """Generate valid endpoint paths."""
    segments = draw(st.lists(
        st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Nd')), min_size=1, max_size=10),
        min_size=1,
        max_size=5
    ))
    return "/" + "/".join(segments)


@st.composite
def valid_http_method(draw):
    """Generate valid HTTP methods."""
    return draw(st.sampled_from(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]))


class TestRollingWindowDigestProperties:
    """Property-based tests for RollingWindowDigest."""

    @given(values=st.lists(valid_duration_ms(), min_size=1, max_size=100))
    def test_count_equals_added_values(self, values):
        """Count should always equal the number of added values."""
        digest = RollingWindowDigest(window_seconds=300, bucket_seconds=60)

        for val in values:
            digest.add(val)

        assert digest.count() == len(values)

    @given(values=st.lists(valid_duration_ms(), min_size=1, max_size=100))
    def test_total_equals_sum_of_values(self, values):
        """Total should equal the sum of all added values."""
        digest = RollingWindowDigest(window_seconds=300, bucket_seconds=60)

        for val in values:
            digest.add(val)

        expected_total = sum(values)
        actual_total = digest.total()

        assert abs(actual_total - expected_total) < 0.01

    @given(values=st.lists(valid_duration_ms(), min_size=1, max_size=100))
    def test_mean_is_total_divided_by_count(self, values):
        """Mean should equal total divided by count."""
        digest = RollingWindowDigest(window_seconds=300, bucket_seconds=60)

        for val in values:
            digest.add(val)

        expected_mean = sum(values) / len(values)
        actual_mean = digest.mean()

        assert abs(actual_mean - expected_mean) < 0.01

    @given(
        values=st.lists(valid_duration_ms(), min_size=2, max_size=50),
        percentile=st.floats(min_value=0.0, max_value=100.0)
    )
    @settings(max_examples=50)
    def test_percentile_within_data_range(self, values, percentile):
        """Percentile should be within the range of input values."""
        digest = RollingWindowDigest(window_seconds=300, bucket_seconds=60)

        for val in values:
            digest.add(val)

        result = digest.percentile(percentile)

        if result is not None:
            min_val = min(values)
            max_val = max(values)
            assert min_val <= result <= max_val

    @given(value=valid_duration_ms())
    def test_single_value_no_percentile(self, value):
        """Single value should not allow percentile calculation."""
        digest = RollingWindowDigest(window_seconds=300, bucket_seconds=60)
        digest.add(value)

        assert digest.percentile(95) is None

    @given(values=st.lists(valid_duration_ms(), min_size=1, max_size=100))
    def test_adding_zero_count_remains_correct(self, values):
        """Adding values should maintain correct count."""
        digest = RollingWindowDigest(window_seconds=300, bucket_seconds=60)

        cumulative_count = 0
        for val in values:
            digest.add(val)
            cumulative_count += 1
            assert digest.count() == cumulative_count


class TestPulseMetricsProperties:
    """Property-based tests for PulseMetrics."""

    @given(
        endpoint=valid_endpoint_path(),
        method=valid_http_method(),
        status_code=valid_status_code(),
        duration=valid_duration_ms(),
    )
    @settings(max_examples=100)
    def test_record_request_always_increments_total(
        self, endpoint, method, status_code, duration
    ):
        """Recording a request should always increment total count."""
        metrics = PulseMetrics()
        initial = metrics.get_metrics()["summary"]["total_requests"]

        metrics.record_request(endpoint, method, status_code, duration)

        final = metrics.get_metrics()["summary"]["total_requests"]
        assert final == initial + 1

    @given(
        endpoint=valid_endpoint_path(),
        method=valid_http_method(),
        status_code=st.integers(min_value=400, max_value=599),
        duration=valid_duration_ms(),
    )
    @settings(max_examples=50)
    def test_error_status_increments_error_count(
        self, endpoint, method, status_code, duration
    ):
        """Status codes >= 400 should increment error count."""
        metrics = PulseMetrics()
        initial = metrics.get_metrics()["summary"]["total_errors"]

        metrics.record_request(endpoint, method, status_code, duration)

        final = metrics.get_metrics()["summary"]["total_errors"]
        assert final == initial + 1

    @given(
        endpoint=valid_endpoint_path(),
        method=valid_http_method(),
        status_code=st.integers(min_value=200, max_value=399),
        duration=valid_duration_ms(),
    )
    @settings(max_examples=50)
    def test_success_status_does_not_increment_error_count(
        self, endpoint, method, status_code, duration
    ):
        """Status codes < 400 should not increment error count."""
        metrics = PulseMetrics()
        initial = metrics.get_metrics()["summary"]["total_errors"]

        metrics.record_request(endpoint, method, status_code, duration)

        final = metrics.get_metrics()["summary"]["total_errors"]
        assert final == initial

    @given(
        requests=st.lists(
            st.tuples(
                valid_endpoint_path(),
                valid_http_method(),
                valid_status_code(),
                valid_duration_ms(),
            ),
            min_size=1,
            max_size=50,
        )
    )
    @settings(max_examples=50)
    def test_total_requests_equals_recorded_count(self, requests):
        """Total requests should equal the number of recorded requests."""
        metrics = PulseMetrics()

        for endpoint, method, status_code, duration in requests:
            metrics.record_request(endpoint, method, status_code, duration)

        result = metrics.get_metrics()
        assert result["summary"]["total_requests"] == len(requests)

    @given(
        endpoint=valid_endpoint_path(),
        method=valid_http_method(),
        durations=st.lists(valid_duration_ms(), min_size=2, max_size=20),
    )
    @settings(max_examples=50)
    def test_avg_response_time_is_mean_of_durations(
        self, endpoint, method, durations
    ):
        """Average response time should be mean of recorded durations."""
        metrics = PulseMetrics()

        for duration in durations:
            metrics.record_request(endpoint, method, 200, duration)

        result = metrics.get_metrics()
        endpoint_key = f"{method} {endpoint}"
        avg = result["endpoint_metrics"][endpoint_key]["avg_response_time"]

        expected_avg = sum(durations) / len(durations)
        assert abs(avg - expected_avg) < 1.0

    @given(
        endpoint=valid_endpoint_path(),
        method=valid_http_method(),
        success_count=st.integers(min_value=0, max_value=20),
        error_count=st.integers(min_value=0, max_value=20),
    )
    @settings(max_examples=50)
    def test_error_rate_calculation(
        self, endpoint, method, success_count, error_count
    ):
        """Error rate should be (errors / total) * 100."""
        assume(success_count + error_count > 0)

        metrics = PulseMetrics()

        for _ in range(success_count):
            metrics.record_request(endpoint, method, 200, 50.0)

        for _ in range(error_count):
            metrics.record_request(endpoint, method, 500, 50.0)

        result = metrics.get_metrics()
        error_rate = result["summary"]["error_rate"]

        total = success_count + error_count
        expected_rate = (error_count / total) * 100

        assert abs(error_rate - expected_rate) < 0.01

    @given(
        endpoint=valid_endpoint_path(),
        method=valid_http_method(),
        requests=st.lists(
            st.tuples(valid_status_code(), valid_duration_ms()),
            min_size=1,
            max_size=30,
        ),
    )
    @settings(max_examples=30)
    def test_endpoint_total_equals_request_count(
        self, endpoint, method, requests
    ):
        """Endpoint total_requests should equal recorded count."""
        metrics = PulseMetrics()

        for status_code, duration in requests:
            metrics.record_request(endpoint, method, status_code, duration)

        result = metrics.get_metrics()
        endpoint_key = f"{method} {endpoint}"
        total = result["endpoint_metrics"][endpoint_key]["total_requests"]

        assert total == len(requests)


class TestPathNormalizationProperties:
    """Property-based tests for path normalization."""

    @given(
        base_path=st.text(
            alphabet=st.characters(whitelist_categories=('Ll',)),
            min_size=1,
            max_size=10
        ),
        numeric_id=st.integers(min_value=1, max_value=999999),
    )
    @settings(max_examples=50)
    def test_numeric_ids_normalized_consistently(self, base_path, numeric_id):
        """Paths with numeric IDs should normalize consistently."""
        from fastapi_pulse.middleware import PulseMiddleware

        path1 = f"/{base_path}/{numeric_id}"
        path2 = f"/{base_path}/{numeric_id + 1}"

        middleware = PulseMiddleware(
            lambda s, r, snd: None,
            metrics=PulseMetrics(),
        )

        normalized1 = middleware._normalize_path(path1)
        normalized2 = middleware._normalize_path(path2)

        # Both should normalize to same pattern
        assert normalized1 == normalized2
        assert "{id}" in normalized1


class TestPayloadSanitizationProperties:
    """Property-based tests for payload sanitization."""

    @given(
        extra_fields=st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.one_of(st.text(), st.integers(), st.booleans()),
        )
    )
    @settings(max_examples=50)
    def test_sanitize_removes_unknown_fields(self, extra_fields, temp_payload_file):
        """Sanitize should remove fields not in the expected set."""
        from fastapi_pulse.payload_store import PulsePayloadStore

        store = PulsePayloadStore(temp_payload_file)

        payload = {
            "path_params": {},
            "query": {},
            "headers": {},
            "body": None,
            "media_type": None,
            **extra_fields,
        }

        result = store.set("TEST", payload)

        # Only expected fields should remain
        expected_fields = {"path_params", "query", "headers", "body", "media_type"}
        assert set(result.keys()) == expected_fields

    @given(
        path_params=st.dictionaries(st.text(min_size=1), st.text()),
        query=st.dictionaries(st.text(min_size=1), st.one_of(st.text(), st.integers())),
    )
    @settings(max_examples=50)
    def test_sanitize_preserves_valid_fields(
        self, path_params, query, temp_payload_file
    ):
        """Sanitize should preserve all valid fields."""
        from fastapi_pulse.payload_store import PulsePayloadStore

        store = PulsePayloadStore(temp_payload_file)

        payload = {
            "path_params": path_params,
            "query": query,
            "headers": {},
            "body": None,
            "media_type": None,
        }

        result = store.set("TEST", payload)

        assert result["path_params"] == path_params
        assert result["query"] == query

@st.composite
def edge_case_endpoint_path(draw):
    """Generate edge case endpoint paths."""
    return draw(st.one_of(
        st.just(""),  # Empty
        st.just("/"),  # Root
        st.just("/" * 100),  # Many slashes
        st.text(min_size=0, max_size=1000),  # Very long
        st.text(alphabet=st.characters(
            blacklist_categories=('Cs',),  # No surrogates
            blacklist_characters='\x00'  # No null bytes
        ), min_size=0, max_size=100),  # Unicode
    ))


class TestEdgeCaseProperties:
    """Property-based tests for edge cases."""

    @given(
        endpoint=edge_case_endpoint_path(),
        method=valid_http_method(),
        status_code=valid_status_code(),
        duration=valid_duration_ms(),
    )
    @settings(max_examples=50)
    def test_metrics_handles_edge_case_paths(
        self, endpoint, method, status_code, duration
    ):
        """Metrics should handle edge case paths without crashing."""
        metrics = PulseMetrics()

        # Should not raise
        metrics.record_request(endpoint, method, status_code, duration)

        result = metrics.get_metrics()
        assert result["summary"]["total_requests"] == 1

    @given(
        values=st.lists(valid_duration_ms(), min_size=0, max_size=10),
    )
    @settings(max_examples=30)
    def test_rolling_digest_handles_empty_list(self, values):
        """RollingWindowDigest should handle empty value lists."""
        digest = RollingWindowDigest(window_seconds=300, bucket_seconds=60)

        for val in values:
            digest.add(val)

        # Should not crash
        count = digest.count()
        total = digest.total()
        mean = digest.mean()

        assert count == len(values)
        if values:
            assert total > 0 or all(v == 0 for v in values)
        else:
            assert total == 0.0
            assert mean == 0.0

    @given(
        endpoint=st.text(min_size=0, max_size=200),
        method=st.text(alphabet=st.characters(whitelist_categories=('Lu',)), min_size=1, max_size=10),
        count=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=30)
    def test_repeated_requests_accumulate(self, endpoint, method, count):
        """Repeated identical requests should accumulate correctly."""
        metrics = PulseMetrics()

        for _ in range(count):
            metrics.record_request(endpoint, method, 200, 50.0)

        result = metrics.get_metrics()
        assert result["summary"]["total_requests"] == count
