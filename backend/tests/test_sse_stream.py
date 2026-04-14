# input: RoomEventBus, StakeholderChatService, FastAPI test app
# output: Story 2.3 SSE stream tests
# owner: wanhua.gu
# pos: 测试层 - Story 2.3 SSE 实时推送验收测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Story 2.3: SSE streaming endpoints and event flow."""

from __future__ import annotations

import asyncio
import json

import pytest

from application.services.stakeholder.sse import RoomEventBus, format_sse


# ---------------------------------------------------------------------------
# Unit tests: RoomEventBus
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    bus = RoomEventBus()
    queue = bus.subscribe(1)

    await bus.publish(1, "message", {"content": "hello"})

    event, data = await asyncio.wait_for(queue.get(), timeout=1)
    assert event == "message"
    assert data["content"] == "hello"

    bus.unsubscribe(1, queue)


@pytest.mark.asyncio
async def test_event_bus_no_cross_room():
    """Events for room 1 don't leak to room 2."""
    bus = RoomEventBus()
    q1 = bus.subscribe(1)
    q2 = bus.subscribe(2)

    await bus.publish(1, "message", {"x": 1})

    assert not q2.empty() is False or q2.qsize() == 0
    event, data = await asyncio.wait_for(q1.get(), timeout=1)
    assert data["x"] == 1

    bus.unsubscribe(1, q1)
    bus.unsubscribe(2, q2)


def test_format_sse():
    result = format_sse("typing", {"persona_id": "jianfeng", "status": "start"})
    assert result.startswith("event: typing\n")
    assert "persona_id" in result
    assert result.endswith("\n\n")


# ---------------------------------------------------------------------------
# Integration: SSE event sequence during send_message
# ---------------------------------------------------------------------------


from domain.stakeholder.persona_entity import (
    DecisionPattern,
    ExpressionStyle,
    HardRule,
    IdentityProfile,
    InterpersonalStyle,
    Persona,
)


def _make_persona(id: str, name: str, role: str = "CTO") -> Persona:
    return Persona(
        id=id,
        name=name,
        role=role,
        hard_rules=[HardRule(statement="test rule", severity="medium")],
        identity=IdentityProfile(background="bg", core_values=["v1"], hidden_agenda=None),
        expression=ExpressionStyle(
            tone="formal", catchphrases=["test"], interruption_tendency="low"
        ),
        decision=DecisionPattern(
            style="analytical", risk_tolerance="medium", typical_questions=["why?"]
        ),
        interpersonal=InterpersonalStyle(
            authority_mode="direct", triggers=["delay"], emotion_states=["neutral"]
        ),
    )


class FakePersonaLoader:
    def get_persona(self, pid):
        if pid == "jianfeng":
            return _make_persona("jianfeng", "剑锋")
        return None


class FakeLLM:
    async def generate(self, messages, **kwargs):
        from application.ports.llm import LLMResponse

        return LLMResponse(
            content="I agree.",
            model="fake",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            finish_reason="end_turn",
        )

    async def stream(self, messages, **kwargs):
        from application.ports.llm import LLMChunk

        yield LLMChunk(content="I agree.")
        yield LLMChunk(content="", finish_reason="end_turn")


class FailingLLM:
    async def generate(self, messages, **kwargs):
        raise RuntimeError("LLM down")

    async def stream(self, messages, **kwargs):
        raise RuntimeError("LLM down")


class FakeDispatcher:
    """Minimal stub: first persona responds, no followups."""

    async def decide_responders(self, *, user_message, history, persona_ids, mentioned_ids=None):
        if persona_ids:
            return [{"persona_id": persona_ids[0], "reason": "test"}]
        return []

    async def check_followup(self, *, last_reply, history, persona_ids, already_responded):
        return []


@pytest.fixture
async def engine():
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from infrastructure.models.base import Base

    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def session_factory(engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _uow_factory(sf):
    from infrastructure.unit_of_work import SQLAlchemyUnitOfWork

    def factory(**kwargs):
        return SQLAlchemyUnitOfWork(session_factory=sf, **kwargs)

    return factory


async def _create_room(sf, room_type="private", persona_ids=None):
    from domain.stakeholder.entity import ChatRoom
    from infrastructure.unit_of_work import SQLAlchemyUnitOfWork

    async with SQLAlchemyUnitOfWork(session_factory=sf) as uow:
        room = ChatRoom(
            id=None,
            name="Test",
            type=room_type,
            persona_ids=persona_ids or ["jianfeng"],
        )
        created = await uow.chat_room_repository.create(room)
        return created.id


@pytest.mark.asyncio
async def test_sse_events_on_send(session_factory):
    """AC2-4: Send message produces message, typing, streaming_delta, message, typing events."""
    from application.services.stakeholder.sse import room_event_bus
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )

    room_id = await _create_room(session_factory)

    # Subscribe before sending
    queue = room_event_bus.subscribe(room_id)

    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=FakePersonaLoader(),
        llm=FakeLLM(),
    )
    msg, room = await svc.send_message(room_id, "Hello")
    await svc.generate_replies(room_id, room)

    # Collect all events
    events = []
    while not queue.empty():
        events.append(await queue.get())

    room_event_bus.unsubscribe(room_id, queue)

    event_names = [e for e, _ in events]

    # Strict sequence (in-memory queue guarantees ordering):
    #   message(user) → typing(start) → streaming_delta(s) → message(persona) → typing(stop)
    assert len(events) >= 5, f"Expected >=5 events, got {len(events)}: {event_names}"
    assert event_names[0] == "message"
    assert events[0][1]["sender_type"] == "user"
    assert events[1] == ("typing", {"persona_id": "jianfeng", "status": "start"})

    # At least one streaming_delta before persona message
    delta_indices = [i for i, e in enumerate(event_names) if e == "streaming_delta"]
    assert delta_indices, "Must have at least one streaming_delta"

    second_msg_idx = event_names.index("message", 1)
    assert events[second_msg_idx][1]["sender_type"] == "persona"
    assert all(di < second_msg_idx for di in delta_indices), "Deltas must precede persona message"

    # typing(stop) must be the last event
    assert events[-1] == ("typing", {"persona_id": "jianfeng", "status": "stop"})


@pytest.mark.asyncio
async def test_sse_round_end_for_group(session_factory):
    """AC6: Group chat emits round_end after replies."""
    from application.services.stakeholder.sse import room_event_bus
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )

    room_id = await _create_room(
        session_factory, room_type="group", persona_ids=["jianfeng", "robin"]
    )
    queue = room_event_bus.subscribe(room_id)

    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=FakePersonaLoader(),
        llm=FakeLLM(),
        dispatcher=FakeDispatcher(),
    )
    msg, room = await svc.send_message(room_id, "Team discussion")
    await svc.generate_replies(room_id, room)

    events = []
    while not queue.empty():
        events.append(await queue.get())

    room_event_bus.unsubscribe(room_id, queue)

    event_names = [e for e, _ in events]
    assert "round_end" in event_names
