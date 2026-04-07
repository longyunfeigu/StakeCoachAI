# input: FastAPI test app, StakeholderChatService, stubs
# output: Story 2.2 message API endpoint tests
# owner: wanhua.gu
# pos: 测试层 - Story 2.2 消息 API 路由验收测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""API tests for Story 2.2: POST /rooms/{id}/messages endpoint."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.dependencies import get_chatroom_service
from api.routes.stakeholder import router
from application.ports.llm import LLMResponse
from application.services.stakeholder.chatroom_service import ChatRoomApplicationService
from core.exceptions import register_exception_handlers
from infrastructure.models.base import Base
from infrastructure.unit_of_work import SQLAlchemyUnitOfWork


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


@dataclass
class _FakePersona:
    id: str = "jianfeng"
    name: str = "剑锋"
    role: str = "CTO"
    avatar_color: str = "#f00"
    full_content: str = "# 剑锋\nCTO persona."
    profile_summary: str = "CTO"
    parse_status: str = "ok"


class _StubPersonaLoader:
    _personas = {"jianfeng": _FakePersona(), "robin": _FakePersona(id="robin", name="Robin")}

    def get_persona(self, pid):
        return self._personas.get(pid)

    def list_personas(self):
        return list(self._personas.values())


class _FakeLLM:
    async def generate(self, messages, **kwargs) -> LLMResponse:
        return LLMResponse(
            content="I hear you.",
            model="fake",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            finish_reason="end_turn",
        )

    async def stream(self, messages, **kwargs):
        from application.ports.llm import LLMChunk

        yield LLMChunk(content="I hear you.")
        yield LLMChunk(content="", finish_reason="end_turn")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def client(session_factory):
    stub_loader = _StubPersonaLoader()
    fake_llm = _FakeLLM()

    def _uow(**kwargs):
        return SQLAlchemyUnitOfWork(session_factory=session_factory, **kwargs)

    room_svc = ChatRoomApplicationService(uow_factory=_uow, persona_loader=stub_loader)

    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )

    chat_svc = StakeholderChatService(uow_factory=_uow, persona_loader=stub_loader, llm=fake_llm)

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    from api.dependencies import get_stakeholder_chat_service

    app.dependency_overrides[get_chatroom_service] = lambda: room_svc
    app.dependency_overrides[get_stakeholder_chat_service] = lambda: chat_svc

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create a room first
        await ac.post(
            "/api/v1/stakeholder/rooms",
            json={"name": "Test Room", "type": "private", "persona_ids": ["jianfeng"]},
        )
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# AC1: POST messages → 201 user message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message(client: AsyncClient):
    resp = await client.post(
        "/api/v1/stakeholder/rooms/1/messages",
        json={"content": "Hello, what do you think?"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["sender_type"] == "user"
    assert data["content"] == "Hello, what do you think?"


# ---------------------------------------------------------------------------
# AC2: After send, room has persona reply
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_triggers_persona_reply(client: AsyncClient):
    await client.post(
        "/api/v1/stakeholder/rooms/1/messages",
        json={"content": "Tell me about the plan."},
    )
    # Get room detail — should have user msg + persona reply
    resp = await client.get("/api/v1/stakeholder/rooms/1")
    assert resp.status_code == 200
    messages = resp.json()["data"]["messages"]
    assert len(messages) >= 2
    persona_msgs = [m for m in messages if m["sender_type"] == "persona"]
    assert len(persona_msgs) >= 1


# ---------------------------------------------------------------------------
# AC: Send to nonexistent room → 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_room_not_found(client: AsyncClient):
    resp = await client.post(
        "/api/v1/stakeholder/rooms/99999/messages",
        json={"content": "Hello"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AC: Empty content → 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_empty_message(client: AsyncClient):
    resp = await client.post(
        "/api/v1/stakeholder/rooms/1/messages",
        json={"content": ""},
    )
    assert resp.status_code == 422
