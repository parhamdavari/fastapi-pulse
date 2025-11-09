"""Tests that exercise the less common branches in PulseProbeManager."""

from __future__ import annotations

import asyncio
import json

import pytest

from fastapi import FastAPI

from fastapi_pulse.metrics import PulseMetrics
from fastapi_pulse.probe import (
    EndpointInfo,
    ProbeJob,
    ProbeResult,
    PulseProbeManager,
)


def make_endpoint(path="/items", method="GET", **kwargs):
    return EndpointInfo(
        id=f"{method} {path}",
        method=method,
        path=path,
        summary=None,
        tags=[],
        requires_input=kwargs.get("requires_input", False),
        has_path_params=kwargs.get("has_path_params", False),
        has_request_body=kwargs.get("has_request_body", False),
        path_parameters=kwargs.get("path_parameters", []),
        query_parameters=[],
        header_parameters=[],
        request_body_media_type=kwargs.get("request_body_media_type"),
        request_body_schema=None,
    )


def make_manager(**overrides):
    app = FastAPI()
    metrics = PulseMetrics()
    registry = type("Registry", (), {"openapi_schema": {}})()
    payload_store = type(
        "Store",
        (),
        {
            "get": lambda self, key: None,
            "set": lambda self, key, value: value,
            "delete": lambda self, key: None,
        },
    )()
    return PulseProbeManager(
        app,
        metrics,
        registry=registry,
        payload_store=payload_store,
        **overrides,
    )


@pytest.mark.asyncio
async def test_start_probe_enforces_cooldown(monkeypatch):
    manager = make_manager(min_probe_interval=10)

    async def immediate(job, endpoints):
        job.status = "completed"
        if job._future and not job._future.done():
            job._future.set_result(job)

    monkeypatch.setattr(manager, "_run_job", immediate)
    endpoints = [make_endpoint()]
    manager.start_probe(endpoints)
    with pytest.raises(RuntimeError):
        manager.start_probe(endpoints)


@pytest.mark.asyncio
async def test_start_probe_limits_concurrent_jobs():
    manager = make_manager(max_concurrent_jobs=0)
    with pytest.raises(RuntimeError):
        manager.start_probe([make_endpoint()])


@pytest.mark.asyncio
async def test_wait_for_completion_unknown_job():
    manager = make_manager()
    with pytest.raises(KeyError):
        await manager.wait_for_completion("missing")


@pytest.mark.asyncio
async def test_run_job_handles_timeout(monkeypatch):
    manager = make_manager()
    job = ProbeJob(job_id="job")
    job._future = asyncio.get_running_loop().create_future()

    async def raise_timeout(*args, **kwargs):
        raise asyncio.TimeoutError

    monkeypatch.setattr(manager, "_run_with_timeout", raise_timeout)
    await manager._run_job(job, [])
    assert job.status == "timeout"
    assert job._future.done()


@pytest.mark.asyncio
async def test_run_job_handles_unexpected_exception(monkeypatch):
    manager = make_manager()
    job = ProbeJob(job_id="job")
    job._future = asyncio.get_running_loop().create_future()

    async def boom(*args, **kwargs):
        raise RuntimeError("fail")

    monkeypatch.setattr(manager, "_run_with_timeout", boom)
    await manager._run_job(job, [])
    assert job.status == "failed"
    assert job._future.done()


@pytest.mark.asyncio
async def test_run_with_timeout_prefers_asyncio_timeout(monkeypatch):
    manager = make_manager()
    called = {}

    class DummyTimeout:
        def __init__(self, value):
            called["value"] = value

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("fastapi_pulse.probe.asyncio.timeout", lambda value: DummyTimeout(value), raising=False)

    async def fake_execute(job, endpoints):
        called["ran"] = True

    monkeypatch.setattr(manager, "_execute_probe_batch", fake_execute)

    await manager._run_with_timeout(ProbeJob(job_id="job"), [])
    assert called["value"] == manager.job_timeout
    assert called["ran"]


def test_prepare_payload_respects_missing_body(monkeypatch):
    manager = make_manager()
    endpoint = make_endpoint(path="/needs", method="POST", has_request_body=True)

    monkeypatch.setattr(
        "fastapi_pulse.probe.SamplePayloadBuilder.build",
        lambda self, ep: {"path_params": {}, "query": {}, "headers": {}, "body": None},
    )
    assert manager._prepare_payload(endpoint) is None


def test_prepare_payload_respects_missing_path_params(monkeypatch):
    manager = make_manager()
    endpoint = make_endpoint(path="/needs/{id}", has_path_params=True, path_parameters=[{"name": "id"}])

    monkeypatch.setattr(
        "fastapi_pulse.probe.SamplePayloadBuilder.build",
        lambda self, ep: {"path_params": {"id": None}, "query": {}, "headers": {}, "body": None},
    )
    assert manager._prepare_payload(endpoint) is None


@pytest.mark.asyncio
async def test_probe_endpoint_skips_when_payload_missing(monkeypatch):
    manager = make_manager()
    endpoint = make_endpoint()
    job = ProbeJob(job_id="job")
    job.results = {endpoint.id: ProbeResult(endpoint_id=endpoint.id, method=endpoint.method, path=endpoint.path, status="queued")}

    monkeypatch.setattr(manager, "_prepare_payload", lambda ep: None)
    await manager._probe_endpoint(job, None, endpoint)
    assert job.results[endpoint.id].status == "skipped"


@pytest.mark.asyncio
async def test_probe_endpoint_handles_non_json_body(monkeypatch):
    manager = make_manager()
    endpoint = make_endpoint(method="POST", path="/text")
    job = ProbeJob(job_id="job")
    job.results = {endpoint.id: ProbeResult(endpoint_id=endpoint.id, method=endpoint.method, path=endpoint.path, status="queued")}

    payload = {
        "path_params": {},
        "query": {},
        "headers": {},
        "body": {"foo": "bar"},
        "media_type": "text/plain",
        "source": "custom",
    }
    monkeypatch.setattr(manager, "_prepare_payload", lambda ep: payload)

    captured = {}

    class StubResponse:
        status_code = 200
        text = ""

    class StubClient:
        async def request(self, method, path, **kwargs):
            captured["data"] = kwargs["data"]
            captured["content_type"] = kwargs["headers"]["content-type"]
            return StubResponse()

    await manager._probe_endpoint(job, StubClient(), endpoint)
    assert json.loads(captured["data"]) == {"foo": "bar"}
    assert captured["content_type"] == "text/plain"


@pytest.mark.asyncio
async def test_probe_endpoint_handles_raw_body(monkeypatch):
    manager = make_manager()
    endpoint = make_endpoint(method="POST", path="/raw")
    job = ProbeJob(job_id="job")
    job.results = {endpoint.id: ProbeResult(endpoint_id=endpoint.id, method=endpoint.method, path=endpoint.path, status="queued")}

    payload = {
        "path_params": {},
        "query": {},
        "headers": {},
        "body": "ping",
        "media_type": "text/plain",
        "source": "custom",
    }
    monkeypatch.setattr(manager, "_prepare_payload", lambda ep: payload)

    captured = {}

    class StubResponse:
        status_code = 200
        text = ""

    class StubClient:
        async def request(self, method, path, **kwargs):
            captured["data"] = kwargs["data"]
            captured["headers"] = kwargs["headers"]["content-type"]
            return StubResponse()

    await manager._probe_endpoint(job, StubClient(), endpoint)
    assert captured["data"] == "ping"
    assert captured["headers"] == "text/plain"


@pytest.mark.asyncio
async def test_probe_endpoint_marks_warning_for_slow_success(monkeypatch):
    manager = make_manager()
    endpoint = make_endpoint(path="/slow")
    job = ProbeJob(job_id="job")
    job.results = {endpoint.id: ProbeResult(endpoint_id=endpoint.id, method=endpoint.method, path=endpoint.path, status="queued")}

    monkeypatch.setattr(
        manager,
        "_prepare_payload",
        lambda ep: {"path_params": {}, "query": {}, "headers": {}, "body": None, "media_type": "application/json", "source": "generated"},
    )

    times = iter([0.0, 2.0])
    monkeypatch.setattr("fastapi_pulse.probe.time.perf_counter", lambda: next(times))

    class StubResponse:
        status_code = 200
        text = ""

    class StubClient:
        async def request(self, *args, **kwargs):
            return StubResponse()

    await manager._probe_endpoint(job, StubClient(), endpoint)
    assert job.results[endpoint.id].status == "warning"


@pytest.mark.asyncio
async def test_probe_endpoint_handles_request_exception(monkeypatch):
    manager = make_manager()
    endpoint = make_endpoint(path="/boom")
    job = ProbeJob(job_id="job")
    job.results = {endpoint.id: ProbeResult(endpoint_id=endpoint.id, method=endpoint.method, path=endpoint.path, status="queued")}

    monkeypatch.setattr(
        manager,
        "_prepare_payload",
        lambda ep: {"path_params": {}, "query": {}, "headers": {}, "body": None, "media_type": "application/json", "source": "generated"},
    )

    class StubClient:
        async def request(self, *args, **kwargs):
            raise RuntimeError("boom")

    await manager._probe_endpoint(job, StubClient(), endpoint)
    assert job.results[endpoint.id].status == "critical"
    assert job.results[endpoint.id].error == "boom"


@pytest.mark.asyncio
async def test_wait_for_completion_returns_job(monkeypatch):
    manager = make_manager()

    async def immediate(job, endpoints):
        job.status = "completed"
        if job._future and not job._future.done():
            job._future.set_result(job)

    monkeypatch.setattr(manager, "_run_job", immediate)
    job_id = manager.start_probe([make_endpoint()])
    job = await manager.wait_for_completion(job_id)
    assert job.job_id == job_id
