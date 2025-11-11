"""Unit tests for the SamplePayloadBuilder module."""

import datetime
import pytest
from unittest.mock import Mock

from fastapi_pulse.registry import EndpointInfo
from fastapi_pulse.sample_builder import SamplePayloadBuilder


pytestmark = pytest.mark.unit


class TestSamplePayloadBuilder:
    """Unit tests for SamplePayloadBuilder."""

    @pytest.fixture
    def builder(self, sample_openapi_schema):
        """Create a SamplePayloadBuilder instance."""
        return SamplePayloadBuilder(sample_openapi_schema)

    def test_builder_initialization(self, sample_openapi_schema):
        """Builder should initialize with OpenAPI schema."""
        builder = SamplePayloadBuilder(sample_openapi_schema)

        assert builder.openapi_schema == sample_openapi_schema
        assert builder.components == sample_openapi_schema["components"]

    def test_build_simple_get_endpoint(self, builder):
        """build() should generate payload for simple GET endpoint."""
        endpoint = EndpointInfo(
            id="GET /search",
            method="GET",
            path="/search",
            summary="Search",
            tags=[],
            requires_input=True,
            has_path_params=False,
            has_request_body=False,
            path_parameters=[],
            query_parameters=[
                {
                    "name": "q",
                    "in": "query",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ],
            header_parameters=[],
            request_body_media_type=None,
            request_body_schema=None,
        )

        payload = builder.build(endpoint)

        assert "query" in payload
        assert "q" in payload["query"]
        assert isinstance(payload["query"]["q"], str)

    def test_build_endpoint_with_path_params(self, builder):
        """build() should generate path parameters."""
        endpoint = EndpointInfo(
            id="GET /items/{item_id}",
            method="GET",
            path="/items/{item_id}",
            summary="Get Item",
            tags=[],
            requires_input=True,
            has_path_params=True,
            has_request_body=False,
            path_parameters=[
                {
                    "name": "item_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "integer"},
                }
            ],
            query_parameters=[],
            header_parameters=[],
            request_body_media_type=None,
            request_body_schema=None,
        )

        payload = builder.build(endpoint)

        assert "path_params" in payload
        assert "item_id" in payload["path_params"]
        assert payload["path_params"]["item_id"] == 1

    def test_build_endpoint_with_request_body(self, builder):
        """build() should generate request body from schema."""
        endpoint = EndpointInfo(
            id="PUT /items/{item_id}",
            method="PUT",
            path="/items/{item_id}",
            summary="Update Item",
            tags=[],
            requires_input=True,
            has_path_params=True,
            has_request_body=True,
            path_parameters=[
                {
                    "name": "item_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "integer"},
                }
            ],
            query_parameters=[],
            header_parameters=[],
            request_body_media_type="application/json",
            request_body_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": "number"},
                },
            },
        )

        payload = builder.build(endpoint)

        assert "body" in payload
        assert payload["body"]["name"] == "sample"
        assert payload["body"]["price"] == 1.0
        assert payload["media_type"] == "application/json"

    def test_value_from_schema_string_types(self, builder):
        """_value_from_schema() should generate appropriate string values."""
        test_cases = [
            ({"type": "string"}, "sample"),
            ({"type": "string", "format": "email"}, "user@example.com"),
            ({"type": "string", "format": "uuid"}, "00000000-0000-0000-0000-000000000000"),
        ]

        for schema, expected in test_cases:
            result = builder._value_from_schema(schema)
            assert result == expected

    def test_value_from_schema_date_formats(self, builder):
        """_value_from_schema() should generate date/datetime strings."""
        date_schema = {"type": "string", "format": "date"}
        datetime_schema = {"type": "string", "format": "date-time"}

        date_result = builder._value_from_schema(date_schema)
        datetime_result = builder._value_from_schema(datetime_schema)

        # Should be valid ISO format strings
        assert isinstance(date_result, str)
        assert isinstance(datetime_result, str)
        assert "Z" in datetime_result or "+" in datetime_result

    def test_value_from_schema_numeric_types(self, builder):
        """_value_from_schema() should generate numeric values."""
        test_cases = [
            ({"type": "integer"}, 1),
            ({"type": "number"}, 1.0),
            ({"type": "boolean"}, True),
        ]

        for schema, expected in test_cases:
            result = builder._value_from_schema(schema)
            assert result == expected
            assert type(result) == type(expected)

    def test_value_from_schema_array(self, builder):
        """_value_from_schema() should generate array values."""
        schema = {
            "type": "array",
            "items": {"type": "string"},
        }

        result = builder._value_from_schema(schema)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == "sample"

    def test_value_from_schema_object(self, builder):
        """_value_from_schema() should generate object values."""
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "active": {"type": "boolean"},
            },
        }

        result = builder._value_from_schema(schema)

        assert isinstance(result, dict)
        assert result["id"] == 1
        assert result["name"] == "sample"
        assert result["active"] is True

    def test_value_from_schema_with_default(self, builder):
        """_value_from_schema() should use default value when provided."""
        schema = {
            "type": "string",
            "default": "custom_default",
        }

        result = builder._value_from_schema(schema)

        assert result == "custom_default"

    def test_value_from_schema_with_example(self, builder):
        """_value_from_schema() should use example value when provided."""
        schema = {
            "type": "string",
            "example": "example_value",
        }

        result = builder._value_from_schema(schema)

        assert result == "example_value"

    def test_value_from_schema_with_enum(self, builder):
        """_value_from_schema() should use first enum value."""
        schema = {
            "type": "string",
            "enum": ["option1", "option2", "option3"],
        }

        result = builder._value_from_schema(schema)

        assert result == "option1"

    def test_value_from_schema_handles_ref(self, builder):
        """_value_from_schema() should resolve $ref references."""
        schema = {"$ref": "#/components/schemas/Item"}

        result = builder._value_from_schema(schema)

        assert isinstance(result, dict)
        assert "name" in result
        assert "price" in result

    def test_resolve_ref(self, builder):
        """_resolve_ref() should resolve schema references."""
        ref = "#/components/schemas/Item"

        result = builder._resolve_ref(ref)

        assert result == builder.openapi_schema["components"]["schemas"]["Item"]

    def test_resolve_ref_invalid_reference(self, builder):
        """_resolve_ref() should return empty dict for invalid references."""
        invalid_refs = [
            "#/components/schemas/NonExistent",
            "invalid_format",
            "",
        ]

        for ref in invalid_refs:
            result = builder._resolve_ref(ref)
            assert result == {}

    def test_value_from_schema_depth_limit(self, builder):
        """_value_from_schema() should respect depth limit to prevent infinite recursion."""
        # Create a circular reference scenario
        schema = {
            "type": "object",
            "properties": {
                "nested": {
                    "type": "object",
                    "properties": {
                        "deep": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}},
                        }
                    },
                }
            },
        }

        result = builder._value_from_schema(schema, depth=8)

        # At depth 8, should still return something
        assert isinstance(result, dict)

        # At depth 9 (exceeds limit), should return "sample"
        result_at_limit = builder._value_from_schema(schema, depth=9)
        assert result_at_limit == "sample"

    def test_value_from_schema_anyof(self, builder):
        """_value_from_schema() should handle anyOf by using first option."""
        schema = {
            "anyOf": [
                {"type": "string"},
                {"type": "integer"},
            ]
        }

        result = builder._value_from_schema(schema)

        assert result == "sample"

    def test_value_from_schema_oneof(self, builder):
        """_value_from_schema() should handle oneOf by using first option."""
        schema = {
            "oneOf": [
                {"type": "integer"},
                {"type": "string"},
            ]
        }

        result = builder._value_from_schema(schema)

        assert result == 1

    def test_value_from_schema_additional_properties(self, builder):
        """_value_from_schema() should handle additionalProperties."""
        schema = {
            "type": "object",
            "additionalProperties": {"type": "string"},
        }

        result = builder._value_from_schema(schema)

        assert isinstance(result, dict)
        assert "key" in result
        assert result["key"] == "sample"

    def test_value_for_parameter_with_example(self, builder):
        """_value_for_parameter() should use parameter example if available."""
        parameter = {
            "name": "test_param",
            "in": "query",
            "example": "custom_example",
            "schema": {"type": "string"},
        }

        result = builder._value_for_parameter(parameter)

        assert result == "custom_example"

    def test_value_for_parameter_with_content(self, builder):
        """_value_for_parameter() should handle parameters with content field."""
        parameter = {
            "name": "test_param",
            "in": "query",
            "content": {
                "application/json": {
                    "schema": {"type": "integer"}
                }
            },
        }

        result = builder._value_for_parameter(parameter)

        assert result == 1

    def test_build_with_header_parameters(self, builder):
        """build() should generate header parameters."""
        endpoint = EndpointInfo(
            id="GET /secure",
            method="GET",
            path="/secure",
            summary="Secure endpoint",
            tags=[],
            requires_input=False,
            has_path_params=False,
            has_request_body=False,
            path_parameters=[],
            query_parameters=[],
            header_parameters=[
                {
                    "name": "X-API-Key",
                    "in": "header",
                    "schema": {"type": "string"},
                }
            ],
            request_body_media_type=None,
            request_body_schema=None,
        )

        payload = builder.build(endpoint)

        assert "headers" in payload
        assert "X-API-Key" in payload["headers"]

    def test_build_complex_nested_schema(self, builder):
        """build() should handle complex nested schemas."""
        endpoint = EndpointInfo(
            id="POST /complex",
            method="POST",
            path="/complex",
            summary="Complex endpoint",
            tags=[],
            requires_input=True,
            has_path_params=False,
            has_request_body=True,
            path_parameters=[],
            query_parameters=[],
            header_parameters=[],
            request_body_media_type="application/json",
            request_body_schema={
                "type": "object",
                "properties": {
                    "user": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                    "metadata": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                },
            },
        )

        payload = builder.build(endpoint)

        assert "body" in payload
        assert "user" in payload["body"]
        assert "name" in payload["body"]["user"]
        assert "tags" in payload["body"]["user"]
        assert isinstance(payload["body"]["user"]["tags"], list)
