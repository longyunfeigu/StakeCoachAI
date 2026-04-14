# input: FastAPI test app, stubbed PersonaBuilderService
# output: Story 2.5 POST /persona/build SSE endpoint验收测试
# owner: wanhua.gu
# pos: 测试层 - Story 2.5 persona build SSE API 验收测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""API tests for Story 2.5: POST /api/v1/stakeholder/persona/build (SSE).

Strategy: stub get_persona_builder_service with a fake service whose build()
yields a configurable sequence of BuildEvents. Heartbeat is exercised by
slowing emission. Disconnect behaviour verified by inspecting whether the
producer task continued after the client closed.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Callable, Optional

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.dependencies import get_persona_builder_service
from api.routes.stakeholder import router
from application.services.stakeholder.build_events import (
    BUILD_ADVERSARIALIZE_DONE,
    BUILD_ADVERSARIALIZE_START,
    BUILD_AGENT_TOOL_USE,
    BUILD_PARSE_DONE,
    BUILD_PERSIST_DONE,
    BUILD_WORKSPACE_READY,
    BuildEvent,
)
from core.exceptions import register_exception_handlers


# ---------------------------------------------------------------------------
# Stub PersonaBuilderService
# ---------------------------------------------------------------------------


class _StubBuilder:
    """Yields a configurable BuildEvent sequence."""

    def __init__(
        self,
        *,
        events: Optional[list[BuildEvent]] = None,
        delay_between_s: float = 0.0,
        raise_after: Optional[int] = None,
        on_complete: Optional[Callable[[], None]] = None,
    ):
        self.events = events or _happy_path_events()
        self.delay_between_s = delay_between_s
        self.raise_after = raise_after
        self.on_complete = on_complete
        self.calls: list[dict] = []
        self.completed = False

    async def build(
        self,
        *,
        user_id,
        materials,
        name=None,
        role=None,
        target_persona_id=None,
    ) -> AsyncIterator[BuildEvent]:
        self.calls.append(
            {
                "user_id": user_id,
                "materials": materials,
                "name": name,
                "role": role,
                "target_persona_id": target_persona_id,
            }
        )
        for i, ev in enumerate(self.events):
            if self.raise_after is not None and i >= self.raise_after:
                raise RuntimeError("simulated failure mid-build")
            if self.delay_between_s:
                await asyncio.sleep(self.delay_between_s)
            yield ev
        self.completed = True
        if self.on_complete:
            self.on_complete()


def _happy_path_events() -> list[BuildEvent]:
    return [
        BuildEvent(seq=1, type=BUILD_WORKSPACE_READY, ts=1.0, data={"workspace_path": "/tmp/x"}),
        BuildEvent(
            seq=2, type=BUILD_AGENT_TOOL_USE, ts=2.0, data={"tool_uses": [{"name": "Read"}]}
        ),
        BuildEvent(seq=3, type=BUILD_PARSE_DONE, ts=3.0, data={"persona_id": "p1", "claims": 5}),
        BuildEvent(seq=4, type=BUILD_ADVERSARIALIZE_START, ts=4.0, data={}),
        BuildEvent(seq=5, type=BUILD_ADVERSARIALIZE_DONE, ts=5.0, data={"hostile_applied": True}),
        BuildEvent(
            seq=6,
            type=BUILD_PERSIST_DONE,
            ts=6.0,
            data={"persona_id": "p1", "hostile_applied": True, "from_cache": False},
        ),
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_app():
    """Factory: build FastAPI app with overrideable persona builder service."""

    def _make(stub: _StubBuilder) -> FastAPI:
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[get_persona_builder_service] = lambda: stub
        return app

    return _make


async def _consume_sse(client: AsyncClient, body: dict) -> tuple[int, list[dict]]:
    """POST to /persona/build, parse SSE data lines into envelopes."""
    events: list[dict] = []
    async with client.stream(
        "POST",
        "/api/v1/stakeholder/persona/build",
        json=body,
    ) as resp:
        if resp.status_code != 200:
            await resp.aread()
            return resp.status_code, []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: ") :]))
        return resp.status_code, events


# ---------------------------------------------------------------------------
# AC1 + AC2 + AC3: 200, content-type, full event sequence, seq monotonic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_sse_response(make_app):
    stub = _StubBuilder()
    app = make_app(stub)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        async with client.stream(
            "POST",
            "/api/v1/stakeholder/persona/build",
            json={"materials": ["hello"]},
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            events = []
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[len("data: ") :]))

    types = [e["type"] for e in events]
    assert types == [
        BUILD_WORKSPACE_READY,
        BUILD_AGENT_TOOL_USE,
        BUILD_PARSE_DONE,
        BUILD_ADVERSARIALIZE_START,
        BUILD_ADVERSARIALIZE_DONE,
        BUILD_PERSIST_DONE,
    ]
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)
    for ev in events:
        assert {"seq", "type", "ts", "data"} == set(ev.keys())


# ---------------------------------------------------------------------------
# AC4: heartbeat after idle gap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_emitted_during_idle(monkeypatch, make_app):
    # Speed up the heartbeat for testability
    import api.routes.stakeholder as routes_mod

    monkeypatch.setattr(routes_mod, "_PERSONA_BUILD_HEARTBEAT_S", 0.05)

    stub = _StubBuilder(delay_between_s=0.12)  # > heartbeat → at least 1 hb between events
    app = make_app(stub)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        _, events = await _consume_sse(client, {"materials": ["x"]})

    types = [e["type"] for e in events]
    assert "heartbeat" in types
    # workspace_ready must still arrive before persist_done
    assert types.index(BUILD_WORKSPACE_READY) < types.index(BUILD_PERSIST_DONE)


# ---------------------------------------------------------------------------
# AC6: materials > 400k chars → 413 + MATERIAL_TOO_LARGE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_material_too_large_413(make_app):
    stub = _StubBuilder()
    app = make_app(stub)
    huge = "x" * (400_001)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post(
            "/api/v1/stakeholder/persona/build",
            json={"materials": [huge]},
        )
    assert resp.status_code == 413
    body = resp.json()
    # Wrapped by global exception handler; assert code present somewhere
    detail = body.get("detail") or body.get("data") or body
    assert "MATERIAL_TOO_LARGE" in json.dumps(detail)
    assert stub.calls == []  # builder was not invoked


# ---------------------------------------------------------------------------
# AC7: empty materials → 400 + MATERIAL_EMPTY
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_material_empty_400(make_app):
    stub = _StubBuilder()
    app = make_app(stub)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        # All-whitespace strings considered empty
        resp = await client.post(
            "/api/v1/stakeholder/persona/build",
            json={"materials": ["   ", "\n\n"]},
        )
    assert resp.status_code == 400
    body = resp.json()
    detail = body.get("detail") or body.get("data") or body
    assert "MATERIAL_EMPTY" in json.dumps(detail)
    assert stub.calls == []


@pytest.mark.asyncio
async def test_materials_zero_length_422(make_app):
    """Pydantic min_length=1 → 422 before reaching our hand-written check."""
    stub = _StubBuilder()
    app = make_app(stub)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post(
            "/api/v1/stakeholder/persona/build",
            json={"materials": []},
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# AC8: error event on internal failure + stream closes cleanly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_internal_error_emits_error_event(make_app):
    # Producer raises after 2 events without yielding the service's own error
    stub = _StubBuilder(raise_after=2)
    app = make_app(stub)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        _, events = await _consume_sse(client, {"materials": ["abc"]})

    types = [e["type"] for e in events]
    # At least one error event
    assert "error" in types
    # error has error_code
    err = next(e for e in events if e["type"] == "error")
    assert err["data"].get("error_code") == "BUILD_FAILED"


# ---------------------------------------------------------------------------
# AC9: client disconnect → builder runs to completion in background
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_disconnect_lets_builder_finish(make_app):
    """If client closes the stream early, producer task should still run to completion.

    Verified by checking that ``stub.completed`` becomes True after the client
    disconnects partway through.
    """
    stub = _StubBuilder(delay_between_s=0.05)
    app = make_app(stub)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        async with client.stream(
            "POST",
            "/api/v1/stakeholder/persona/build",
            json={"materials": ["disconnect-test"]},
        ) as resp:
            # Read just one event then break (simulating client disconnect)
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    break

    # Give the background producer time to drain remaining 5 events
    for _ in range(50):
        if stub.completed:
            break
        await asyncio.sleep(0.05)
    assert stub.completed is True


# ---------------------------------------------------------------------------
# Body forwarding: materials/name/role/target_persona_id are passed through
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_body_forwarded(make_app):
    stub = _StubBuilder()
    app = make_app(stub)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        await _consume_sse(
            client,
            {
                "materials": ["m1", "m2"],
                "name": "Boss",
                "role": "CEO",
                "target_persona_id": "boss-1",
            },
        )

    assert len(stub.calls) == 1
    call = stub.calls[0]
    assert call["materials"] == ["m1", "m2"]
    assert call["name"] == "Boss"
    assert call["role"] == "CEO"
    assert call["target_persona_id"] == "boss-1"
    assert call["user_id"] == "anonymous"
