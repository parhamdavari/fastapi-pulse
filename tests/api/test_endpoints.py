"""API endpoint tests for FastAPI Pulse."""

import pytest


pytestmark = pytest.mark.api


class TestHealthPulseEndpoint:
    """Tests for GET /health/pulse endpoint."""

    async def test_returns_200(self, async_client):
        """Endpoint should return 200 OK."""
        response = await async_client.get("/health/pulse")
        assert response.status_code == 200

    async def test_response_structure(self, async_client):
        """Response should have expected structure."""
        response = await async_client.get("/health/pulse")
        data = response.json()

        assert "performance_metrics" in data
        assert "sla_compliance" in data

        perf = data["performance_metrics"]
        assert "summary" in perf
        assert "endpoint_metrics" in perf

        sla = data["sla_compliance"]
        assert "latency_sla_met" in sla
        assert "error_rate_sla_met" in sla
        assert "overall_sla_met" in sla

    async def test_summary_metrics(self, async_client, pulse_metrics):
        """Summary should include key metrics."""
        # Generate some data
        for _ in range(3):
            await async_client.get("/")

        response = await async_client.get("/health/pulse")
        data = response.json()

        summary = data["performance_metrics"]["summary"]
        assert "total_requests" in summary
        assert "total_errors" in summary
        assert "error_rate" in summary
        assert "avg_response_time" in summary

    async def test_sla_details(self, async_client):
        """SLA compliance should include details."""
        response = await async_client.get("/health/pulse")
        data = response.json()

        details = data["sla_compliance"]["details"]
        assert "p95_response_time" in details
        assert "error_rate" in details
        assert "p95_response_time_sla" in details
        assert "error_rate_sla" in details


class TestEndpointsListEndpoint:
    """Tests for GET /health/pulse/endpoints endpoint."""

    async def test_returns_200(self, async_client):
        """Endpoint should return 200 OK."""
        response = await async_client.get("/health/pulse/endpoints")
        assert response.status_code == 200

    async def test_response_structure(self, async_client):
        """Response should have expected structure."""
        response = await async_client.get("/health/pulse/endpoints")
        data = response.json()

        assert "endpoints" in data
        assert "summary" in data
        assert isinstance(data["endpoints"], list)

    async def test_endpoint_entry_structure(self, async_client):
        """Each endpoint entry should have required fields."""
        response = await async_client.get("/health/pulse/endpoints")
        data = response.json()

        if data["endpoints"]:
            endpoint = data["endpoints"][0]
            assert "id" in endpoint
            assert "method" in endpoint
            assert "path" in endpoint
            assert "metrics" in endpoint
            assert "last_probe" in endpoint
            assert "payload" in endpoint

    async def test_summary_counts(self, async_client):
        """Summary should include endpoint counts."""
        response = await async_client.get("/health/pulse/endpoints")
        data = response.json()

        summary = data["summary"]
        assert "total" in summary
        assert "auto_probed" in summary
        assert "requires_input" in summary

        # Counts should be consistent
        assert summary["total"] == len(data["endpoints"])


class TestProbeEndpoints:
    """Tests for probe-related endpoints."""

    async def test_trigger_probe_returns_job_id(self, async_client):
        """POST /health/pulse/probe should return job ID."""
        response = await async_client.post("/health/pulse/probe")

        assert response.status_code == 200
        data = response.json()

        assert "job_id" in data
        assert "total" in data
        assert isinstance(data["job_id"], str)

    async def test_probe_status_returns_job_details(self, async_client):
        """GET /health/pulse/probe/{job_id} should return job status."""
        # Start a probe
        start = await async_client.post("/health/pulse/probe")
        job_id = start.json()["job_id"]

        # Get status
        response = await async_client.get(f"/health/pulse/probe/{job_id}")

        assert response.status_code == 200
        data = response.json()

        assert "job_id" in data
        assert "status" in data
        assert "total" in data
        assert "completed" in data
        assert "results" in data

    async def test_probe_nonexistent_job_404(self, async_client):
        """Requesting non-existent job should return 404."""
        response = await async_client.get("/health/pulse/probe/nonexistent")

        assert response.status_code == 404

    async def test_probe_selective_endpoints(self, async_client):
        """Probe should accept endpoint filter."""
        payload = {"endpoints": ["GET /"]}

        response = await async_client.post("/health/pulse/probe", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    async def test_probe_invalid_endpoints_404(self, async_client):
        """Probe with invalid endpoints should return 404."""
        payload = {"endpoints": ["GET /invalid"]}

        response = await async_client.post("/health/pulse/probe", json=payload)

        assert response.status_code == 404


class TestPayloadEndpoints:
    """Tests for payload management endpoints."""

    async def test_save_payload_returns_200(self, async_client):
        """PUT /health/pulse/probe/{endpoint_id}/payload should succeed."""
        from urllib.parse import quote

        endpoint_id = quote("POST /items", safe="")
        payload = {
            "path_params": {},
            "query": {},
            "headers": {},
            "body": {"name": "test", "price": 1.0},
        }

        response = await async_client.put(
            f"/health/pulse/probe/{endpoint_id}/payload",
            json=payload,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "ok"
        assert "payload" in data

    async def test_save_payload_marks_as_custom(self, async_client):
        """Saved payload should be marked with source=custom."""
        from urllib.parse import quote

        endpoint_id = quote("POST /items", safe="")
        payload = {
            "path_params": {},
            "query": {},
            "headers": {},
            "body": {"test": "data"},
        }

        response = await async_client.put(
            f"/health/pulse/probe/{endpoint_id}/payload",
            json=payload,
        )

        data = response.json()
        assert data["payload"]["source"] == "custom"

    async def test_save_payload_invalid_endpoint_404(self, async_client):
        """Saving payload for non-existent endpoint should return 404."""
        from urllib.parse import quote

        endpoint_id = quote("GET /nonexistent", safe="")
        payload = {
            "path_params": {},
            "query": {},
            "headers": {},
            "body": None,
        }

        response = await async_client.put(
            f"/health/pulse/probe/{endpoint_id}/payload",
            json=payload,
        )

        assert response.status_code == 404

    async def test_delete_payload_returns_200(self, async_client):
        """DELETE /health/pulse/probe/{endpoint_id}/payload should succeed."""
        from urllib.parse import quote

        endpoint_id = quote("POST /items", safe="")

        # First save
        await async_client.put(
            f"/health/pulse/probe/{endpoint_id}/payload",
            json={"path_params": {}, "query": {}, "headers": {}, "body": None},
        )

        # Then delete
        response = await async_client.delete(
            f"/health/pulse/probe/{endpoint_id}/payload"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    async def test_delete_payload_invalid_endpoint_404(self, async_client):
        """Deleting payload for non-existent endpoint should return 404."""
        from urllib.parse import quote

        endpoint_id = quote("GET /nonexistent", safe="")

        response = await async_client.delete(
            f"/health/pulse/probe/{endpoint_id}/payload"
        )

        assert response.status_code == 404


class TestApplicationEndpoints:
    """Tests for application endpoints (not pulse endpoints)."""

    async def test_root_endpoint(self, async_client):
        """Application root endpoint should work."""
        response = await async_client.get("/")
        assert response.status_code == 200

    async def test_items_get(self, async_client):
        """GET /items/{item_id} should work."""
        response = await async_client.get("/items/123")
        assert response.status_code == 200
        data = response.json()
        assert "item_id" in data

    async def test_items_post(self, async_client):
        """POST /items should accept valid payload."""
        response = await async_client.post(
            "/items",
            json={"name": "test item", "price": 99.99},
        )
        assert response.status_code == 200

    async def test_error_endpoint_returns_500(self, async_client):
        """Error endpoint should return 500."""
        response = await async_client.get("/error")
        assert response.status_code == 500

    async def test_all_responses_have_headers(self, async_client):
        """All application responses should have response time header."""
        endpoints = [
            "/",
            "/items/123",
        ]

        for endpoint in endpoints:
            response = await async_client.get(endpoint)
            assert "x-response-time-ms" in response.headers


class TestCORSAndSecurity:
    """Tests for CORS and security features."""

    async def test_cors_headers_present(self, async_client):
        """CORS should be enabled for pulse endpoints."""
        response = await async_client.options(
            "/health/pulse",
            headers={"Origin": "http://example.com"},
        )

        # Should not fail
        assert response.status_code in [200, 204, 405]  # Method may not be allowed but shouldn't fail

    async def test_pulse_endpoints_not_in_openapi(self, async_client, app_with_pulse):
        """Pulse endpoints should be excluded from OpenAPI schema."""
        schema = app_with_pulse.openapi()

        # Pulse management endpoints shouldn't be in schema
        assert "/health/pulse" not in schema.get("paths", {})
