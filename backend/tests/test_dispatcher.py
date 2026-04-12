# input: Dispatcher, FakeLLM, FakePersonaLoader stubs
# output: Story 3.1 Dispatcher unit tests
# owner: wanhua.gu
# pos: 测试层 - Story 3.1 群聊调度器单元测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Dispatcher — Story 3.1 AC coverage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import pytest

from application.ports.llm import LLMMessage, LLMResponse


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


@dataclass
class FakePersona:
    id: str = "jianfeng"
    name: str = "剑锋"
    role: str = "CTO"
    avatar_color: str = "#f00"
    full_content: str = "# 剑锋\n\nA seasoned CTO."
    profile_summary: str = "CTO with strong opinions"
    parse_status: str = "ok"


class FakePersonaLoader:
    def __init__(self, personas: dict[str, FakePersona] | None = None):
        self._personas = personas or {}

    def get_persona(self, pid: str) -> Optional[FakePersona]:
        return self._personas.get(pid)

    def list_personas(self) -> list[FakePersona]:
        return list(self._personas.values())


class FakeLLM:
    """Stub LLM that returns a configurable JSON response and captures calls."""

    def __init__(self, response_json: str = "[]"):
        self._response_json = response_json
        self.calls: list[list[LLMMessage]] = []

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        self.calls.append(messages)
        return LLMResponse(
            content=self._response_json,
            model="fake",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            finish_reason="end_turn",
        )


class FailingLLM:
    """Stub LLM that raises during dispatcher decision."""

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        raise RuntimeError("dispatcher unavailable")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PERSONAS = {
    "jianfeng": FakePersona(
        id="jianfeng",
        name="剑锋",
        role="CTO",
        profile_summary="CTO with strong opinions",
        full_content="# 剑锋\n\nA seasoned CTO.",
    ),
    "mingzhu": FakePersona(
        id="mingzhu",
        name="明珠",
        role="CFO",
        avatar_color="#0f0",
        profile_summary="CFO focused on budget",
        full_content="# 明珠\n\nA cautious CFO.",
    ),
    "liqiang": FakePersona(
        id="liqiang",
        name="力强",
        role="PM",
        avatar_color="#00f",
        profile_summary="PM balancing stakeholder needs",
        full_content="# 力强\n\nA pragmatic PM.",
    ),
}

_HISTORY = [
    {"sender_type": "user", "sender_id": "user", "content": "我们应该采用微服务架构吗？"},
]


# ---------------------------------------------------------------------------
# AC1: decide_responders returns list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_decide_responders_returns_list():
    from application.services.stakeholder.dispatcher import Dispatcher

    llm_response = json.dumps(
        [
            {"persona_id": "jianfeng", "reason": "作为 CTO 需要对技术架构发表意见"},
            {"persona_id": "mingzhu", "reason": "作为 CFO 需要评估成本影响"},
        ]
    )
    llm = FakeLLM(response_json=llm_response)
    loader = FakePersonaLoader(_PERSONAS)

    dispatcher = Dispatcher(llm=llm, persona_loader=loader)
    result = await dispatcher.decide_responders(
        user_message="我们应该采用微服务架构吗？",
        history=_HISTORY,
        persona_ids=["jianfeng", "mingzhu", "liqiang"],
    )

    assert isinstance(result, list)
    assert len(result) >= 1


@pytest.mark.asyncio
async def test_dispatcher_decide_responders_falls_back_when_empty():
    from application.services.stakeholder.dispatcher import Dispatcher

    llm = FakeLLM(response_json="[]")
    loader = FakePersonaLoader(_PERSONAS)

    dispatcher = Dispatcher(llm=llm, persona_loader=loader)
    result = await dispatcher.decide_responders(
        user_message="是你们到底在讨论什么问题啊",
        history=_HISTORY,
        persona_ids=["jianfeng", "mingzhu"],
    )

    assert result == [
        {
            "persona_id": "jianfeng",
            "reason": "调度器未返回有效角色，默认回应以避免冷场",
        }
    ]


@pytest.mark.asyncio
async def test_dispatcher_decide_responders_falls_back_when_llm_fails():
    from application.services.stakeholder.dispatcher import Dispatcher

    loader = FakePersonaLoader(_PERSONAS)

    dispatcher = Dispatcher(llm=FailingLLM(), persona_loader=loader)
    result = await dispatcher.decide_responders(
        user_message="普通群聊消息也需要有人回应",
        history=_HISTORY,
        persona_ids=["jianfeng", "mingzhu"],
    )

    assert result[0]["persona_id"] == "jianfeng"


# ---------------------------------------------------------------------------
# AC2: decide_responders returns [{persona_id, reason}]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_response_format():
    from application.services.stakeholder.dispatcher import Dispatcher

    llm_response = json.dumps(
        [
            {"persona_id": "jianfeng", "reason": "技术决策需要 CTO 意见"},
        ]
    )
    llm = FakeLLM(response_json=llm_response)
    loader = FakePersonaLoader(_PERSONAS)

    dispatcher = Dispatcher(llm=llm, persona_loader=loader)
    result = await dispatcher.decide_responders(
        user_message="我们应该采用微服务架构吗？",
        history=_HISTORY,
        persona_ids=["jianfeng", "mingzhu"],
    )

    for item in result:
        assert "persona_id" in item
        assert "reason" in item
        assert isinstance(item["persona_id"], str)
        assert isinstance(item["reason"], str)


# ---------------------------------------------------------------------------
# AC3: check_followup returns follow-up list or empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_check_followup():
    from application.services.stakeholder.dispatcher import Dispatcher

    # LLM says mingzhu wants to follow up
    llm_response = json.dumps(
        [
            {"persona_id": "mingzhu", "reason": "对 CTO 的成本估算有异议"},
        ]
    )
    llm = FakeLLM(response_json=llm_response)
    loader = FakePersonaLoader(_PERSONAS)

    dispatcher = Dispatcher(llm=llm, persona_loader=loader)

    history_with_reply = _HISTORY + [
        {"sender_type": "persona", "sender_id": "jianfeng", "content": "微服务会增加运维成本"},
    ]

    result = await dispatcher.check_followup(
        last_reply={
            "sender_type": "persona",
            "sender_id": "jianfeng",
            "content": "微服务会增加运维成本",
        },
        history=history_with_reply,
        persona_ids=["jianfeng", "mingzhu", "liqiang"],
        already_responded={"jianfeng"},
    )

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_dispatcher_check_followup_empty():
    from application.services.stakeholder.dispatcher import Dispatcher

    # LLM says no follow-up needed
    llm = FakeLLM(response_json="[]")
    loader = FakePersonaLoader(_PERSONAS)

    dispatcher = Dispatcher(llm=llm, persona_loader=loader)

    result = await dispatcher.check_followup(
        last_reply={"sender_type": "persona", "sender_id": "jianfeng", "content": "同意"},
        history=_HISTORY,
        persona_ids=["jianfeng", "mingzhu"],
        already_responded={"jianfeng"},
    )

    assert result == []


# ---------------------------------------------------------------------------
# AC4: prompt contains all persona summaries and context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_prompt_contains_all_personas():
    from application.services.stakeholder.dispatcher import Dispatcher

    llm_response = json.dumps([{"persona_id": "jianfeng", "reason": "tech lead"}])
    llm = FakeLLM(response_json=llm_response)
    loader = FakePersonaLoader(_PERSONAS)

    dispatcher = Dispatcher(llm=llm, persona_loader=loader)
    await dispatcher.decide_responders(
        user_message="我们应该采用微服务架构吗？",
        history=_HISTORY,
        persona_ids=["jianfeng", "mingzhu", "liqiang"],
    )

    # Inspect the captured LLM call
    assert len(llm.calls) == 1
    messages = llm.calls[0]

    # Find system message
    system_msgs = [m for m in messages if m.role == "system"]
    assert len(system_msgs) == 1
    system_content = system_msgs[0].content

    # All persona names and roles should appear in system prompt
    assert "剑锋" in system_content
    assert "明珠" in system_content
    assert "力强" in system_content
    assert "CTO" in system_content
    assert "CFO" in system_content
    assert "PM" in system_content

    # User message context should appear in the messages
    all_content = " ".join(m.content for m in messages)
    assert "微服务" in all_content


# ---------------------------------------------------------------------------
# AC5: returned persona_ids are valid participants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_returns_valid_persona_ids():
    from application.services.stakeholder.dispatcher import Dispatcher

    # LLM returns an invalid persona_id mixed with valid ones
    llm_response = json.dumps(
        [
            {"persona_id": "jianfeng", "reason": "valid"},
            {"persona_id": "nonexistent", "reason": "should be filtered"},
        ]
    )
    llm = FakeLLM(response_json=llm_response)
    loader = FakePersonaLoader(_PERSONAS)

    dispatcher = Dispatcher(llm=llm, persona_loader=loader)
    result = await dispatcher.decide_responders(
        user_message="Test",
        history=_HISTORY,
        persona_ids=["jianfeng", "mingzhu"],
    )

    # All returned persona_ids must be in the provided persona_ids
    valid_ids = {"jianfeng", "mingzhu"}
    for item in result:
        assert item["persona_id"] in valid_ids


@pytest.mark.asyncio
async def test_dispatcher_check_followup_filters_invalid_ids():
    from application.services.stakeholder.dispatcher import Dispatcher

    llm_response = json.dumps(
        [
            {"persona_id": "invalid_id", "reason": "should be filtered"},
        ]
    )
    llm = FakeLLM(response_json=llm_response)
    loader = FakePersonaLoader(_PERSONAS)

    dispatcher = Dispatcher(llm=llm, persona_loader=loader)
    result = await dispatcher.check_followup(
        last_reply={"sender_type": "persona", "sender_id": "jianfeng", "content": "ok"},
        history=_HISTORY,
        persona_ids=["jianfeng", "mingzhu"],
        already_responded={"jianfeng"},
    )

    # Invalid ids should be filtered out
    for item in result:
        assert item["persona_id"] in {"jianfeng", "mingzhu"}
