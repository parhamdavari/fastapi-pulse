"""Unit tests for probe router endpoints."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from urllib.parse import quote

from fastapi_pulse import add_pulse


@pytest.fixture(name="client")
def client_fixture():
    """Provide a TestClient backed by an app with Pulse enabled."""
    app = FastAPI()

    @app.get("/items/{item_id}")
    def read_item(item_id: int):
        return {"id": item_id, "status": "ok"}

    @app.post("/items")
    def create_item(payload: dict):
        return payload

    add_pulse(app)
    manager = app.state.fastapi_pulse_probe_manager
    manager.min_probe_interval = 0

    with TestClient(app) as client:
        yield client


def test_probe_start_without_body_returns_job_id(client: TestClient):
    """POST /pulse/probe without body should return job_id."""
    response = client.post("/health/pulse/probe")
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert isinstance(data["job_id"], str)
    assert "total" in data
    assert isinstance(data["total"], int)


def test_probe_start_with_endpoints_returns_job_id(client: TestClient):
    """POST /pulse/probe with JSON body should return job_id."""
    # Get available endpoints first
    endpoints_response = client.get("/health/pulse/endpoints")
    assert endpoints_response.status_code == 200
    endpoints_data = endpoints_response.json()
    endpoint_ids = [e["id"] for e in endpoints_data["endpoints"]]

    if endpoint_ids:
        # Test with valid endpoint
        response = client.post(
            "/health/pulse/probe",
            json={"endpoints": [endpoint_ids[0]]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert isinstance(data["job_id"], str)
        assert "total" in data
        assert data["total"] >= 1


def test_probe_start_with_invalid_endpoint_returns_404(client: TestClient):
    """POST /pulse/probe with non-existent endpoint should return 404."""
    response = client.post(
            "/health/pulse/probe",
        json={"endpoints": ["GET /nonexistent/endpoint"]}
    )
    assert response.status_code == 404
    assert "missing_endpoints" in response.json()["detail"]


def test_probe_status_returns_job_info(client: TestClient):
    """GET /pulse/probe/{job_id} should return job status."""
    # Start a probe job
    start_response = client.post("/health/pulse/probe")
    assert start_response.status_code == 200
    job_id = start_response.json()["job_id"]

    # Check job status
    status_response = client.get(f"/health/pulse/probe/{job_id}")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert "status" in status_data
    assert status_data["status"] in ["queued", "running", "completed", "failed", "timeout"]


def test_probe_status_invalid_job_returns_404(client: TestClient):
    """GET /pulse/probe/{job_id} with invalid job_id should return 404."""
    response = client.get("/health/pulse/probe/invalid-job-id-12345")
    assert response.status_code == 404
    assert response.json()["detail"] == "Probe job not found"


def test_save_custom_payload(client: TestClient):
    """PUT /pulse/probe/{endpoint_id}/payload should save custom payload."""
    # Get available endpoints
    endpoints_response = client.get("/health/pulse/endpoints")
    endpoints_data = endpoints_response.json()

    # Find a POST endpoint for testing
    post_endpoint = None
    for e in endpoints_data["endpoints"]:
        if e["method"] == "POST":
            post_endpoint = e
            break

    if post_endpoint:
        endpoint_id = post_endpoint["id"]
        encoded_id = quote(endpoint_id, safe='')

        custom_payload = {
            "path_params": {},
            "query": {"test": "value"},
            "headers": {"x-custom": "header"},
            "body": {"name": "test", "value": 123}
        }

        response = client.put(
            f"/health/pulse/probe/{encoded_id}/payload",
            json=custom_payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["payload"]["source"] == "custom"
        assert "query" in data["payload"]


def test_save_payload_invalid_endpoint_returns_404(client: TestClient):
    """PUT /pulse/probe/{endpoint_id}/payload with invalid endpoint should return 404."""
    endpoint_id = "GET /nonexistent/endpoint"
    encoded_id = quote(endpoint_id, safe='')

    response = client.put(
        f"/health/pulse/probe/{encoded_id}/payload",
        json={"body": {"test": "data"}}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Endpoint not found"


def test_delete_custom_payload(client: TestClient):
    """DELETE /pulse/probe/{endpoint_id}/payload should reset to generated."""
    # Get available endpoints
    endpoints_response = client.get("/health/pulse/endpoints")
    endpoints_data = endpoints_response.json()

    # Find a POST endpoint
    post_endpoint = None
    for e in endpoints_data["endpoints"]:
        if e["method"] == "POST":
            post_endpoint = e
            break

    if post_endpoint:
        endpoint_id = post_endpoint["id"]
        encoded_id = quote(endpoint_id, safe='')

        # First save a custom payload
        custom_payload = {
            "body": {"name": "test"}
        }
        client.put(
            f"/health/pulse/probe/{encoded_id}/payload",
            json=custom_payload
        )

        # Delete it
        response = client.delete(f"/health/pulse/probe/{encoded_id}/payload")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Verify it's reset to generated
        endpoints_response = client.get("/health/pulse/endpoints")
        endpoints_data = endpoints_response.json()
        endpoint = next((e for e in endpoints_data["endpoints"] if e["id"] == endpoint_id), None)
        if endpoint:
            assert endpoint["payload"]["source"] in ["generated", "none"]


def test_delete_payload_invalid_endpoint_returns_404(client: TestClient):
    """DELETE /pulse/probe/{endpoint_id}/payload with invalid endpoint should return 404."""
    endpoint_id = "GET /nonexistent/endpoint"
    encoded_id = quote(endpoint_id, safe='')

    response = client.delete(f"/health/pulse/probe/{encoded_id}/payload")
    assert response.status_code == 404
    assert response.json()["detail"] == "Endpoint not found"


def test_multiple_probe_jobs_with_different_payloads(client: TestClient):
    """Test multiple probe jobs can run with different endpoint selections."""
    # First probe with all endpoints
    response1 = client.post("/health/pulse/probe")
    assert response1.status_code == 200
    job1_id = response1.json()["job_id"]

    # Get endpoint list
    endpoints_response = client.get("/health/pulse/endpoints")
    endpoints_data = endpoints_response.json()
    endpoint_ids = [e["id"] for e in endpoints_data["endpoints"]]

    if len(endpoint_ids) > 1:
        # Second probe with specific endpoint
        response2 = client.post(
            "/health/pulse/probe",
            json={"endpoints": [endpoint_ids[0]]}
        )
        assert response2.status_code == 200
        job2_id = response2.json()["job_id"]

        # Job IDs should be different
        assert job1_id != job2_id

        # Both jobs should be queryable
        status1 = client.get(f"/health/pulse/probe/{job1_id}")
        status2 = client.get(f"/health/pulse/probe/{job2_id}")
        assert status1.status_code == 200
        assert status2.status_code == 200


def test_probe_start_returns_500_when_job_id_missing(client: TestClient):
    """POST /pulse/probe should surface 500 when probe manager fails."""
    manager = client.app.state.fastapi_pulse_probe_manager
    original_start = manager.start_probe
    try:
        manager.start_probe = lambda targets: None  # type: ignore[assignment]
        response = client.post("/health/pulse/probe")
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to start probe job"
    finally:
        manager.start_probe = original_start


def test_endpoints_require_input_summary_counts(monkeypatch, client: TestClient):
    """Ensure requires_input counter increments when no payload can be built."""
    monkeypatch.setattr(
        "fastapi_pulse.router.SamplePayloadBuilder.build",
        lambda self, endpoint: None,
        raising=False,
    )
    response = client.get("/health/pulse/endpoints")
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["requires_input"] >= 1
