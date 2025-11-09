"""Unit tests for SamplePayloadBuilder to improve coverage."""

import datetime
import pytest
from fastapi_pulse.sample_builder import SamplePayloadBuilder
from fastapi_pulse.registry import EndpointInfo


def test_build_with_path_parameters():
    """Test building payload with path parameters."""
    schema = {
        "openapi": "3.0.0",
        "paths": {}
    }
    builder = SamplePayloadBuilder(schema)

    endpoint = EndpointInfo(
        id="GET /users/{id}",
        method="GET",
        path="/users/{id}",
        summary="Get user",
        tags=[],
        requires_input=False,
        has_path_params=True,
        has_request_body=False,
        path_parameters=[{"name": "id", "schema": {"type": "integer"}}],
        query_parameters=[],
        header_parameters=[],
        request_body_schema=None,
        request_body_media_type=None
    )

    payload = builder.build(endpoint)
    assert "path_params" in payload
    assert payload["path_params"]["id"] == 1


def test_build_with_query_parameters():
    """Test building payload with query parameters."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    endpoint = EndpointInfo(
        id="GET /search",
        method="GET",
        path="/search",
        summary="Search",
        tags=[],
        requires_input=False,
        has_path_params=False,
        has_request_body=False,
        path_parameters=[],
        query_parameters=[
            {"name": "q", "schema": {"type": "string"}},
            {"name": "limit", "schema": {"type": "integer"}}
        ],
        header_parameters=[],
        request_body_schema=None,
        request_body_media_type=None
    )

    payload = builder.build(endpoint)
    assert "query" in payload
    assert payload["query"]["q"] == "sample"
    assert payload["query"]["limit"] == 1


def test_build_with_headers():
    """Test building payload with headers."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    endpoint = EndpointInfo(
        id="GET /api/data",
        method="GET",
        path="/api/data",
        summary="Get data",
        tags=[],
        requires_input=False,
        has_path_params=False,
        has_request_body=False,
        path_parameters=[],
        query_parameters=[],
        header_parameters=[
            {"name": "X-API-Key", "schema": {"type": "string"}}
        ],
        request_body_schema=None,
        request_body_media_type=None
    )

    payload = builder.build(endpoint)
    assert "headers" in payload
    assert payload["headers"]["X-API-Key"] == "sample"


def test_build_with_request_body():
    """Test building payload with request body."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    endpoint = EndpointInfo(
        id="POST /users",
        method="POST",
        path="/users",
        summary="Create user",
        tags=[],
        requires_input=False,
        has_path_params=False,
        has_request_body=True,
        path_parameters=[],
        query_parameters=[],
        header_parameters=[],
        request_body_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            }
        },
        request_body_media_type="application/json"
    )

    payload = builder.build(endpoint)
    assert payload["body"] is not None
    assert payload["body"]["name"] == "sample"
    assert payload["body"]["age"] == 1
    assert payload["media_type"] == "application/json"


def test_value_for_parameter_with_example():
    """Test _value_for_parameter uses example if provided."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    param = {
        "name": "id",
        "example": 42,
        "schema": {"type": "integer"}
    }

    value = builder._value_for_parameter(param)
    assert value == 42


def test_value_for_parameter_with_content():
    """Test _value_for_parameter handles content parameter."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    param = {
        "name": "data",
        "content": {
            "application/json": {
                "schema": {"type": "string"}
            }
        }
    }

    value = builder._value_for_parameter(param)
    assert value == "sample"


def test_resolve_ref_valid():
    """Test _resolve_ref resolves valid $ref."""
    schema = {
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"}
                    }
                }
            }
        }
    }
    builder = SamplePayloadBuilder(schema)

    resolved = builder._resolve_ref("#/components/schemas/User")
    assert resolved["type"] == "object"
    assert "name" in resolved["properties"]


def test_resolve_ref_invalid():
    """Test _resolve_ref handles invalid $ref."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    resolved = builder._resolve_ref("#/components/schemas/NonExistent")
    assert resolved == {}


def test_resolve_ref_empty():
    """Test _resolve_ref handles empty ref."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    resolved = builder._resolve_ref("")
    assert resolved == {}


def test_value_from_schema_prefers_default_over_generated():
    """_value_from_schema should return the provided default."""
    builder = SamplePayloadBuilder({})
    result = builder._value_from_schema({"type": "integer", "default": 99})
    assert result == 99


@pytest.mark.parametrize(
    "fmt, assertion",
    [
        ("date-time", lambda v: v.endswith("Z") and "T" in v),
        ("date", lambda v: len(v.split("-")) == 3),
        ("email", lambda v: v == "user@example.com"),
        ("uuid", lambda v: v == "00000000-0000-0000-0000-000000000000"),
    ],
)
def test_value_from_schema_handles_string_formats(fmt, assertion):
    """String schemas should respect known formats."""
    builder = SamplePayloadBuilder({})
    value = builder._value_from_schema({"type": "string", "format": fmt})
    assert assertion(value)


def test_value_from_schema_handles_numeric_and_boolean_types():
    """Numeric and boolean schemas should map to sample primitives."""
    builder = SamplePayloadBuilder({})
    assert builder._value_from_schema({"type": "integer"}) == 1
    assert builder._value_from_schema({"type": "number"}) == pytest.approx(1.0)
    assert builder._value_from_schema({"type": "boolean"}) is True


def test_value_from_schema_handles_arrays_and_objects():
    """Arrays and objects should recurse into nested schemas."""
    builder = SamplePayloadBuilder({})
    array_schema = {"type": "array", "items": {"type": "integer"}}
    object_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "profile": {"type": "object", "properties": {"age": {"type": "integer"}}},
        },
    }
    assert builder._value_from_schema(array_schema) == [1]
    payload = builder._value_from_schema(object_schema)
    assert payload["name"] == "sample"
    assert payload["profile"]["age"] == 1


def test_value_from_schema_handles_additional_properties_only():
    """Objects with only additionalProperties should still produce a dict."""
    builder = SamplePayloadBuilder({})
    schema = {"type": "object", "additionalProperties": {"type": "boolean"}}
    assert builder._value_from_schema(schema)["key"] is True


def test_value_from_schema_handles_anyof_and_oneof():
    """Union-like schemas should evaluate the first option."""
    builder = SamplePayloadBuilder({})
    anyof_value = builder._value_from_schema({"anyOf": [{"type": "number"}]})
    oneof_value = builder._value_from_schema({"oneOf": [{"type": "boolean"}]})
    assert anyof_value == pytest.approx(1.0)
    assert oneof_value is True


def test_value_from_schema_handles_enum_and_depth_limits():
    """Ensure enums return the first entry and depth guard works."""
    builder = SamplePayloadBuilder({})
    assert builder._value_from_schema({"enum": ["first", "second"]}) == "first"
    assert builder._value_from_schema({"type": "string"}, depth=9) == "sample"


def test_resolve_ref_handles_non_dict_node():
    """_resolve_ref should return {} when path traverses non-dict structures."""
    schema = {"components": ["invalid"]}
    builder = SamplePayloadBuilder(schema)
    resolved = builder._resolve_ref("#/components/schemas/User")
    assert resolved == {}


def test_value_from_schema_prefers_example_without_default():
    """Ensure example values are used when provided."""
    builder = SamplePayloadBuilder({})
    assert builder._value_from_schema({"example": {"foo": "bar"}}) == {"foo": "bar"}


def test_value_from_schema_returns_sample_for_unknown_type():
    """Schemas with unknown types should fall back to 'sample'."""
    builder = SamplePayloadBuilder({})
    assert builder._value_from_schema({"type": "mystery"}) == "sample"


def test_value_from_schema_with_ref():
    """Test _value_from_schema resolves $ref."""
    schema = {
        "components": {
            "schemas": {
                "User": {
                    "type": "string"
                }
            }
        }
    }
    builder = SamplePayloadBuilder(schema)

    value = builder._value_from_schema({"$ref": "#/components/schemas/User"})
    assert value == "sample"


def test_value_from_schema_with_default():
    """Test _value_from_schema uses default value."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    value = builder._value_from_schema({"type": "string", "default": "default_value"})
    assert value == "default_value"


def test_value_from_schema_with_enum():
    """Test _value_from_schema uses first enum value."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    value = builder._value_from_schema({"type": "string", "enum": ["option1", "option2"]})
    assert value == "option1"


def test_value_from_schema_string_formats():
    """Test _value_from_schema handles string formats."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    # date-time format
    value = builder._value_from_schema({"type": "string", "format": "date-time"})
    assert "Z" in value

    # date format
    value = builder._value_from_schema({"type": "string", "format": "date"})
    assert "-" in value

    # email format
    value = builder._value_from_schema({"type": "string", "format": "email"})
    assert "@" in value

    # uuid format
    value = builder._value_from_schema({"type": "string", "format": "uuid"})
    assert value == "00000000-0000-0000-0000-000000000000"

    # default string
    value = builder._value_from_schema({"type": "string"})
    assert value == "sample"


def test_value_from_schema_primitive_types():
    """Test _value_from_schema handles primitive types."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    # integer
    value = builder._value_from_schema({"type": "integer"})
    assert value == 1

    # number
    value = builder._value_from_schema({"type": "number"})
    assert value == 1.0

    # boolean
    value = builder._value_from_schema({"type": "boolean"})
    assert value is True


def test_value_from_schema_array():
    """Test _value_from_schema handles array type."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    value = builder._value_from_schema({
        "type": "array",
        "items": {"type": "string"}
    })
    assert isinstance(value, list)
    assert len(value) == 1
    assert value[0] == "sample"


def test_value_from_schema_object():
    """Test _value_from_schema handles object type."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    value = builder._value_from_schema({
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"}
        }
    })
    assert isinstance(value, dict)
    assert value["name"] == "sample"
    assert value["age"] == 1


def test_value_from_schema_object_with_additional_properties():
    """Test _value_from_schema handles additionalProperties."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    value = builder._value_from_schema({
        "type": "object",
        "additionalProperties": {"type": "string"}
    })
    assert isinstance(value, dict)
    assert "key" in value
    assert value["key"] == "sample"


def test_value_from_schema_anyof():
    """Test _value_from_schema handles anyOf."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    value = builder._value_from_schema({
        "anyOf": [
            {"type": "string"},
            {"type": "integer"}
        ]
    })
    assert value == "sample"


def test_value_from_schema_oneof():
    """Test _value_from_schema handles oneOf."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    value = builder._value_from_schema({
        "oneOf": [
            {"type": "integer"},
            {"type": "string"}
        ]
    })
    assert value == 1


def test_value_from_schema_depth_limit():
    """Test _value_from_schema respects depth limit."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    # Create deeply nested schema
    value = builder._value_from_schema({
        "type": "object",
        "properties": {
            "level1": {
                "type": "object",
                "properties": {
                    "level2": {
                        "type": "object",
                        "properties": {
                            "level3": {"type": "string"}
                        }
                    }
                }
            }
        }
    }, depth=7)
    # At depth 7, should still work but at depth > 8 returns "sample"
    assert isinstance(value, dict)


def test_value_from_schema_none():
    """Test _value_from_schema handles None schema."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    value = builder._value_from_schema(None)
    assert value == "sample"


def test_value_from_schema_empty_dict():
    """Test _value_from_schema handles empty dict schema."""
    schema = {}
    builder = SamplePayloadBuilder(schema)

    value = builder._value_from_schema({})
    assert value == "sample"


def test_builder_with_none_schema():
    """Test SamplePayloadBuilder handles None openapi_schema."""
    builder = SamplePayloadBuilder(None)
    assert builder.openapi_schema == {}
    assert builder.components == {}
