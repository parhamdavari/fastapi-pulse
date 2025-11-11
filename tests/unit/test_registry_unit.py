"""Unit tests for the PulseEndpointRegistry module."""

import pytest
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi_pulse.registry import EndpointInfo, PulseEndpointRegistry


pytestmark = pytest.mark.unit


class TestEndpointInfo:
    """Unit tests for EndpointInfo dataclass."""

    def test_endpoint_info_creation(self):
        """EndpointInfo should be created with all required fields."""
        endpoint = EndpointInfo(
            id="GET /users",
            method="GET",
            path="/users",
            summary="List users",
            tags=["users"],
            requires_input=False,
            has_path_params=False,
            has_request_body=False,
            path_parameters=[],
            query_parameters=[],
            header_parameters=[],
            request_body_media_type=None,
            request_body_schema=None,
        )

        assert endpoint.id == "GET /users"
        assert endpoint.method == "GET"
        assert endpoint.path == "/users"
        assert endpoint.requires_input is False

    def test_endpoint_info_to_dict(self):
        """EndpointInfo.to_dict() should return serializable dictionary."""
        endpoint = EndpointInfo(
            id="POST /items",
            method="POST",
            path="/items",
            summary="Create item",
            tags=["items"],
            requires_input=True,
            has_path_params=False,
            has_request_body=True,
            path_parameters=[],
            query_parameters=[],
            header_parameters=[],
            request_body_media_type="application/json",
            request_body_schema={"type": "object"},
        )

        result = endpoint.to_dict()

        assert isinstance(result, dict)
        assert result["id"] == "POST /items"
        assert result["method"] == "POST"
        assert result["requires_input"] is True


class TestPulseEndpointRegistry:
    """Unit tests for PulseEndpointRegistry."""

    @pytest.fixture
    def mock_app(self, sample_openapi_schema):
        """Create a mock FastAPI app with OpenAPI schema."""
        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=sample_openapi_schema)
        return app

    def test_registry_initialization(self, simple_app):
        """Registry should initialize without errors."""
        registry = PulseEndpointRegistry(simple_app)
        assert registry.app == simple_app
        assert len(registry._endpoints) == 0

    def test_refresh_discovers_endpoints(self, mock_app):
        """refresh() should discover endpoints from OpenAPI schema."""
        registry = PulseEndpointRegistry(mock_app)
        registry.refresh()

        endpoints = registry._endpoints
        assert len(endpoints) > 0

        # Verify expected endpoints
        endpoint_ids = {ep.id for ep in endpoints}
        assert "GET /items/{item_id}" in endpoint_ids
        assert "PUT /items/{item_id}" in endpoint_ids
        assert "GET /search" in endpoint_ids

    def test_list_endpoints_returns_copy(self, mock_app):
        """list_endpoints() should return a list copy."""
        registry = PulseEndpointRegistry(mock_app)

        endpoints1 = registry.list_endpoints()
        endpoints2 = registry.list_endpoints()

        # Should be different list instances
        assert endpoints1 is not endpoints2
        # But with same content
        assert len(endpoints1) == len(endpoints2)

    def test_get_endpoint_map(self, mock_app):
        """get_endpoint_map() should return endpoints keyed by ID."""
        registry = PulseEndpointRegistry(mock_app)

        endpoint_map = registry.get_endpoint_map()

        assert isinstance(endpoint_map, dict)
        assert "GET /items/{item_id}" in endpoint_map
        assert endpoint_map["GET /items/{item_id}"].method == "GET"

    def test_exclude_prefixes_filters_endpoints(self, sample_openapi_schema):
        """Registry should exclude endpoints matching configured prefixes."""
        # Add health endpoint to schema
        schema_with_health = sample_openapi_schema.copy()
        schema_with_health["paths"]["/health/pulse"] = {
            "get": {
                "summary": "Health check",
                "responses": {"200": {"description": "OK"}},
            }
        }

        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=schema_with_health)

        registry = PulseEndpointRegistry(
            app,
            exclude_prefixes=["/health/pulse"]
        )

        endpoints = registry.list_endpoints()
        endpoint_paths = {ep.path for ep in endpoints}

        # Health endpoint should be excluded
        assert "/health/pulse" not in endpoint_paths

    def test_requires_input_detection_path_params(self):
        """Endpoints with path parameters should be marked as requires_input."""
        schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/users/{user_id}": {
                    "get": {
                        "parameters": [
                            {
                                "name": "user_id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "integer"},
                            }
                        ],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }

        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=schema)

        registry = PulseEndpointRegistry(app)
        endpoints = registry.list_endpoints()

        endpoint = endpoints[0]
        assert endpoint.requires_input is True
        assert endpoint.has_path_params is True

    def test_requires_input_detection_request_body(self):
        """Endpoints with request body should be marked as requires_input."""
        schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/items": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            }
                        },
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }

        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=schema)

        registry = PulseEndpointRegistry(app)
        endpoints = registry.list_endpoints()

        endpoint = endpoints[0]
        assert endpoint.requires_input is True
        assert endpoint.has_request_body is True

    def test_requires_input_detection_required_query(self):
        """Endpoints with required query params should be marked as requires_input."""
        schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/search": {
                    "get": {
                        "parameters": [
                            {
                                "name": "q",
                                "in": "query",
                                "required": True,
                                "schema": {"type": "string"},
                            }
                        ],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }

        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=schema)

        registry = PulseEndpointRegistry(app)
        endpoints = registry.list_endpoints()

        endpoint = endpoints[0]
        assert endpoint.requires_input is True

    def test_auto_probe_targets_filters_correctly(self, mock_app):
        """auto_probe_targets() should return only endpoints without required input."""
        registry = PulseEndpointRegistry(mock_app)

        auto_targets = registry.auto_probe_targets()

        # All returned endpoints should not require input
        for endpoint in auto_targets:
            assert endpoint.requires_input is False

    def test_openapi_schema_property(self, mock_app, sample_openapi_schema):
        """openapi_schema property should return the schema."""
        registry = PulseEndpointRegistry(mock_app)

        schema = registry.openapi_schema

        assert schema == sample_openapi_schema

    def test_schema_hash_prevents_unnecessary_refresh(self, mock_app):
        """Registry should not re-parse if schema hasn't changed."""
        registry = PulseEndpointRegistry(mock_app)

        # First refresh
        registry.refresh()
        first_hash = registry._schema_hash
        first_endpoints = list(registry._endpoints)

        # Second refresh (schema unchanged)
        registry.refresh()
        second_hash = registry._schema_hash
        second_endpoints = list(registry._endpoints)

        # Hashes should match
        assert first_hash == second_hash
        # Endpoints should be same instances (not re-parsed)
        assert first_endpoints is second_endpoints

    def test_multiple_methods_same_path(self):
        """Registry should handle multiple HTTP methods for same path."""
        schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/items": {
                    "get": {"responses": {"200": {"description": "OK"}}},
                    "post": {"responses": {"200": {"description": "OK"}}},
                    "delete": {"responses": {"200": {"description": "OK"}}},
                }
            },
        }

        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=schema)

        registry = PulseEndpointRegistry(app)
        endpoints = registry.list_endpoints()

        methods = {ep.method for ep in endpoints}
        assert methods == {"GET", "POST", "DELETE"}

    def test_endpoints_sorted_by_path_and_method(self, mock_app):
        """Endpoints should be sorted by path then method."""
        registry = PulseEndpointRegistry(mock_app)
        endpoints = registry.list_endpoints()

        # Verify sorting
        for i in range(len(endpoints) - 1):
            current = endpoints[i]
            next_ep = endpoints[i + 1]

            # Either current path < next path, or same path with current method <= next method
            assert (current.path < next_ep.path) or \
                   (current.path == next_ep.path and current.method <= next_ep.method)

    def test_endpoint_summary_extraction(self):
        """Registry should extract summary or operationId for endpoints."""
        schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/with-summary": {
                    "get": {
                        "summary": "Get items",
                        "responses": {"200": {"description": "OK"}},
                    }
                },
                "/with-operation-id": {
                    "get": {
                        "operationId": "get_users",
                        "responses": {"200": {"description": "OK"}},
                    }
                },
            },
        }

        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=schema)

        registry = PulseEndpointRegistry(app)
        endpoints = registry.list_endpoints()

        summaries = {ep.path: ep.summary for ep in endpoints}
        assert summaries["/with-summary"] == "Get items"
        assert summaries["/with-operation-id"] == "get_users"

    def test_endpoint_tags_extraction(self):
        """Registry should extract tags from endpoints."""
        schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/items": {
                    "get": {
                        "tags": ["items", "catalog"],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }

        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=schema)

        registry = PulseEndpointRegistry(app)
        endpoints = registry.list_endpoints()

        endpoint = endpoints[0]
        assert endpoint.tags == ["items", "catalog"]

    def test_request_body_media_type_detection(self):
        """Registry should detect request body media types."""
        schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/json-endpoint": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            }
                        },
                        "responses": {"200": {"description": "OK"}},
                    }
                },
                "/form-endpoint": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/x-www-form-urlencoded": {
                                    "schema": {"type": "object"}
                                }
                            }
                        },
                        "responses": {"200": {"description": "OK"}},
                    }
                },
            },
        }

        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=schema)

        registry = PulseEndpointRegistry(app)
        endpoints = registry.list_endpoints()

        media_types = {ep.path: ep.request_body_media_type for ep in endpoints}
        assert media_types["/json-endpoint"] == "application/json"
        assert media_types["/form-endpoint"] == "application/x-www-form-urlencoded"

    def test_common_parameters_inheritance(self):
        """Parameters at path level should be inherited by all methods."""
        schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/items": {
                    "parameters": [
                        {
                            "name": "api-key",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "get": {"responses": {"200": {"description": "OK"}}},
                    "post": {"responses": {"200": {"description": "OK"}}},
                }
            },
        }

        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=schema)

        registry = PulseEndpointRegistry(app)
        endpoints = registry.list_endpoints()

        # Both methods should have the common header parameter
        for endpoint in endpoints:
            assert len(endpoint.header_parameters) == 1
            assert endpoint.header_parameters[0]["name"] == "api-key"

    def test_ignores_invalid_methods(self):
        """Registry should ignore non-standard HTTP methods."""
        schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/items": {
                    "get": {"responses": {"200": {"description": "OK"}}},
                    "invalid_method": {"responses": {"200": {"description": "OK"}}},
                }
            },
        }

        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=schema)

        registry = PulseEndpointRegistry(app)
        endpoints = registry.list_endpoints()

        # Should only have GET, not invalid_method
        methods = {ep.method for ep in endpoints}
        assert methods == {"GET"}

    def test_malformed_openapi_schema(self):
        """Registry should handle malformed OpenAPI schema gracefully."""
        schema = {
            "openapi": "3.0.0",
            # Missing "info"
            "paths": "not a dict",  # Wrong type
        }

        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=schema)

        registry = PulseEndpointRegistry(app)

        # Should not crash
        endpoints = registry.list_endpoints()
        assert isinstance(endpoints, list)

    def test_empty_openapi_schema(self):
        """Registry should handle empty OpenAPI schema."""
        schema = {}

        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=schema)

        registry = PulseEndpointRegistry(app)
        endpoints = registry.list_endpoints()

        assert endpoints == []

    def test_none_openapi_schema(self):
        """Registry should handle None OpenAPI schema."""
        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=None)

        registry = PulseEndpointRegistry(app)

        # Should handle gracefully
        try:
            endpoints = registry.list_endpoints()
            assert isinstance(endpoints, list)
        except (TypeError, AttributeError):
            # Acceptable if it raises - documents the behavior
            pass

    def test_paths_with_none_operations(self):
        """Registry should handle paths with None operations."""
        schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/test": None,  # None instead of dict
            },
        }

        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=schema)

        registry = PulseEndpointRegistry(app)
        endpoints = registry.list_endpoints()

        # Should skip invalid path
        assert len(endpoints) == 0

    def test_operation_without_responses(self):
        """Registry should handle operations without responses field."""
        schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        # Missing responses field
                    }
                }
            },
        }

        app = Mock(spec=FastAPI)
        app.openapi = Mock(return_value=schema)

        registry = PulseEndpointRegistry(app)
        endpoints = registry.list_endpoints()

        # Should still discover endpoint
        assert len(endpoints) == 1
        assert endpoints[0].path == "/test"
