"""Coverage for PulsePayloadStore edge cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from fastapi_pulse.payload_store import PulsePayloadStore


def test_load_handles_missing_and_corrupt_file(tmp_path: Path):
    store_path = tmp_path / "payloads.json"
    PulsePayloadStore(store_path)  # Missing file path exercises early return

    store_path.write_text("{broken json", encoding="utf-8")
    store = PulsePayloadStore(store_path)
    assert store.all() == {}


def test_set_validates_endpoint_format(tmp_path: Path):
    store = PulsePayloadStore(tmp_path / "payloads.json")
    with pytest.raises(ValueError):
        store.set("invalid", {})


def test_set_rejects_large_payload(monkeypatch, tmp_path: Path):
    store = PulsePayloadStore(tmp_path / "payloads.json")
    monkeypatch.setattr("fastapi_pulse.payload_store.MAX_PAYLOAD_SIZE_BYTES", 10)

    with pytest.raises(ValueError):
        store.set("GET /ok", {"body": "x" * 100})


def test_set_rejects_when_storage_limit_exceeded(monkeypatch, tmp_path: Path):
    store_path = tmp_path / "payloads.json"
    store_path.write_text("{}", encoding="utf-8")
    store = PulsePayloadStore(store_path)

    monkeypatch.setattr("fastapi_pulse.payload_store.MAX_TOTAL_STORAGE_BYTES", 1)
    store_path.write_text("x" * 20, encoding="utf-8")

    with pytest.raises(ValueError):
        store.set("GET /foo", {"body": None})


def test_all_returns_copy(tmp_path: Path):
    store = PulsePayloadStore(tmp_path / "payloads.json")
    store.set("GET /foo", {"body": {"value": 1}})
    snapshot = store.all()
    snapshot["GET /foo"] = {"body": {"value": 999}}
    snapshot["GET /bar"] = {"body": {"value": 1}}
    assert store.get("GET /foo")["body"]["value"] == 1
    assert store.get("GET /bar") is None
