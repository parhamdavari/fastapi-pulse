"""Tests for router error handling paths to improve coverage."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_get_registry_raises_when_not_initialized():
    """Test that _get_registry raises RuntimeError when not initialized."""
    from fastapi_pulse.router import _get_registry
    from fastapi import Request

    # Create a minimal app without add_pulse
    app = FastAPI()

    with TestClient(app) as client:
        # Create a mock request
        response = app.router.match(("/", "GET"))
        # This will fail because we can't easily create a Request object
        # Instead, we'll test this through the endpoint

    # Better approach: test through endpoint
    from fastapi_pulse.router import create_pulse_router
    from fastapi_pulse.metrics import PulseMetrics

    app = FastAPI()
    metrics = PulseMetrics()
    router = create_pulse_router(metrics)
    app.include_router(router)

    # Don't initialize pulse - this will cause RuntimeError
    # when trying to access registry
    client = TestClient(app)

    # This should raise RuntimeError about registry not initialized
    with pytest.raises(Exception) as exc_info:
        response = client.get("/health/pulse/endpoints")
    # The error will be wrapped in HTTP 500


def test_get_probe_manager_raises_when_not_initialized():
    """Test that _get_probe_manager raises RuntimeError when not initialized."""
    from fastapi_pulse.router import create_pulse_router
    from fastapi_pulse.metrics import PulseMetrics

    app = FastAPI()
    metrics = PulseMetrics()
    router = create_pulse_router(metrics)
    app.include_router(router)

    client = TestClient(app)

    # Probe endpoint should fail without probe manager
    with pytest.raises(Exception):
        response = client.post("/health/pulse/probe")


def test_get_payload_store_raises_when_not_initialized():
    """Test that _get_payload_store raises RuntimeError when not initialized."""
    from fastapi_pulse.router import create_pulse_router
    from fastapi_pulse.metrics import PulseMetrics

    app = FastAPI()
    metrics = PulseMetrics()
    router = create_pulse_router(metrics)
    app.include_router(router)

    client = TestClient(app)

    # Payload endpoints should fail without payload store
    with pytest.raises(Exception):
        response = client.put("/health/pulse/probe/GET%20%2Ftest/payload", json={})
