"""Unit tests for the PulsePayloadStore module."""

import json
from pathlib import Path

import pytest

from fastapi_pulse.payload_store import PulsePayloadStore


pytestmark = pytest.mark.unit


class TestPulsePayloadStore:
    """Unit tests for PulsePayloadStore."""

    def test_store_initialization_creates_empty_store(self, temp_payload_file):
        """Store should initialize with empty payloads if file doesn't exist."""
        store = PulsePayloadStore(temp_payload_file)

        assert store._payloads == {}
        assert store.all() == {}

    def test_store_loads_existing_file(self, temp_payload_file):
        """Store should load existing payload file on initialization."""
        # Create a file with some data
        existing_data = {
            "GET /test": {
                "path_params": {},
                "query": {"id": "123"},
                "headers": {},
                "body": None,
                "media_type": None,
            }
        }

        temp_payload_file.write_text(json.dumps(existing_data))

        store = PulsePayloadStore(temp_payload_file)

        assert "GET /test" in store._payloads
        assert store.get("GET /test")["query"] == {"id": "123"}

    def test_get_returns_none_for_missing_endpoint(self, temp_payload_file):
        """get() should return None for non-existent endpoint."""
        store = PulsePayloadStore(temp_payload_file)

        result = store.get("GET /nonexistent")

        assert result is None

    def test_set_saves_payload(self, temp_payload_file):
        """set() should save payload and persist to disk."""
        store = PulsePayloadStore(temp_payload_file)

        payload = {
            "path_params": {"id": "123"},
            "query": {"expand": "true"},
            "headers": {"x-api-key": "secret"},
            "body": {"name": "test"},
            "media_type": "application/json",
        }

        result = store.set("POST /items", payload)

        assert result == payload
        assert store.get("POST /items") == payload
        # Verify file was written
        assert temp_payload_file.exists()

    def test_set_sanitizes_payload(self, temp_payload_file):
        """set() should sanitize payload to include only expected fields."""
        store = PulsePayloadStore(temp_payload_file)

        payload = {
            "path_params": {"id": "123"},
            "query": {"page": 1},
            "headers": {},
            "body": {"data": "value"},
            "media_type": "application/json",
            "extra_field": "should_be_removed",  # Extra field
        }

        result = store.set("GET /test", payload)

        # Extra field should not be in result
        assert "extra_field" not in result
        # Standard fields should be present
        assert "path_params" in result
        assert "query" in result

    def test_delete_removes_payload(self, temp_payload_file):
        """delete() should remove payload from store and persist."""
        store = PulsePayloadStore(temp_payload_file)

        payload = {
            "path_params": {},
            "query": {},
            "headers": {},
            "body": None,
            "media_type": None,
        }

        store.set("GET /test", payload)
        assert store.get("GET /test") is not None

        store.delete("GET /test")

        assert store.get("GET /test") is None

    def test_delete_idempotent_for_missing_endpoint(self, temp_payload_file):
        """delete() should not fail when endpoint doesn't exist."""
        store = PulsePayloadStore(temp_payload_file)

        # Should not raise exception
        store.delete("GET /nonexistent")

    def test_all_returns_all_payloads(self, temp_payload_file):
        """all() should return dictionary of all stored payloads."""
        store = PulsePayloadStore(temp_payload_file)

        payload1 = {
            "path_params": {},
            "query": {},
            "headers": {},
            "body": None,
            "media_type": None,
        }
        payload2 = {
            "path_params": {"id": "456"},
            "query": {},
            "headers": {},
            "body": None,
            "media_type": None,
        }

        store.set("GET /test1", payload1)
        store.set("GET /test2", payload2)

        all_payloads = store.all()

        assert len(all_payloads) == 2
        assert "GET /test1" in all_payloads
        assert "GET /test2" in all_payloads

    def test_flush_creates_parent_directory(self, temp_dir):
        """_flush() should create parent directories if they don't exist."""
        nested_path = temp_dir / "config" / "subdir" / "payloads.json"

        store = PulsePayloadStore(nested_path)
        store.set("GET /test", {
            "path_params": {},
            "query": {},
            "headers": {},
            "body": None,
            "media_type": None,
        })

        assert nested_path.exists()
        assert nested_path.parent.exists()

    def test_flush_uses_atomic_write(self, temp_payload_file):
        """_flush() should use atomic write with temp file."""
        store = PulsePayloadStore(temp_payload_file)

        store.set("GET /test", {
            "path_params": {},
            "query": {},
            "headers": {},
            "body": None,
            "media_type": None,
        })

        # Temp file should not exist after successful write
        tmp_path = temp_payload_file.with_suffix(".tmp")
        assert not tmp_path.exists()

        # Main file should exist
        assert temp_payload_file.exists()

    def test_load_handles_corrupted_file(self, temp_payload_file):
        """_load() should handle corrupted JSON gracefully."""
        # Write invalid JSON
        temp_payload_file.write_text("{ invalid json }")

        # Should not raise exception
        store = PulsePayloadStore(temp_payload_file)

        # Should start with empty payloads
        assert store._payloads == {}

    def test_load_handles_non_dict_json(self, temp_payload_file):
        """_load() should handle non-dict JSON gracefully."""
        # Write JSON array instead of object
        temp_payload_file.write_text("[]")

        store = PulsePayloadStore(temp_payload_file)

        # Should start with empty payloads
        assert store._payloads == {}

    def test_sanitize_payload_handles_missing_fields(self, temp_payload_file):
        """_sanitize_payload() should handle payloads with missing fields."""
        store = PulsePayloadStore(temp_payload_file)

        # Minimal payload
        payload = {"body": {"test": "data"}}

        result = store.set("POST /test", payload)

        # Should have all required fields with defaults
        assert "path_params" in result
        assert "query" in result
        assert "headers" in result
        assert result["body"] == {"test": "data"}

    def test_sanitize_payload_preserves_none_body(self, temp_payload_file):
        """_sanitize_payload() should preserve None body correctly."""
        store = PulsePayloadStore(temp_payload_file)

        payload = {"body": None}

        result = store.set("GET /test", payload)

        # body should be None, not {}
        assert result["body"] is None

    def test_concurrent_access_safety(self, temp_payload_file):
        """Store should handle concurrent access safely with locking."""
        import threading

        store = PulsePayloadStore(temp_payload_file)

        def write_payload(endpoint_id, value):
            payload = {
                "path_params": {},
                "query": {"value": value},
                "headers": {},
                "body": None,
                "media_type": None,
            }
            store.set(endpoint_id, payload)

        threads = []
        for i in range(10):
            thread = threading.Thread(
                target=write_payload,
                args=(f"GET /endpoint{i}", str(i))
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All payloads should be saved
        assert len(store.all()) == 10

    def test_file_persists_across_instances(self, temp_payload_file):
        """Data should persist when creating new store instances."""
        # First instance
        store1 = PulsePayloadStore(temp_payload_file)
        store1.set("GET /test", {
            "path_params": {},
            "query": {"page": "1"},
            "headers": {},
            "body": None,
            "media_type": None,
        })

        # Second instance (should load from file)
        store2 = PulsePayloadStore(temp_payload_file)

        result = store2.get("GET /test")
        assert result is not None
        assert result["query"] == {"page": "1"}

    def test_empty_values_preserved(self, temp_payload_file):
        """Empty dicts and None should be preserved correctly."""
        store = PulsePayloadStore(temp_payload_file)

        payload = {
            "path_params": {},
            "query": {},
            "headers": {},
            "body": None,
            "media_type": None,
        }

        result = store.set("GET /test", payload)

        assert result["path_params"] == {}
        assert result["query"] == {}
        assert result["headers"] == {}
        assert result["body"] is None
        assert result["media_type"] is None
