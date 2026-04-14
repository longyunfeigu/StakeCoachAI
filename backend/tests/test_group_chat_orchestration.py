# input: StakeholderChatService, Dispatcher, prompt_builder stubs, in-memory DB
# output: Story 3.2 群聊多轮编排 integration + unit tests
# owner: wanhua.gu
# pos: 测试层 - Story 3.2 群聊多轮对话编排测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for group chat multi-round orchestration — Story 3.2 AC coverage."""

from __future__ import annotations

import json
from typing import Optional

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from application.ports.llm import LLMMessage, LLMResponse
from domain.stakeholder.persona_entity import (
    DecisionPattern,
    ExpressionStyle,
    HardRule,
    IdentityProfile,
    InterpersonalStyle,
    Persona,
)
from infrastructure.models.base import Base
from infrastructure.unit_of_work import SQLAlchemyUnitOfWork


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


def _make_persona(id: str, name: str, role: str) -> Persona:
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


PERSONAS = {
    "jianfeng": _make_persona("jianfeng", "剑锋", "CTO"),
    "mingzhu": _make_persona("mingzhu", "明珠", "CFO"),
    "liqiang": _make_persona("liqiang", "力强", "PM"),
}


class FakePersonaLoader:
    def __init__(self, personas: dict[str, Persona] | None = None):
        self._personas = personas or PERSONAS

    def get_persona(self, pid: str) -> Optional[Persona]:
        return self._personas.get(pid)


class FakeLLM:
    """Stub LLM that returns a fixed response and captures calls."""

    def __init__(self, response: str = "I understand your concern."):
        self._response = response
        self.calls: list[list[LLMMessage]] = []

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        self.calls.append(messages)
        return LLMResponse(
            content=self._response,
            model="fake",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            finish_reason="end_turn",
        )

    async def stream(self, messages: list[LLMMessage], **kwargs):
        from application.ports.llm import LLMChunk

        self.calls.append(messages)
        yield LLMChunk(content=self._response)
        yield LLMChunk(content="", finish_reason="end_turn")


class FailingLLM:
    """Stub LLM that always raises."""

    async def generate(self, messages, **kwargs):
        raise RuntimeError("Claude API unavailable")

    async def stream(self, messages, **kwargs):
        raise RuntimeError("Claude API unavailable")


class FakeDispatcher:
    """Stub Dispatcher with configurable responses."""

    def __init__(
        self,
        *,
        first_responders: list[dict[str, str]] | None = None,
        followup_responses: list[list[dict[str, str]]] | None = None,
    ):
        self._first_responders = first_responders or [
            {"persona_id": "jianfeng", "reason": "CTO needs to respond"},
            {"persona_id": "mingzhu", "reason": "CFO has budget concerns"},
        ]
        self._followup_queue = list(followup_responses or [])
        self.decide_calls: list[dict] = []
        self.followup_calls: list[dict] = []

    async def decide_responders(self, *, user_message, history, persona_ids, mentioned_ids=None):
        self.decide_calls.append(
            {
                "user_message": user_message,
                "history": history,
                "persona_ids": persona_ids,
            }
        )
        return self._first_responders

    async def check_followup(self, *, last_reply, history, persona_ids, already_responded):
        self.followup_calls.append(
            {
                "last_reply": last_reply,
                "history": history,
                "persona_ids": persona_ids,
                "already_responded": already_responded,
            }
        )
        if self._followup_queue:
            return self._followup_queue.pop(0)
        return []


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


def _uow_factory(sf):
    def factory(**kwargs):
        return SQLAlchemyUnitOfWork(session_factory=sf, **kwargs)

    return factory


async def _create_group_room(sf, name="Group Room", persona_ids=None):
    """Helper: create a group chat room."""
    from domain.stakeholder.entity import ChatRoom

    async with SQLAlchemyUnitOfWork(session_factory=sf) as uow:
        room = ChatRoom(
            id=None,
            name=name,
            type="group",
            persona_ids=persona_ids or ["jianfeng", "mingzhu", "liqiang"],
        )
        created = await uow.chat_room_repository.create(room)
        return created.id


async def _send_and_reply(svc, room_id, content):
    """Helper: send message then generate replies (simulates BackgroundTasks)."""
    msg, room = await svc.send_message(room_id, content)
    await svc.generate_replies(room_id, room)
    return msg


# ---------------------------------------------------------------------------
# AC2: prompt includes full history (including other persona replies)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_group_chat_prompt_includes_full_history(session_factory):
    """AC2: Each persona's LLM call includes complete conversation history."""
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )

    room_id = await _create_group_room(session_factory)
    llm = FakeLLM(response="I agree with the approach.")
    dispatcher = FakeDispatcher(
        first_responders=[
            {"persona_id": "jianfeng", "reason": "CTO"},
            {"persona_id": "mingzhu", "reason": "CFO"},
        ],
        followup_responses=[[], []],
    )
    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=FakePersonaLoader(),
        llm=llm,
        dispatcher=dispatcher,
    )
    await _send_and_reply(svc, room_id, "Should we invest in AI?")

    assert len(llm.calls) == 2
    second_call_contents = " ".join(m.content for m in llm.calls[1])
    assert "I agree with the approach" in second_call_contents


# ---------------------------------------------------------------------------
# AC1: Full group chat flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_group_chat_full_flow(session_factory):
    """AC1: User msg → dispatch → replies → followup → round_end."""
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )

    room_id = await _create_group_room(session_factory)
    llm = FakeLLM(response="Noted.")
    dispatcher = FakeDispatcher(
        first_responders=[
            {"persona_id": "jianfeng", "reason": "CTO"},
        ],
        followup_responses=[
            [{"persona_id": "mingzhu", "reason": "CFO followup"}],
            [],
        ],
    )
    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=FakePersonaLoader(),
        llm=llm,
        dispatcher=dispatcher,
    )
    await _send_and_reply(svc, room_id, "Let's discuss the budget")

    async with SQLAlchemyUnitOfWork(session_factory=session_factory, readonly=True) as uow:
        msgs = await uow.stakeholder_message_repository.list_by_room_id(room_id)
    persona_msgs = [m for m in msgs if m.sender_type == "persona"]
    assert len(persona_msgs) == 2
    sender_ids = [m.sender_id for m in persona_msgs]
    assert "jianfeng" in sender_ids
    assert "mingzhu" in sender_ids


# ---------------------------------------------------------------------------
# AC3: Max rounds limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_group_chat_max_rounds_limit(session_factory):
    """AC3: Group chat stops at max_group_rounds."""
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )

    room_id = await _create_group_room(session_factory)
    llm = FakeLLM(response="Reply.")

    infinite_followups = [
        [{"persona_id": "mingzhu", "reason": "followup"}],
        [{"persona_id": "liqiang", "reason": "followup"}],
        [{"persona_id": "jianfeng", "reason": "followup"}],
    ] * 20
    dispatcher = FakeDispatcher(
        first_responders=[{"persona_id": "jianfeng", "reason": "start"}],
        followup_responses=infinite_followups,
    )
    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=FakePersonaLoader(),
        llm=llm,
        dispatcher=dispatcher,
        max_group_rounds=3,
    )
    await _send_and_reply(svc, room_id, "Discuss")

    async with SQLAlchemyUnitOfWork(session_factory=session_factory, readonly=True) as uow:
        msgs = await uow.stakeholder_message_repository.list_by_room_id(room_id)
    persona_msgs = [m for m in msgs if m.sender_type == "persona"]
    assert len(persona_msgs) <= 3


# ---------------------------------------------------------------------------
# AC4: Max rounds → system message + round_end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_group_chat_max_rounds_system_message(session_factory):
    """AC4: When max rounds reached, insert system message."""
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )

    room_id = await _create_group_room(session_factory)
    llm = FakeLLM(response="Reply.")

    infinite_followups = [
        [{"persona_id": "mingzhu", "reason": "followup"}],
        [{"persona_id": "liqiang", "reason": "followup"}],
        [{"persona_id": "jianfeng", "reason": "followup"}],
    ] * 20
    dispatcher = FakeDispatcher(
        first_responders=[{"persona_id": "jianfeng", "reason": "start"}],
        followup_responses=infinite_followups,
    )
    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=FakePersonaLoader(),
        llm=llm,
        dispatcher=dispatcher,
        max_group_rounds=2,
    )
    await _send_and_reply(svc, room_id, "Discuss")

    async with SQLAlchemyUnitOfWork(session_factory=session_factory, readonly=True) as uow:
        msgs = await uow.stakeholder_message_repository.list_by_room_id(room_id)
    system_msgs = [m for m in msgs if m.sender_type == "system"]
    assert len(system_msgs) >= 1
    assert any("轮次" in m.content or "上限" in m.content for m in system_msgs)


# ---------------------------------------------------------------------------
# AC5: Normal end → round_end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_group_chat_normal_end_round_end(session_factory):
    """AC5: When no followup, group chat ends normally."""
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )

    room_id = await _create_group_room(session_factory)
    llm = FakeLLM(response="Done.")
    dispatcher = FakeDispatcher(
        first_responders=[{"persona_id": "jianfeng", "reason": "CTO"}],
        followup_responses=[[]],
    )
    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=FakePersonaLoader(),
        llm=llm,
        dispatcher=dispatcher,
    )
    await _send_and_reply(svc, room_id, "Quick question")

    async with SQLAlchemyUnitOfWork(session_factory=session_factory, readonly=True) as uow:
        msgs = await uow.stakeholder_message_repository.list_by_room_id(room_id)
    assert len(msgs) == 2
    assert msgs[0].sender_type == "user"
    assert msgs[1].sender_type == "persona"
    assert msgs[1].sender_id == "jianfeng"


# ---------------------------------------------------------------------------
# AC7: LLM failure → graceful stop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_group_chat_api_failure_graceful_stop(session_factory):
    """AC7: Claude API failure stops the round with system error message."""
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )

    room_id = await _create_group_room(session_factory)
    dispatcher = FakeDispatcher(
        first_responders=[{"persona_id": "jianfeng", "reason": "CTO"}],
    )
    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=FakePersonaLoader(),
        llm=FailingLLM(),
        dispatcher=dispatcher,
    )
    await _send_and_reply(svc, room_id, "Test failure")

    async with SQLAlchemyUnitOfWork(session_factory=session_factory, readonly=True) as uow:
        msgs = await uow.stakeholder_message_repository.list_by_room_id(room_id)
    system_msgs = [m for m in msgs if m.sender_type == "system"]
    assert len(system_msgs) >= 1
    persona_msgs = [m for m in msgs if m.sender_type == "persona"]
    assert len(persona_msgs) == 0
