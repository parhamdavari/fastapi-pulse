"""Extra CLI command coverage tests."""

from __future__ import annotations

import types
import sys

import pytest
from click.testing import CliRunner

from fastapi_pulse.cli import commands


def test_check_uses_config_file_and_watch_mode(monkeypatch, tmp_path):
    cfg = tmp_path / "pulse.yaml"
    cfg.write_text(
        "\n".join(
            [
                "base_url: http://config",
                "timeout: 5",
                "concurrency: 7",
                "endpoints:",
                "  include:",
                "    - GET /from-config",
            ]
        ),
        encoding="utf-8",
    )

    called = {}

    def fake_watch(base_url, timeout, headers, concurrency, endpoints, fmt, interval, fail_on_error, asgi_app):
        called["base_url"] = base_url
        called["timeout"] = timeout
        called["endpoints"] = endpoints
        raise SystemExit(0)

    monkeypatch.setattr(commands, "_run_watch_mode", fake_watch)

    runner = CliRunner()
    result = runner.invoke(
        commands.check,
        ["http://cli", "--config", str(cfg), "--watch"],
    )
    assert result.exit_code == 0
    assert called["base_url"] == "http://cli"
    assert called["timeout"] == 5
    assert called["endpoints"] == ["GET /from-config"]


def test_check_handles_keyboard_interrupt(monkeypatch):
    runner = CliRunner()
    def fake_run(coro, *args, **kwargs):
        coro.close()
        raise KeyboardInterrupt()
    monkeypatch.setattr(commands.asyncio, "run", fake_run)
    result = runner.invoke(commands.check, ["http://test"])
    assert result.exit_code == 130
    assert "Interrupted by user" in result.output


def test_check_handles_generic_exception(monkeypatch):
    runner = CliRunner()
    def fake_run(coro, *args, **kwargs):
        coro.close()
        raise RuntimeError("boom")
    monkeypatch.setattr(commands.asyncio, "run", fake_run)
    result = runner.invoke(commands.check, ["http://test"])
    assert result.exit_code == 1
    assert "Error: boom" in result.output


def test_check_validates_asgi_app(monkeypatch):
    runner = CliRunner()
    result = runner.invoke(commands.check, ["http://test", "--asgi-app", "invalid.module:app"])
    assert result.exit_code != 0
    assert "Failed to load ASGI app" in result.output


def test_run_watch_mode_exits_on_failure(monkeypatch):
    def fake_run(coro, *args, **kwargs):
        coro.close()
        return 1
    monkeypatch.setattr(commands.asyncio, "run", fake_run)
    with pytest.raises(SystemExit) as excinfo:
        commands._run_watch_mode(
            base_url="http://test",
            timeout=1.0,
            headers={},
            concurrency=1,
            specific_endpoints=[],
            output_format="json",
            interval=1,
            fail_on_error=True,
        )
    assert excinfo.value.code == 1


def test_load_asgi_app_handles_coroutine_object(monkeypatch):
    module = types.ModuleType("tests.fake_asgi")

    async def factory():
        return "app"

    module.coro = factory()
    monkeypatch.setitem(sys.modules, "tests.fake_asgi", module)

    result = commands._load_asgi_app("tests.fake_asgi:coro")
    assert result == "app"


@pytest.mark.asyncio
async def test_run_probe_without_endpoints(monkeypatch, capsys):
    class EmptyClient:
        def __init__(self, **_):
            pass

        async def fetch_endpoints(self):
            return []

    monkeypatch.setattr(commands, "StandaloneProbeClient", EmptyClient)

    exit_code = await commands._run_probe(
        base_url="http://test",
        timeout=1.0,
        headers={},
        concurrency=1,
        specific_endpoints=[],
        output_format="json",
        fail_on_error=False,
    )
    captured = capsys.readouterr()
    assert "No endpoints to check" in captured.err
    assert exit_code == 1
