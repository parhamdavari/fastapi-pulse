"""Unit tests for the router module."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timezone

from fastapi import Request, HTTPException
from fastapi_pulse.router import (
    _get_registry,
    _get_probe_manager,
    _get_payload_store,
    _serialize_probe_result,
    _serialize_endpoint,
)
from fastapi_pulse.probe import ProbeResult
from fastapi_pulse.registry import EndpointInfo


pytestmark = pytest.mark.unit


class TestRouterHelpers:
    """Unit tests for router helper functions."""

    def test_get_registry_raises_when_not_initialized(self):
        """_get_registry should raise RuntimeError when registry is not initialized."""
        request = Mock(spec=Request)
        request.app.state = Mock()
        delattr(request.app.state, 'fastapi_pulse_endpoint_registry')

        with pytest.raises(RuntimeError, match="not initialized"):
            _get_registry(request)

    def test_get_probe_manager_raises_when_not_initialized(self):
        """_get_probe_manager should raise RuntimeError when manager is not initialized."""
        request = Mock(spec=Request)
        request.app.state = Mock()
        delattr(request.app.state, 'fastapi_pulse_probe_manager')

        with pytest.raises(RuntimeError, match="not initialized"):
            _get_probe_manager(request)

    def test_get_payload_store_raises_when_not_initialized(self):
        """_get_payload_store should raise RuntimeError when store is not initialized."""
        request = Mock(spec=Request)
        request.app.state = Mock()
        delattr(request.app.state, 'fastapi_pulse_payload_store')

        with pytest.raises(RuntimeError, match="not initialized"):
            _get_payload_store(request)

    def test_serialize_probe_result_with_none(self):
        """_serialize_probe_result should handle None result."""
        result = _serialize_probe_result(None)

        assert result["status"] == "unknown"
        assert result["status_code"] is None
        assert result["latency_ms"] is None
        assert result["error"] is None
        assert result["checked_at"] is None
        assert result["checked_at_iso"] is None

    def test_serialize_probe_result_with_valid_result(self):
        """_serialize_probe_result should serialize valid ProbeResult."""
        probe_result = ProbeResult(
            endpoint_id="GET /test",
            method="GET",
            path="/test",
            status="healthy",
            status_code=200,
            latency_ms=50.5,
            error=None,
            checked_at=1234567890.0,
            payload={"test": "data"},
        )

        result = _serialize_probe_result(probe_result)

        assert result["status"] == "healthy"
        assert result["status_code"] == 200
        assert result["latency_ms"] == 50.5
        assert result["checked_at"] == 1234567890.0
        assert "checked_at_iso" in result
        assert result["payload"] == {"test": "data"}

    def test_serialize_probe_result_with_error(self):
        """_serialize_probe_result should include error message."""
        probe_result = ProbeResult(
            endpoint_id="GET /error",
            method="GET",
            path="/error",
            status="critical",
            status_code=500,
            error="Connection failed",
            checked_at=1234567890.0,
        )

        result = _serialize_probe_result(probe_result)

        assert result["status"] == "critical"
        assert result["error"] == "Connection failed"

    def test_serialize_probe_result_formats_iso_time(self):
        """_serialize_probe_result should format timestamp as ISO string."""
        timestamp = 1609459200.0  # 2021-01-01 00:00:00 UTC
        probe_result = ProbeResult(
            endpoint_id="GET /test",
            method="GET",
            path="/test",
            status="healthy",
            checked_at=timestamp,
        )

        result = _serialize_probe_result(probe_result)

        assert result["checked_at_iso"] == "2021-01-01T00:00:00+00:00"

    def test_serialize_endpoint_with_no_metrics(self):
        """_serialize_endpoint should handle endpoint with no metrics."""
        endpoint = EndpointInfo(
            id="GET /test",
            method="GET",
            path="/test",
            summary="Test",
            tags=["test"],
            requires_input=False,
            has_path_params=False,
            has_request_body=False,
            path_parameters=[],
            query_parameters=[],
            header_parameters=[],
            request_body_media_type=None,
            request_body_schema=None,
        )

        result = _serialize_endpoint(endpoint, {}, None, {})

        assert result["id"] == "GET /test"
        assert result["method"] == "GET"
        assert result["path"] == "/test"
        assert result["metrics"]["total_requests"] == 0
        assert result["metrics"]["error_rate"] == 0

    def test_serialize_endpoint_with_metrics(self):
        """_serialize_endpoint should include endpoint metrics."""
        endpoint = EndpointInfo(
            id="GET /api",
            method="GET",
            path="/api",
            summary="API",
            tags=[],
            requires_input=False,
            has_path_params=False,
            has_request_body=False,
            path_parameters=[],
            query_parameters=[],
            header_parameters=[],
            request_body_media_type=None,
            request_body_schema=None,
        )

        endpoint_metrics = {
            "GET /api": {
                "total_requests": 100,
                "success_count": 95,
                "error_count": 5,
                "avg_response_time": 125.5,
                "p95_response_time": 200.0,
            }
        }

        result = _serialize_endpoint(endpoint, endpoint_metrics, None, {})

        assert result["metrics"]["total_requests"] == 100
        assert result["metrics"]["success_count"] == 95
        assert result["metrics"]["error_count"] == 5
        assert result["metrics"]["error_rate"] == 5.0
        assert result["metrics"]["avg_response_time"] == 125.5

    def test_serialize_endpoint_calculates_error_rate(self):
        """_serialize_endpoint should calculate error rate correctly."""
        endpoint = EndpointInfo(
            id="GET /api",
            method="GET",
            path="/api",
            summary="API",
            tags=[],
            requires_input=False,
            has_path_params=False,
            has_request_body=False,
            path_parameters=[],
            query_parameters=[],
            header_parameters=[],
            request_body_media_type=None,
            request_body_schema=None,
        )

        endpoint_metrics = {
            "GET /api": {
                "total_requests": 200,
                "error_count": 10,
            }
        }

        result = _serialize_endpoint(endpoint, endpoint_metrics, None, {})

        # 10/200 * 100 = 5%
        assert result["metrics"]["error_rate"] == 5.0

    def test_serialize_endpoint_with_probe_result(self):
        """_serialize_endpoint should include probe result."""
        endpoint = EndpointInfo(
            id="GET /test",
            method="GET",
            path="/test",
            summary="Test",
            tags=[],
            requires_input=False,
            has_path_params=False,
            has_request_body=False,
            path_parameters=[],
            query_parameters=[],
            header_parameters=[],
            request_body_media_type=None,
            request_body_schema=None,
        )

        probe_result = ProbeResult(
            endpoint_id="GET /test",
            method="GET",
            path="/test",
            status="healthy",
            status_code=200,
            latency_ms=50.0,
        )

        result = _serialize_endpoint(endpoint, {}, probe_result, {})

        assert result["last_probe"]["status"] == "healthy"
        assert result["last_probe"]["status_code"] == 200

    def test_serialize_endpoint_with_payload_info(self):
        """_serialize_endpoint should include payload information."""
        endpoint = EndpointInfo(
            id="GET /test",
            method="GET",
            path="/test",
            summary="Test",
            tags=[],
            requires_input=False,
            has_path_params=False,
            has_request_body=False,
            path_parameters=[],
            query_parameters=[],
            header_parameters=[],
            request_body_media_type=None,
            request_body_schema=None,
        )

        payload_info = {
            "source": "custom",
            "effective": {"query": {"test": "value"}},
        }

        result = _serialize_endpoint(endpoint, {}, None, payload_info)

        assert result["payload"]["source"] == "custom"
        assert result["payload"]["effective"]["query"]["test"] == "value"

    def test_serialize_endpoint_includes_all_fields(self):
        """_serialize_endpoint should include all endpoint fields."""
        endpoint = EndpointInfo(
            id="POST /items",
            method="POST",
            path="/items",
            summary="Create Item",
            tags=["items", "catalog"],
            requires_input=True,
            has_path_params=False,
            has_request_body=True,
            path_parameters=[],
            query_parameters=[],
            header_parameters=[],
            request_body_media_type="application/json",
            request_body_schema={"type": "object"},
        )

        result = _serialize_endpoint(endpoint, {}, None, {})

        assert result["id"] == "POST /items"
        assert result["method"] == "POST"
        assert result["path"] == "/items"
        assert result["summary"] == "Create Item"
        assert result["tags"] == ["items", "catalog"]
        assert result["requires_input"] is True


class TestRouterEdgeCases:
    """Unit tests for router edge cases."""

    def test_serialize_endpoint_zero_division_protection(self):
        """_serialize_endpoint should handle zero total requests."""
        endpoint = EndpointInfo(
            id="GET /new",
            method="GET",
            path="/new",
            summary="New",
            tags=[],
            requires_input=False,
            has_path_params=False,
            has_request_body=False,
            path_parameters=[],
            query_parameters=[],
            header_parameters=[],
            request_body_media_type=None,
            request_body_schema=None,
        )

        endpoint_metrics = {
            "GET /new": {
                "total_requests": 0,
                "error_count": 0,
            }
        }

        result = _serialize_endpoint(endpoint, endpoint_metrics, None, {})

        # Should not raise ZeroDivisionError
        assert result["metrics"]["error_rate"] == 0

    def test_serialize_probe_result_with_none_timestamp(self):
        """_serialize_probe_result should handle None timestamp."""
        probe_result = ProbeResult(
            endpoint_id="GET /test",
            method="GET",
            path="/test",
            status="healthy",
            checked_at=None,
        )

        result = _serialize_probe_result(probe_result)

        assert result["checked_at"] is None
        assert result["checked_at_iso"] is None
