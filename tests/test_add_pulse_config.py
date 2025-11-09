"""Tests that exercise rarely used branches in add_pulse."""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi import FastAPI

from fastapi_pulse import add_pulse


def _get_cors_middleware(app: FastAPI):
    for middleware in app.user_middleware:
        if middleware.cls.__name__ == "CORSMiddleware":
            return middleware
    raise AssertionError("CORS middleware not installed")


def test_add_pulse_respects_explicit_origins():
    app = FastAPI()
    add_pulse(app, cors_allowed_origins=["https://example.com"])
    middleware = _get_cors_middleware(app)
    assert "https://example.com" in middleware.kwargs["allow_origins"]


def test_add_pulse_reads_env_origins(monkeypatch):
    app = FastAPI()
    monkeypatch.setenv("PULSE_ALLOWED_ORIGINS", "https://foo.test, https://bar.test")
    add_pulse(app)
    middleware = _get_cors_middleware(app)
    assert set(middleware.kwargs["allow_origins"]) == {"https://foo.test", "https://bar.test"}


def test_add_pulse_uses_importlib_files_when_available(monkeypatch, tmp_path):
    app = FastAPI()

    class DummyFiles:
        def __truediv__(self, item: str):
            assert item == "static"
            return tmp_path

    monkeypatch.setattr(importlib.resources, "files", lambda *_: DummyFiles(), raising=False)
    mounted = {}

    def fake_mount(route, static_files, name):
        mounted["directory"] = static_files.directory

    monkeypatch.setattr(app, "mount", fake_mount)
    add_pulse(app, enable_cors=False)
    assert mounted["directory"] == str(tmp_path)


def test_add_pulse_logs_when_mount_fails(monkeypatch, caplog):
    app = FastAPI()

    def boom(*args, **kwargs):
        raise RuntimeError("mount failed")

    monkeypatch.setattr(app, "mount", boom)
    caplog.set_level("WARNING")
    add_pulse(app, enable_cors=False)
    assert "Could not mount pulse dashboard" in caplog.text
