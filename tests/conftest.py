"""Shared test fixtures for FastAPI Pulse test suite."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncIterator, Iterator

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pydantic import BaseModel

from fastapi_pulse import add_pulse, PulseMetrics
from fastapi_pulse.constants import (
    PULSE_ENDPOINT_REGISTRY_KEY,
    PULSE_PAYLOAD_STORE_KEY,
    PULSE_PROBE_MANAGER_KEY,
    PULSE_STATE_KEY,
)


# Fixtures for isolation

@pytest.fixture
def temp_dir() -> Iterator[Path]:
    """Provide a temporary directory for test file operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_payload_file(temp_dir: Path) -> Path:
    """Provide a temporary file path for payload storage."""
    return temp_dir / "test_payloads.json"


@pytest.fixture
def clean_metrics() -> PulseMetrics:
    """Provide a fresh PulseMetrics instance with default settings."""
    return PulseMetrics(window_seconds=300, bucket_seconds=60)


# App factory fixtures

@pytest.fixture
def simple_app() -> FastAPI:
    """Create a minimal FastAPI app without pulse."""
    app = FastAPI(title="Test App")

    @app.get("/")
    async def root():
        return {"message": "ok"}

    @app.get("/users/{user_id}")
    async def get_user(user_id: int):
        return {"user_id": user_id, "name": "test"}

    return app


@pytest.fixture
def app_with_pulse(temp_payload_file: Path) -> FastAPI:
    """Create a FastAPI app with pulse monitoring enabled."""
    app = FastAPI(title="Test App with Pulse")

    @app.get("/")
    async def root():
        return {"message": "ok"}

    @app.get("/items/{item_id}")
    async def get_item(item_id: int):
        return {"item_id": item_id}

    @app.get("/error")
    async def error():
        raise ValueError("Test error")

    class CreateItemRequest(BaseModel):
        name: str
        price: float

    @app.post("/items")
    async def create_item(item: CreateItemRequest):
        return {"name": item.name, "price": item.price}

    add_pulse(
        app,
        enable_detailed_logging=False,
        payload_config_path=temp_payload_file,
    )

    return app


@pytest.fixture
async def async_client(app_with_pulse: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Provide an async HTTP client with ASGI transport for testing."""
    async with LifespanManager(app_with_pulse):
        transport = httpx.ASGITransport(app=app_with_pulse)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver"
        ) as client:
            yield client


@pytest.fixture
async def sync_client_lifespan(app_with_pulse: FastAPI) -> AsyncIterator[FastAPI]:
    """Manage app lifespan for synchronous test clients."""
    async with LifespanManager(app_with_pulse):
        yield app_with_pulse


# Component access fixtures

@pytest.fixture
def pulse_metrics(app_with_pulse: FastAPI) -> PulseMetrics:
    """Extract PulseMetrics from app state."""
    return getattr(app_with_pulse.state, PULSE_STATE_KEY)


@pytest.fixture
def pulse_registry(app_with_pulse: FastAPI):
    """Extract PulseEndpointRegistry from app state."""
    return getattr(app_with_pulse.state, PULSE_ENDPOINT_REGISTRY_KEY)


@pytest.fixture
def pulse_probe_manager(app_with_pulse: FastAPI):
    """Extract PulseProbeManager from app state."""
    return getattr(app_with_pulse.state, PULSE_PROBE_MANAGER_KEY)


@pytest.fixture
def pulse_payload_store(app_with_pulse: FastAPI):
    """Extract PulsePayloadStore from app state."""
    return getattr(app_with_pulse.state, PULSE_PAYLOAD_STORE_KEY)


# OpenAPI schema fixtures

@pytest.fixture
def sample_openapi_schema() -> dict:
    """Provide a sample OpenAPI schema for testing."""
    return {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/items/{item_id}": {
                "get": {
                    "summary": "Get Item",
                    "operationId": "get_item",
                    "tags": ["items"],
                    "parameters": [
                        {
                            "name": "item_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {"200": {"description": "Success"}},
                },
                "put": {
                    "summary": "Update Item",
                    "operationId": "update_item",
                    "tags": ["items"],
                    "parameters": [
                        {
                            "name": "item_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "price": {"type": "number"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "Success"}},
                },
            },
            "/search": {
                "get": {
                    "summary": "Search Items",
                    "operationId": "search_items",
                    "tags": ["items"],
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "Success"}},
                },
            },
        },
        "components": {
            "schemas": {
                "Item": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "price": {"type": "number"},
                    },
                }
            }
        },
    }


# Event loop configuration for pytest-asyncio

@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for consistent async behavior."""
    return asyncio.get_event_loop_policy()
