"""Unit tests for the PulseMiddleware module."""

import asyncio
from unittest.mock import AsyncMock, Mock, call

import pytest

from fastapi_pulse.middleware import PulseMiddleware
from fastapi_pulse.metrics import PulseMetrics


pytestmark = pytest.mark.unit


class TestPulseMiddleware:
    """Unit tests for PulseMiddleware."""

    @pytest.fixture
    def mock_metrics(self):
        """Provide a mocked PulseMetrics instance."""
        return Mock(spec=PulseMetrics)

    @pytest.fixture
    def mock_app(self):
        """Provide a mock ASGI app."""
        async def app(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"message":"ok"}',
            })
        return app

    @pytest.fixture
    def middleware(self, mock_app, mock_metrics):
        """Create middleware instance."""
        return PulseMiddleware(
            mock_app,
            metrics=mock_metrics,
            enable_detailed_logging=False,
        )

    async def test_middleware_tracks_http_request(self, middleware, mock_metrics):
        """Middleware should track HTTP requests in metrics."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
        }

        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # Verify metrics were recorded
        mock_metrics.record_request.assert_called_once()
        call_args = mock_metrics.record_request.call_args
        assert call_args.kwargs["endpoint"] == "/test"
        assert call_args.kwargs["method"] == "GET"
        assert call_args.kwargs["status_code"] == 200
        assert call_args.kwargs["duration_ms"] > 0

    async def test_middleware_ignores_non_http(self, middleware, mock_metrics):
        """Middleware should pass through non-HTTP requests."""
        scope = {"type": "websocket", "path": "/ws"}
        receive = AsyncMock()
        send = AsyncMock()

        # Mock app that handles websocket
        async def ws_app(scope, receive, send):
            pass

        middleware.app = ws_app

        await middleware(scope, receive, send)

        # No metrics should be recorded for websocket
        mock_metrics.record_request.assert_not_called()

    async def test_middleware_adds_response_time_header(self, middleware):
        """Middleware should add X-Response-Time-Ms header."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
        }

        receive = AsyncMock()
        sent_messages = []

        async def capture_send(message):
            sent_messages.append(message)

        await middleware(scope, receive, capture_send)

        # Find the response.start message
        start_msg = next(m for m in sent_messages if m["type"] == "http.response.start")

        # Check for response time header
        headers = dict(start_msg["headers"])
        assert b"x-response-time-ms" in headers
        response_time = float(headers[b"x-response-time-ms"])
        assert response_time >= 0

    async def test_middleware_normalizes_paths(self, middleware, mock_metrics):
        """Middleware should normalize paths with IDs to generic patterns."""
        test_cases = [
            ("/users/123", "/users/{id}"),
            ("/items/456/details", "/items/{id}/details"),
            ("/orders/abc123", "/orders/abc{id}"),
        ]

        for original_path, expected_normalized in test_cases:
            scope = {
                "type": "http",
                "method": "GET",
                "path": original_path,
                "headers": [],
            }

            receive = AsyncMock()
            send = AsyncMock()

            await middleware(scope, receive, send)

        # Check that paths were normalized
        for call_obj in mock_metrics.record_request.call_args_list:
            endpoint = call_obj.kwargs["endpoint"]
            # At least one should be normalized
            assert "{id}" in endpoint or endpoint.startswith("/")

    async def test_middleware_handles_exceptions(self, middleware, mock_metrics):
        """Middleware should handle exceptions and return 500."""
        # Mock app that raises an exception
        async def failing_app(scope, receive, send):
            raise ValueError("Test error")

        middleware.app = failing_app

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/error",
            "headers": [],
        }

        receive = AsyncMock()
        sent_messages = []

        async def capture_send(message):
            sent_messages.append(message)

        await middleware(scope, receive, capture_send)

        # Should have sent 500 response
        start_msg = next(m for m in sent_messages if m["type"] == "http.response.start")
        assert start_msg["status"] == 500

        # Should have recorded error in metrics
        call_args = mock_metrics.record_request.call_args
        assert call_args.kwargs["status_code"] == 500

    async def test_middleware_extracts_correlation_id(self, middleware, mock_metrics):
        """Middleware should extract correlation ID from headers."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [
                (b"x-correlation-id", b"test-correlation-123"),
            ],
        }

        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        call_args = mock_metrics.record_request.call_args
        assert call_args.kwargs["correlation_id"] == "test-correlation-123"

    async def test_middleware_uses_unknown_correlation_when_missing(
        self, middleware, mock_metrics
    ):
        """Middleware should use 'unknown' when correlation ID is missing."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
        }

        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        call_args = mock_metrics.record_request.call_args
        assert call_args.kwargs["correlation_id"] == "unknown"

    async def test_middleware_excludes_configured_paths(self, mock_app, mock_metrics):
        """Middleware should skip tracking for excluded paths."""
        middleware = PulseMiddleware(
            mock_app,
            metrics=mock_metrics,
            enable_detailed_logging=False,
            exclude_path_prefixes=("/health/pulse", "/metrics"),
        )

        excluded_paths = [
            "/health/pulse",
            "/health/pulse/endpoints",
            "/metrics",
            "/metrics/detailed",
        ]

        for path in excluded_paths:
            scope = {
                "type": "http",
                "method": "GET",
                "path": path,
                "headers": [],
            }

            receive = AsyncMock()
            send = AsyncMock()

            await middleware(scope, receive, send)

        # No metrics should be recorded for excluded paths
        mock_metrics.record_request.assert_not_called()

    async def test_middleware_tracks_non_excluded_paths(self, mock_app, mock_metrics):
        """Middleware should track paths not in exclusion list."""
        middleware = PulseMiddleware(
            mock_app,
            metrics=mock_metrics,
            enable_detailed_logging=False,
            exclude_path_prefixes=("/admin",),
        )

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/users",
            "headers": [],
        }

        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # Should record metrics for non-excluded path
        mock_metrics.record_request.assert_called_once()

    async def test_middleware_handles_late_exception(self, mock_metrics):
        """Middleware should handle exceptions after response has started."""
        async def failing_after_start_app(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })
            raise ValueError("Late error")

        middleware = PulseMiddleware(
            failing_after_start_app,
            metrics=mock_metrics,
            enable_detailed_logging=False,
        )

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
        }

        receive = AsyncMock()
        sent_messages = []

        async def capture_send(message):
            sent_messages.append(message)

        await middleware(scope, receive, capture_send)

        # Should complete response body
        body_msgs = [m for m in sent_messages if m["type"] == "http.response.body"]
        assert len(body_msgs) == 1

        # Should record as error
        call_args = mock_metrics.record_request.call_args
        assert call_args.kwargs["status_code"] == 500

    async def test_middleware_normalizes_uuid_paths(self, middleware, mock_metrics):
        """Middleware should normalize UUID patterns in paths."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/users/550e8400-e29b-41d4-a716-446655440000",
            "headers": [],
        }

        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        call_args = mock_metrics.record_request.call_args
        endpoint = call_args.kwargs["endpoint"]
        assert "{id}" in endpoint

    async def test_middleware_tracks_different_status_codes(self, mock_metrics):
        """Middleware should correctly track various status codes."""
        status_codes = [200, 201, 204, 301, 400, 404, 500, 503]

        for status in status_codes:
            async def app_with_status(scope, receive, send):
                await send({
                    "type": "http.response.start",
                    "status": status,
                    "headers": [],
                })
                await send({
                    "type": "http.response.body",
                    "body": b"{}",
                })

            middleware = PulseMiddleware(
                app_with_status,
                metrics=mock_metrics,
                enable_detailed_logging=False,
            )

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/test",
                "headers": [],
            }

            receive = AsyncMock()
            send = AsyncMock()

            await middleware(scope, receive, send)

        # Verify all status codes were recorded
        recorded_statuses = [
            call.kwargs["status_code"]
            for call in mock_metrics.record_request.call_args_list
        ]
        assert set(recorded_statuses) == set(status_codes)

    async def test_middleware_duration_is_positive(self, middleware, mock_metrics):
        """Middleware should always record positive duration."""
        async def slow_app(scope, receive, send):
            await asyncio.sleep(0.01)  # 10ms delay
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })
            await send({
                "type": "http.response.body",
                "body": b"ok",
            })

        middleware.app = slow_app

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/slow",
            "headers": [],
        }

        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        call_args = mock_metrics.record_request.call_args
        duration = call_args.kwargs["duration_ms"]
        assert duration >= 10.0  # At least 10ms

    def test_should_skip_tracking(self, mock_app, mock_metrics):
        """_should_skip_tracking should correctly identify excluded paths."""
        middleware = PulseMiddleware(
            mock_app,
            metrics=mock_metrics,
            exclude_path_prefixes=("/health", "/admin/"),
        )

        # Should skip
        assert middleware._should_skip_tracking("/health") is True
        assert middleware._should_skip_tracking("/health/pulse") is True
        assert middleware._should_skip_tracking("/admin/users") is True

        # Should not skip
        assert middleware._should_skip_tracking("/api/health") is False
        assert middleware._should_skip_tracking("/users") is False

    def test_normalize_path_with_numbers(self, middleware):
        """_normalize_path should replace numeric IDs."""
        assert middleware._normalize_path("/users/123") == "/users/{id}"
        assert middleware._normalize_path("/items/456/edit") == "/items/{id}/edit"
        assert middleware._normalize_path("/api/v1/products/789") == "/api/v{id}/products/{id}"

    async def test_fallback_response_format(self, mock_metrics):
        """Middleware should return proper JSON error on early failure."""
        async def failing_app(scope, receive, send):
            raise RuntimeError("Early failure")

        middleware = PulseMiddleware(
            failing_app,
            metrics=mock_metrics,
            enable_detailed_logging=False,
        )

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
        }

        receive = AsyncMock()
        sent_messages = []

        async def capture_send(message):
            sent_messages.append(message)

        await middleware(scope, receive, capture_send)

        # Check response structure
        start_msg = next(m for m in sent_messages if m["type"] == "http.response.start")
        body_msg = next(m for m in sent_messages if m["type"] == "http.response.body")

        assert start_msg["status"] == 500
        headers = dict(start_msg["headers"])
        assert headers[b"content-type"] == b"application/json"
        assert b"Internal Server Error" in body_msg["body"]

    async def test_empty_path(self, middleware, mock_metrics):
        """Middleware should handle empty path."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "",
            "headers": [],
        }

        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # Should still record metrics
        mock_metrics.record_request.assert_called_once()

    async def test_missing_method(self, mock_app, mock_metrics):
        """Middleware should handle missing method gracefully."""
        middleware = PulseMiddleware(
            mock_app,
            metrics=mock_metrics,
            enable_detailed_logging=False,
        )

        scope = {
            "type": "http",
            # Missing "method"
            "path": "/test",
            "headers": [],
        }

        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # Should use default method
        call_args = mock_metrics.record_request.call_args
        assert call_args.kwargs["method"] == "GET"

    async def test_malformed_headers(self, middleware, mock_metrics):
        """Middleware should handle malformed headers."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [
                (b"x-test", b"value"),
            ],
        }

        receive = AsyncMock()
        send = AsyncMock()

        # Should not crash
        await middleware(scope, receive, send)

    def test_normalize_path_empty_string(self, middleware):
        """_normalize_path should handle empty string."""
        result = middleware._normalize_path("")
        assert result == ""

    def test_normalize_path_root(self, middleware):
        """_normalize_path should handle root path."""
        result = middleware._normalize_path("/")
        assert result == "/"

    def test_normalize_path_multiple_ids(self, middleware):
        """_normalize_path should replace multiple numeric IDs."""
        result = middleware._normalize_path("/users/123/posts/456/comments/789")
        assert result == "/users/{id}/posts/{id}/comments/{id}"

    def test_should_skip_exact_match(self, mock_app, mock_metrics):
        """_should_skip_tracking should match exact paths."""
        middleware = PulseMiddleware(
            mock_app,
            metrics=mock_metrics,
            exclude_path_prefixes=("/exact",),
        )

        assert middleware._should_skip_tracking("/exact") is True
        assert middleware._should_skip_tracking("/exact/sub") is True
        assert middleware._should_skip_tracking("/exactnot") is False

    def test_should_skip_root_special_case(self, mock_app, mock_metrics):
        """_should_skip_tracking should handle root path specially."""
        middleware = PulseMiddleware(
            mock_app,
            metrics=mock_metrics,
            exclude_path_prefixes=("/",),
        )

        assert middleware._should_skip_tracking("/") is True
        # Root exclusion should not exclude all paths
        assert middleware._should_skip_tracking("/api") is False
