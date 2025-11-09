"""Additional coverage for the registry module."""

from __future__ import annotations

from fastapi_pulse.registry import EndpointInfo, PulseEndpointRegistry


class DummyApp:
    def __init__(self, schema):
        self._schema = schema

    def openapi(self):
        return self._schema


def build_schema():
    return {
        "paths": {
            "/health/pulse/private": {"get": {}},
            "/skip/me": {"get": {}},
            "/invalid": [],
            "/mixed": {
                "parameters": [{"name": "common", "in": "query"}],
                "trace": {},
                "get": "not-a-dict",
                "post": {
                    "summary": "Create",
                    "parameters": [
                        {"name": "item_id", "in": "path", "required": True},
                        {"name": "q", "in": "query", "required": True, "schema": {}},
                    ],
                    "requestBody": {
                        "content": {
                            "text/plain": {
                                "schema": {"type": "string"}
                            }
                        }
                    },
                },
            },
            "/no-input": {
                "get": {
                    "summary": "List",
                    "parameters": [],
                }
            },
        }
    }


def test_registry_parses_various_operations():
    schema = build_schema()
    app = DummyApp(schema)
    registry = PulseEndpointRegistry(app, exclude_prefixes=["/skip"])

    endpoints = registry.list_endpoints()
    endpoint_ids = {endpoint.id for endpoint in endpoints}

    assert "POST /mixed" in endpoint_ids
    assert "GET /no-input" in endpoint_ids
    assert "GET /health/pulse/private" not in endpoint_ids
    assert "GET /skip/me" not in endpoint_ids

    # Ensure EndpointInfo serialization is covered
    info_dict = next(iter(endpoints)).to_dict()
    assert "id" in info_dict

    # Ensure openapi_schema property refreshes
    assert registry.openapi_schema["paths"]

    # auto_probe_targets should exclude requires_input endpoints
    targets = registry.auto_probe_targets()
    assert all(not endpoint.requires_input for endpoint in targets)
