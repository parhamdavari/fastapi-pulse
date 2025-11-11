"""Integration tests for FastAPI Pulse full application flow."""

import asyncio

import pytest

from fastapi_pulse import PULSE_STATE_KEY


pytestmark = pytest.mark.integration


class TestFullIntegration:
    """Integration tests for complete FastAPI Pulse workflow."""

    async def test_request_recorded_in_metrics(self, async_client, pulse_metrics):
        """Requests should be recorded and available in metrics."""
        response = await async_client.get("/")
        assert response.status_code == 200

        metrics = pulse_metrics.get_metrics()
        assert metrics["summary"]["total_requests"] >= 1

    async def test_response_time_header_present(self, async_client):
        """All responses should include X-Response-Time-Ms header."""
        response = await async_client.get("/")

        assert "x-response-time-ms" in response.headers
        response_time = float(response.headers["x-response-time-ms"])
        assert response_time >= 0

    async def test_health_endpoint_returns_metrics(self, async_client):
        """GET /health/pulse should return metrics data."""
        response = await async_client.get("/health/pulse")

        assert response.status_code == 200
        data = response.json()

        assert "performance_metrics" in data
        assert "sla_compliance" in data

    async def test_endpoints_list_returns_discovered_routes(self, async_client):
        """GET /health/pulse/endpoints should list all application endpoints."""
        response = await async_client.get("/health/pulse/endpoints")

        assert response.status_code == 200
        data = response.json()

        assert "endpoints" in data
        assert "summary" in data
        assert isinstance(data["endpoints"], list)

    async def test_error_handling_integration(self, async_client, pulse_metrics):
        """Errors should be caught, logged, and metrics updated."""
        response = await async_client.get("/error")

        assert response.status_code == 500

        metrics = pulse_metrics.get_metrics()
        assert metrics["summary"]["total_errors"] >= 1

    async def test_probe_workflow(self, async_client):
        """Complete probe workflow: trigger, poll, verify results."""
        # Trigger probe
        start_response = await async_client.post("/health/pulse/probe")
        assert start_response.status_code == 200

        job_data = start_response.json()
        job_id = job_data["job_id"]

        # Poll for completion
        for _ in range(30):
            await asyncio.sleep(0.1)
            status_response = await async_client.get(
                f"/health/pulse/probe/{job_id}"
            )
            assert status_response.status_code == 200

            status = status_response.json()
            if status["status"] == "completed":
                break

        # Verify completion
        assert status["status"] == "completed"
        assert status["total"] > 0
        assert len(status["results"]) > 0

    async def test_custom_payload_persistence(self, async_client, temp_payload_file):
        """Custom payloads should persist across requests."""
        from urllib.parse import quote

        endpoint_id = "POST /items"
        encoded_id = quote(endpoint_id, safe="")

        custom_payload = {
            "path_params": {},
            "query": {},
            "headers": {"x-test": "value"},
            "body": {"name": "test", "price": 99.99},
        }

        # Save custom payload
        save_response = await async_client.put(
            f"/health/pulse/probe/{encoded_id}/payload",
            json=custom_payload,
        )
        assert save_response.status_code == 200

        # Verify it's stored
        endpoints_response = await async_client.get("/health/pulse/endpoints")
        data = endpoints_response.json()

        item_endpoint = next(
            (e for e in data["endpoints"] if e["id"] == endpoint_id), None
        )
        assert item_endpoint is not None
        assert item_endpoint["payload"]["source"] == "custom"

    async def test_metrics_aggregation_per_endpoint(self, async_client, pulse_metrics):
        """Metrics should be aggregated separately per endpoint."""
        # Make requests to different endpoints
        await async_client.get("/")
        await async_client.get("/items/123")
        await async_client.get("/")

        metrics = pulse_metrics.get_metrics()
        endpoint_metrics = metrics["endpoint_metrics"]

        # Should have metrics for both endpoints
        assert "GET /" in endpoint_metrics
        assert "GET /items/{id}" in endpoint_metrics

        # GET / should have 2 requests
        assert endpoint_metrics["GET /"]["total_requests"] == 2

    async def test_sla_compliance_calculation(self, async_client, pulse_metrics):
        """SLA compliance should be calculated correctly."""
        # Generate enough requests for percentile calculation
        for _ in range(20):
            await async_client.get("/")

        response = await async_client.get("/health/pulse")
        data = response.json()

        sla = data["sla_compliance"]
        assert "latency_sla_met" in sla
        assert "error_rate_sla_met" in sla
        assert "overall_sla_met" in sla

    async def test_path_normalization_in_metrics(self, async_client, pulse_metrics):
        """Paths with IDs should be normalized in metrics."""
        # Make requests with different IDs
        await async_client.get("/items/123")
        await async_client.get("/items/456")
        await async_client.get("/items/789")

        metrics = pulse_metrics.get_metrics()
        endpoint_metrics = metrics["endpoint_metrics"]

        # All should be grouped under normalized path
        normalized_key = "GET /items/{id}"
        assert normalized_key in endpoint_metrics
        assert endpoint_metrics[normalized_key]["total_requests"] == 3

    async def test_excluded_paths_not_tracked(self, async_client, pulse_metrics):
        """Pulse internal endpoints should not be tracked in metrics."""
        initial_metrics = pulse_metrics.get_metrics()
        initial_count = initial_metrics["summary"]["total_requests"]

        # Make requests to pulse endpoints
        await async_client.get("/health/pulse")
        await async_client.get("/health/pulse/endpoints")

        final_metrics = pulse_metrics.get_metrics()
        final_count = final_metrics["summary"]["total_requests"]

        # Count should not increase
        assert final_count == initial_count

    async def test_concurrent_requests_handled_correctly(
        self, async_client, pulse_metrics
    ):
        """Concurrent requests should be handled safely."""
        # Make concurrent requests
        tasks = [async_client.get("/") for _ in range(10)]
        responses = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

        # Metrics should reflect all requests
        metrics = pulse_metrics.get_metrics()
        assert metrics["endpoint_metrics"]["GET /"]["total_requests"] == 10

    async def test_status_code_distribution(self, async_client, pulse_metrics):
        """Status codes should be tracked correctly."""
        # Make requests with different outcomes
        await async_client.get("/")  # 200
        await async_client.get("/items/999")  # 200
        await async_client.post("/items", json={"name": "test", "price": 1.0})  # 200
        await async_client.get("/error")  # 500

        metrics = pulse_metrics.get_metrics()

        # Check overall counts
        assert metrics["summary"]["total_requests"] == 4
        assert metrics["summary"]["total_errors"] >= 1

    async def test_probe_selective_endpoints(self, async_client):
        """Probe should support targeting specific endpoints."""
        # Trigger probe for specific endpoint
        probe_request = {"endpoints": ["GET /"]}

        response = await async_client.post(
            "/health/pulse/probe", json=probe_request
        )
        assert response.status_code == 200

        job_data = response.json()
        assert job_data["total"] == 1

    async def test_probe_missing_endpoint_error(self, async_client):
        """Probe should return 404 for non-existent endpoints."""
        probe_request = {"endpoints": ["GET /nonexistent"]}

        response = await async_client.post(
            "/health/pulse/probe", json=probe_request
        )

        assert response.status_code == 404
        assert "missing_endpoints" in response.json()["detail"]

    async def test_delete_payload_integration(self, async_client):
        """Deleting payload should revert to generated payload."""
        from urllib.parse import quote

        endpoint_id = "POST /items"
        encoded_id = quote(endpoint_id, safe="")

        # Set custom payload
        custom = {
            "path_params": {},
            "query": {},
            "headers": {},
            "body": {"name": "custom", "price": 1.0},
        }
        await async_client.put(
            f"/health/pulse/probe/{encoded_id}/payload", json=custom
        )

        # Delete it
        delete_response = await async_client.delete(
            f"/health/pulse/probe/{encoded_id}/payload"
        )
        assert delete_response.status_code == 200

        # Verify it's gone
        endpoints_response = await async_client.get("/health/pulse/endpoints")
        data = endpoints_response.json()

        item_endpoint = next(
            (e for e in data["endpoints"] if e["id"] == endpoint_id), None
        )
        assert item_endpoint["payload"]["source"] in ["generated", "none"]

    async def test_metrics_window_behavior(self, async_client, pulse_metrics):
        """Metrics should respect configured window settings."""
        # Record some requests
        for _ in range(5):
            await async_client.get("/")

        metrics = pulse_metrics.get_metrics()
        summary = metrics["summary"]

        # Window seconds should be reflected
        assert summary["window_seconds"] == 300
        assert summary["window_request_count"] == 5

    async def test_probe_job_not_found(self, async_client):
        """Accessing non-existent probe job should return 404."""
        response = await async_client.get("/health/pulse/probe/invalid-job-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_endpoint_summary_includes_metadata(self, async_client):
        """Endpoint listings should include summary metadata."""
        response = await async_client.get("/health/pulse/endpoints")
        data = response.json()

        summary = data["summary"]
        assert "total" in summary
        assert "auto_probed" in summary
        assert "requires_input" in summary

    async def test_successful_probe_updates_last_probe(self, async_client):
        """Successful probe should update last_probe status."""
        # Trigger probe
        start = await async_client.post("/health/pulse/probe")
        job_id = start.json()["job_id"]

        # Wait for completion
        for _ in range(30):
            await asyncio.sleep(0.1)
            status = await async_client.get(f"/health/pulse/probe/{job_id}")
            if status.json()["status"] == "completed":
                break

        # Check endpoints have probe results
        endpoints = await async_client.get("/health/pulse/endpoints")
        data = endpoints.json()

        # At least one endpoint should have probe results
        has_probe_results = any(
            e["last_probe"]["status"] != "unknown" for e in data["endpoints"]
        )
        assert has_probe_results

    async def test_response_time_header_format(self, async_client):
        """Response time header should be formatted correctly."""
        response = await async_client.get("/")

        header_value = response.headers["x-response-time-ms"]

        # Should be parseable as float
        response_time = float(header_value)
        assert response_time >= 0

        # Should have reasonable precision
        assert "." in header_value
