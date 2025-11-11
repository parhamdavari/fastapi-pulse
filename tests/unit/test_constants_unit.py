"""Unit tests for the constants module."""

import pytest

from fastapi_pulse.constants import (
    PULSE_STATE_KEY,
    PULSE_ENDPOINT_REGISTRY_KEY,
    PULSE_PROBE_MANAGER_KEY,
    PULSE_PAYLOAD_STORE_KEY,
    DEFAULT_PAYLOAD_CONFIG_FILENAME,
)


pytestmark = pytest.mark.unit


class TestConstants:
    """Unit tests for module constants."""

    def test_pulse_state_key_is_string(self):
        """PULSE_STATE_KEY should be a string."""
        assert isinstance(PULSE_STATE_KEY, str)
        assert len(PULSE_STATE_KEY) > 0

    def test_endpoint_registry_key_is_string(self):
        """PULSE_ENDPOINT_REGISTRY_KEY should be a string."""
        assert isinstance(PULSE_ENDPOINT_REGISTRY_KEY, str)
        assert len(PULSE_ENDPOINT_REGISTRY_KEY) > 0

    def test_probe_manager_key_is_string(self):
        """PULSE_PROBE_MANAGER_KEY should be a string."""
        assert isinstance(PULSE_PROBE_MANAGER_KEY, str)
        assert len(PULSE_PROBE_MANAGER_KEY) > 0

    def test_payload_store_key_is_string(self):
        """PULSE_PAYLOAD_STORE_KEY should be a string."""
        assert isinstance(PULSE_PAYLOAD_STORE_KEY, str)
        assert len(PULSE_PAYLOAD_STORE_KEY) > 0

    def test_default_payload_filename_is_string(self):
        """DEFAULT_PAYLOAD_CONFIG_FILENAME should be a string."""
        assert isinstance(DEFAULT_PAYLOAD_CONFIG_FILENAME, str)
        assert len(DEFAULT_PAYLOAD_CONFIG_FILENAME) > 0

    def test_all_keys_are_unique(self):
        """All state keys should be unique."""
        keys = [
            PULSE_STATE_KEY,
            PULSE_ENDPOINT_REGISTRY_KEY,
            PULSE_PROBE_MANAGER_KEY,
            PULSE_PAYLOAD_STORE_KEY,
        ]

        assert len(keys) == len(set(keys))

    def test_keys_follow_naming_convention(self):
        """State keys should follow fastapi_pulse_ naming convention."""
        keys = [
            PULSE_STATE_KEY,
            PULSE_ENDPOINT_REGISTRY_KEY,
            PULSE_PROBE_MANAGER_KEY,
            PULSE_PAYLOAD_STORE_KEY,
        ]

        for key in keys:
            assert key.startswith("fastapi_pulse_")

    def test_filename_has_json_extension(self):
        """DEFAULT_PAYLOAD_CONFIG_FILENAME should be a JSON file."""
        assert DEFAULT_PAYLOAD_CONFIG_FILENAME.endswith(".json")

    def test_constants_are_not_empty_strings(self):
        """No constant should be an empty string."""
        constants = [
            PULSE_STATE_KEY,
            PULSE_ENDPOINT_REGISTRY_KEY,
            PULSE_PROBE_MANAGER_KEY,
            PULSE_PAYLOAD_STORE_KEY,
            DEFAULT_PAYLOAD_CONFIG_FILENAME,
        ]

        for constant in constants:
            assert constant.strip() != ""

    def test_constants_contain_no_special_characters(self):
        """State key constants should only contain alphanumeric and underscore."""
        keys = [
            PULSE_STATE_KEY,
            PULSE_ENDPOINT_REGISTRY_KEY,
            PULSE_PROBE_MANAGER_KEY,
            PULSE_PAYLOAD_STORE_KEY,
        ]

        for key in keys:
            assert key.replace("_", "").isalnum()
