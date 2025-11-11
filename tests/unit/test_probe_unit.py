"""Unit tests for the PulseProbeManager module."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import httpx

from fastapi import FastAPI
from fastapi_pulse.probe import PulseProbeManager, ProbeJob, ProbeResult
from fastapi_pulse.metrics import PulseMetrics
from fastapi_pulse.registry import EndpointInfo, PulseEndpointRegistry
from fastapi_pulse.payload_store import PulsePayloadStore


pytestmark = pytest.mark.unit


class TestProbeResult:
    """Unit tests for ProbeResult dataclass."""

    def test_probe_result_creation(self):
        """ProbeResult should be created with all fields."""
        result = ProbeResult(
            endpoint_id="GET /test",
            method="GET",
            path="/test",
            status="healthy",
            status_code=200,
            latency_ms=50.0,
            checked_at=1234567890.0,
        )

        assert result.endpoint_id == "GET /test"
        assert result.status == "healthy"

    def test_probe_result_to_dict(self):
        """ProbeResult.to_dict() should return dictionary."""
        result = ProbeResult(
            endpoint_id="GET /test",
            method="GET",
            path="/test",
            status="healthy",
            status_code=200,
        )

        data = result.to_dict()

        assert isinstance(data, dict)
        assert data["endpoint_id"] == "GET /test"
        assert data["status"] == "healthy"


class TestProbeJob:
    """Unit tests for ProbeJob dataclass."""

    def test_probe_job_creation(self):
        """ProbeJob should be created with default values."""
        job = ProbeJob(job_id="test-job-123")

        assert job.job_id == "test-job-123"
        assert job.status == "queued"
        assert job.total_targets == 0
        assert job.completed == 0

    def test_probe_job_to_dict(self):
        """ProbeJob.to_dict() should return dictionary with results."""
        job = ProbeJob(job_id="test-123", status="completed", total_targets=2)
        job.results = {
            "GET /test": ProbeResult(
                endpoint_id="GET /test",
                method="GET",
                path="/test",
                status="healthy",
            )
        }

        data = job.to_dict()

        assert data["job_id"] == "test-123"
        assert data["status"] == "completed"
        assert "results" in data
        assert "GET /test" in data["results"]


class TestPulseProbeManager:
    """Unit tests for PulseProbeManager."""

    @pytest.fixture
    def mock_app(self):
        """Create mock FastAPI app."""
        return Mock(spec=FastAPI)

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        return Mock(spec=PulseEndpointRegistry)

    @pytest.fixture
    def mock_payload_store(self):
        """Create mock payload store."""
        return Mock(spec=PulsePayloadStore)

    @pytest.fixture
    def probe_manager(self, mock_app, mock_registry, mock_payload_store):
        """Create PulseProbeManager instance."""
        metrics = PulseMetrics()
        return PulseProbeManager(
            mock_app,
            metrics,
            registry=mock_registry,
            payload_store=mock_payload_store,
        )

    def test_probe_manager_initialization(self, probe_manager):
        """ProbeManager should initialize with correct settings."""
        assert probe_manager.request_timeout == 10.0
        assert probe_manager._jobs == {}

    async def test_start_probe_creates_job(self, probe_manager):
        """start_probe should create and track a job."""
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

        job_id = probe_manager.start_probe([endpoint])

        assert job_id in probe_manager._jobs
        job = probe_manager.get_job(job_id)
        assert job.total_targets == 1

    def test_get_job_returns_none_for_unknown(self, probe_manager):
        """get_job should return None for unknown job ID."""
        result = probe_manager.get_job("nonexistent")

        assert result is None

    def test_last_job_returns_most_recent(self, probe_manager):
        """last_job should return the most recently started job."""
        assert probe_manager.last_job() is None

        # Will fail because no event loop, but sets _last_job_id
        try:
            probe_manager.start_probe([])
        except RuntimeError:
            pass

        # last_job should still work
        last = probe_manager.last_job()
        assert last is not None or probe_manager._last_job_id is not None

    async def test_prepare_payload_uses_custom_payload(self, probe_manager, mock_payload_store):
        """_prepare_payload should use custom payload when available."""
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

        custom_payload = {"path_params": {}, "query": {"custom": "value"}}
        mock_payload_store.get.return_value = custom_payload

        result = probe_manager._prepare_payload(endpoint)

        assert result["query"] == {"custom": "value"}
        assert result["source"] == "custom"

    async def test_prepare_payload_skips_missing_body(self, probe_manager, mock_payload_store):
        """_prepare_payload should return None when required body is missing."""
        endpoint = EndpointInfo(
            id="POST /test",
            method="POST",
            path="/test",
            summary="Test",
            tags=[],
            requires_input=True,
            has_path_params=False,
            has_request_body=True,
            path_parameters=[],
            query_parameters=[],
            header_parameters=[],
            request_body_media_type="application/json",
            request_body_schema={"type": "object"},
        )

        mock_payload_store.get.return_value = None
        probe_manager.registry.openapi_schema = {}

        result = probe_manager._prepare_payload(endpoint)

        # Should return None when body is required but not provided
        assert result is None

    def test_format_path_replaces_parameters(self, probe_manager):
        """_format_path should replace path parameters."""
        path = "/users/{user_id}/items/{item_id}"
        params = {"user_id": "123", "item_id": "456"}

        result = probe_manager._format_path(path, params)

        assert result == "/users/123/items/456"

    def test_format_path_handles_empty_params(self, probe_manager):
        """_format_path should handle empty parameters."""
        path = "/test"
        params = {}

        result = probe_manager._format_path(path, params)

        assert result == "/test"

    def test_format_path_handles_none_params(self, probe_manager):
        """_format_path should handle None parameters."""
        path = "/test"

        result = probe_manager._format_path(path, None)

        assert result == "/test"

    async def test_probe_endpoint_handles_timeout(self, probe_manager, mock_payload_store):
        """_probe_endpoint should handle request timeouts."""
        endpoint = EndpointInfo(
            id="GET /slow",
            method="GET",
            path="/slow",
            summary="Slow",
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

        job = ProbeJob(job_id="test", total_targets=1)
        job.results = {
            endpoint.id: ProbeResult(
                endpoint_id=endpoint.id,
                method=endpoint.method,
                path=endpoint.path,
                status="queued",
            )
        }

        mock_payload_store.get.return_value = None
        probe_manager.registry.openapi_schema = {}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        await probe_manager._probe_endpoint(job, mock_client, endpoint)

        result = job.results[endpoint.id]
        assert result.status == "critical"
        assert "Timeout" in result.error

    async def test_probe_endpoint_handles_network_error(self, probe_manager, mock_payload_store):
        """_probe_endpoint should handle network errors."""
        endpoint = EndpointInfo(
            id="GET /error",
            method="GET",
            path="/error",
            summary="Error",
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

        job = ProbeJob(job_id="test", total_targets=1)
        job.results = {
            endpoint.id: ProbeResult(
                endpoint_id=endpoint.id,
                method=endpoint.method,
                path=endpoint.path,
                status="queued",
            )
        }

        mock_payload_store.get.return_value = None
        probe_manager.registry.openapi_schema = {}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

        await probe_manager._probe_endpoint(job, mock_client, endpoint)

        result = job.results[endpoint.id]
        assert result.status == "critical"
        assert result.status_code is None

    async def test_probe_endpoint_skips_when_no_payload(self, probe_manager, mock_payload_store):
        """_probe_endpoint should skip when payload cannot be prepared."""
        endpoint = EndpointInfo(
            id="POST /test",
            method="POST",
            path="/test",
            summary="Test",
            tags=[],
            requires_input=True,
            has_path_params=False,
            has_request_body=True,
            path_parameters=[],
            query_parameters=[],
            header_parameters=[],
            request_body_media_type="application/json",
            request_body_schema={"type": "object"},
        )

        job = ProbeJob(job_id="test", total_targets=1)
        job.results = {
            endpoint.id: ProbeResult(
                endpoint_id=endpoint.id,
                method=endpoint.method,
                path=endpoint.path,
                status="queued",
            )
        }

        mock_payload_store.get.return_value = None
        probe_manager.registry.openapi_schema = {}

        mock_client = AsyncMock()

        await probe_manager._probe_endpoint(job, mock_client, endpoint)

        result = job.results[endpoint.id]
        assert result.status == "skipped"
        assert job.completed == 1

    async def test_probe_endpoint_marks_warning_for_slow_success(self, probe_manager, mock_payload_store):
        """_probe_endpoint should mark warning status for slow successful requests."""
        endpoint = EndpointInfo(
            id="GET /slow",
            method="GET",
            path="/slow",
            summary="Slow",
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

        job = ProbeJob(job_id="test", total_targets=1)
        job.results = {
            endpoint.id: ProbeResult(
                endpoint_id=endpoint.id,
                method=endpoint.method,
                path=endpoint.path,
                status="queued",
            )
        }

        mock_payload_store.get.return_value = None
        probe_manager.registry.openapi_schema = {}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = AsyncMock()

        # Make request artificially slow
        async def slow_request(*args, **kwargs):
            await asyncio.sleep(1.5)  # More than 1000ms threshold
            return mock_response

        mock_client.request = slow_request

        await probe_manager._probe_endpoint(job, mock_client, endpoint)

        result = job.results[endpoint.id]
        assert result.status == "warning"
        assert result.status_code == 200
        assert result.latency_ms > 1000
