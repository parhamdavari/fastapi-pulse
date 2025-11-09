"""Additional coverage for PulseMiddleware."""

from __future__ import annotations

import pytest

from fastapi_pulse.middleware import PulseMiddleware


class StubMetrics:
    def __init__(self):
        self.calls = []

    def record_request(self, **kwargs):
        self.calls.append(kwargs)

    def get_metrics(self):
        return {"endpoint_metrics": {}}


@pytest.mark.asyncio
async def test_middleware_sends_empty_body_when_response_started():
    class FailingApp:
        async def __call__(self, scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            raise RuntimeError("boom")

    middleware = PulseMiddleware(FailingApp(), metrics=StubMetrics(), exclude_path_prefixes=())
    scope = {"type": "http", "method": "GET", "path": "/foo", "headers": []}
    messages = []

    async def receive():
        return {"type": "http.request"}

    async def send(message):
        messages.append(message)

    await middleware(scope, receive, send)
    assert messages[-1]["type"] == "http.response.body"
    assert messages[-1]["body"] == b""


@pytest.mark.asyncio
async def test_middleware_swallows_metric_and_logging_errors(monkeypatch):
    class SimpleApp:
        async def __call__(self, scope, receive, send):
            await send({"type": "http.response.start", "status": 500, "headers": []})
            await send({"type": "http.response.body", "body": b"oops", "more_body": False})

    class BadMetrics:
        def record_request(self, **_):
            raise RuntimeError("metrics failed")

        def get_metrics(self):
            return {"endpoint_metrics": {}}

    middleware = PulseMiddleware(SimpleApp(), metrics=BadMetrics(), exclude_path_prefixes=())
    def raise_alert(*args, **kwargs):
        raise RuntimeError("alert fail")

    def raise_sla(*args, **kwargs):
        raise RuntimeError("sla fail")

    monkeypatch.setattr(PulseMiddleware, "_log_performance_alert", raise_alert, raising=False)
    monkeypatch.setattr(PulseMiddleware, "_check_sla_violation", raise_sla, raising=False)

    scope = {"type": "http", "method": "GET", "path": "/err", "headers": []}

    async def receive():
        return {"type": "http.request"}

    async def send(message):
        return message

    await middleware(scope, receive, send)


def test_check_sla_violation_logs_warning(caplog):
    class Metrics:
        def get_metrics(self):
            return {
                "endpoint_metrics": {
                    "GET /slow": {
                        "p95_response_time": 500,
                    }
                }
            }

    middleware = PulseMiddleware(lambda *args, **kwargs: None, metrics=Metrics(), exclude_path_prefixes=())
    caplog.set_level("WARNING")
    middleware._check_sla_violation("GET", "/slow", "cid")
    assert "SLA violation detected" in caplog.text
