# input: StakeholderChatService, in-memory DB, LLM stub, PersonaLoader stub
# output: Story 2.2 application service integration tests
# owner: wanhua.gu
# pos: 测试层 - Story 2.2 私聊消息应用服务测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for StakeholderChatService — Story 2.2 AC coverage."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from application.ports.llm import LLMChunk, LLMMessage, LLMResponse
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


def _make_persona(id: str = "jianfeng", name: str = "剑锋", role: str = "CTO") -> Persona:
    return Persona(
        id=id, name=name, role=role,
        hard_rules=[HardRule(statement="test rule", severity="medium")],
        identity=IdentityProfile(background="bg", core_values=["v1"], hidden_agenda=None),
        expression=ExpressionStyle(tone="formal", catchphrases=["test"], interruption_tendency="low"),
        decision=DecisionPattern(style="analytical", risk_tolerance="medium", typical_questions=["why?"]),
        interpersonal=InterpersonalStyle(authority_mode="direct", triggers=["delay"], emotion_states=["neutral"]),
    )


class FakePersonaLoader:
    def __init__(self, personas: dict[str, Persona] | None = None):
        self._personas = personas or {"jianfeng": _make_persona()}

    def get_persona(self, pid: str):
        return self._personas.get(pid)


class FakeLLM:
    """Stub LLM that returns a fixed response (supports both generate and stream)."""

    def __init__(self, response: str = "I understand your concern."):
        self._response = response

    async def generate(self, messages, **kwargs) -> LLMResponse:
        return LLMResponse(
            content=self._response,
            model="fake",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            finish_reason="end_turn",
        )

    async def stream(self, messages, **kwargs):
        """Yield the response as a single chunk to mimic streaming."""
        yield LLMChunk(content=self._response)
        yield LLMChunk(content="", finish_reason="end_turn")


class FailingLLM:
    """Stub LLM that always raises."""

    async def generate(self, messages, **kwargs):
        raise RuntimeError("Claude API unavailable")

    async def stream(self, messages, **kwargs):
        raise RuntimeError("Claude API unavailable")


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


async def _create_room(sf, name="Test", persona_ids=None):
    """Helper: create a room directly via repo."""
    from domain.stakeholder.entity import ChatRoom

    async with SQLAlchemyUnitOfWork(session_factory=sf) as uow:
        room = ChatRoom(id=None, name=name, type="private", persona_ids=persona_ids or ["jianfeng"])
        created = await uow.chat_room_repository.create(room)
        return created.id


async def _send_and_reply(svc, room_id, content):
    """Helper: send message then generate replies (simulates BackgroundTasks)."""
    msg, room = await svc.send_message(room_id, content)
    await svc.generate_replies(room_id, room)
    return msg


# ---------------------------------------------------------------------------
# AC1: POST messages saves user message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_saves_user_msg(session_factory):
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )

    room_id = await _create_room(session_factory)
    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=FakePersonaLoader(),
        llm=FakeLLM(),
    )
    result, _ = await svc.send_message(room_id, "Hello")
    assert result.sender_type == "user"
    assert result.content == "Hello"


# ---------------------------------------------------------------------------
# AC2: Auto-triggers persona reply
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_triggers_reply(session_factory):
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )

    room_id = await _create_room(session_factory)
    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=FakePersonaLoader(),
        llm=FakeLLM(response="I see your point."),
    )
    await _send_and_reply(svc, room_id, "What do you think?")

    async with SQLAlchemyUnitOfWork(session_factory=session_factory, readonly=True) as uow:
        msgs = await uow.stakeholder_message_repository.list_by_room_id(room_id)
    assert len(msgs) == 2
    assert msgs[1].sender_type == "persona"
    assert msgs[1].content == "I see your point."


# ---------------------------------------------------------------------------
# AC4: Persona reply has correct sender_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reply_sender_is_persona(session_factory):
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )

    room_id = await _create_room(session_factory)
    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=FakePersonaLoader(),
        llm=FakeLLM(),
    )
    await _send_and_reply(svc, room_id, "Hi")

    async with SQLAlchemyUnitOfWork(session_factory=session_factory, readonly=True) as uow:
        msgs = await uow.stakeholder_message_repository.list_by_room_id(room_id)
    persona_msg = [m for m in msgs if m.sender_type == "persona"][0]
    assert persona_msg.sender_id == "jianfeng"


# ---------------------------------------------------------------------------
# AC5: last_message_at updated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_message_at_updated(session_factory):
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )

    room_id = await _create_room(session_factory)
    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=FakePersonaLoader(),
        llm=FakeLLM(),
    )
    await _send_and_reply(svc, room_id, "Test")

    async with SQLAlchemyUnitOfWork(session_factory=session_factory, readonly=True) as uow:
        room = await uow.chat_room_repository.get_by_id(room_id)
    assert room.last_message_at is not None


# ---------------------------------------------------------------------------
# AC6: Claude API failure → system message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claude_api_failure_system_message(session_factory):
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )

    room_id = await _create_room(session_factory)
    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=FakePersonaLoader(),
        llm=FailingLLM(),
    )
    await _send_and_reply(svc, room_id, "Hello")

    async with SQLAlchemyUnitOfWork(session_factory=session_factory, readonly=True) as uow:
        msgs = await uow.stakeholder_message_repository.list_by_room_id(room_id)
    assert len(msgs) == 2
    assert msgs[1].sender_type == "system"
    assert "error" in msgs[1].content.lower() or "失败" in msgs[1].content


# ---------------------------------------------------------------------------
# Room not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_room_not_found(session_factory):
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )
    from domain.common.exceptions import BusinessException

    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=FakePersonaLoader(),
        llm=FakeLLM(),
    )
    with pytest.raises(BusinessException):
        await svc.send_message(99999, "Hello")


# ---------------------------------------------------------------------------
# Story 2.8: v2 persona branches to build_system_prompt — catchphrase in prompt
# ---------------------------------------------------------------------------


class _CapturingLLM:
    """LLM stub that captures the last message list it was asked to stream."""

    def __init__(self, response: str = "roger."):
        self._response = response
        self.last_messages: list[LLMMessage] = []

    async def generate(self, messages, **kwargs):
        self.last_messages = list(messages)
        return LLMResponse(content=self._response, model="fake")

    async def stream(self, messages, **kwargs):
        self.last_messages = list(messages)
        yield LLMChunk(content=self._response)
        yield LLMChunk(content="", finish_reason="end_turn")


@pytest.mark.asyncio
async def test_v2_persona_prompts_use_5_layer_builder(session_factory):
    """Story 2.8 AC5/AC6: a v2 persona's system prompt must include Expression
    catchphrases (proves build_system_prompt was chosen over markdown path)."""
    from application.services.stakeholder.stakeholder_chat_service import (
        StakeholderChatService,
    )
    from domain.stakeholder.persona_entity import (
        ExpressionStyle,
        HardRule,
        IdentityProfile,
        Persona,
    )

    v2_persona = Persona(
        id="cfo",
        name="CFO",
        role="首席财务官",
        hard_rules=[HardRule(statement="预算超支必报", severity="critical")],
        identity=IdentityProfile(background="20 年会计", hidden_agenda="裁员 15%"),
        expression=ExpressionStyle(
            tone="严谨",
            catchphrases=["数字会说话"],
            interruption_tendency="medium",
        ),
    )
    loader = FakePersonaLoader(personas={"cfo": v2_persona})
    llm = _CapturingLLM(response="roger that.")
    room_id = await _create_room(session_factory, persona_ids=["cfo"])

    svc = StakeholderChatService(
        uow_factory=_uow_factory(session_factory),
        persona_loader=loader,
        llm=llm,
    )
    await _send_and_reply(svc, room_id, "怎么回事？")

    # LLM was invoked once; first message is the system prompt.
    assert llm.last_messages, "LLM was never called"
    system_msg = llm.last_messages[0]
    assert system_msg.role == "system"
    # v2 catchphrase must be present — proves the 5-layer builder was used
    assert "数字会说话" in system_msg.content
    # Hostile section must be injected with the "don't expose" marker
    assert "不要在对话里直接说出来" in system_msg.content
    assert "裁员 15%" in system_msg.content
