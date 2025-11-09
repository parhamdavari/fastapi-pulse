"""Additional coverage for CLI output formatters."""

from __future__ import annotations

import json

from fastapi_pulse.cli import output


def sample_results():
    return [
        {
            "endpoint_id": "GET /ok",
            "method": "GET",
            "path": "/ok",
            "status": "healthy",
            "status_code": 200,
            "latency_ms": 10.0,
            "error": None,
        },
        {
            "endpoint_id": "GET /warn",
            "method": "GET",
            "path": "/warn",
            "status": "warning",
            "status_code": 200,
            "latency_ms": 1500.0,
            "error": "slow",
        },
        {
            "endpoint_id": "GET /fail",
            "method": "GET",
            "path": "/fail",
            "status": "critical",
            "status_code": 500,
            "latency_ms": None,
            "error": "boom",
        },
    ]


def test_summary_formatter_includes_avg_latency():
    text = output.SummaryFormatter.format(sample_results())
    assert "Total:" in text
    assert "Avg latency" in text


def test_table_formatter_without_rich(monkeypatch):
    # Force fallback path
    monkeypatch.setattr(output, "RICH_AVAILABLE", False, raising=False)
    table = output.TableFormatter.format(sample_results())
    assert "Endpoint" in table
    assert "Summary:" in table


def test_json_formatter_roundtrip():
    raw = output.JSONFormatter.format(sample_results())
    payload = json.loads(raw)
    assert payload["summary"]["total"] == 3


def test_table_formatter_with_rich(monkeypatch):
    # Reload module to ensure RICH path is available
    monkeypatch.setattr(output, "RICH_AVAILABLE", True, raising=False)
    text = output.TableFormatter.format(sample_results())
    assert "Summary:" in text


def test_table_formatter_handles_skipped_status(monkeypatch):
    monkeypatch.setattr(output, "RICH_AVAILABLE", True, raising=False)
    results = sample_results() + [{
        "endpoint_id": "GET /skip",
        "method": "GET",
        "path": "/skip",
        "status": "skipped",
        "status_code": None,
        "latency_ms": None,
        "error": None,
    }]
    text = output.TableFormatter.format(results)
    assert "skipped" in text.lower()


def test_output_formatter_handles_missing_rich(monkeypatch):
    import builtins
    import importlib
    from fastapi_pulse.cli import output as output_module

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("rich"):
            raise ImportError("forced")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    module = importlib.reload(output_module)
    assert module.RICH_AVAILABLE is False
    monkeypatch.setattr("builtins.__import__", original_import)
    importlib.reload(output_module)
