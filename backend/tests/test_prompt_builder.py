# input: prompt_builder module
# output: Story 2.2 prompt builder unit tests
# owner: wanhua.gu
# pos: 测试层 - Story 2.2 prompt builder 验收测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Story 2.2: prompt_builder — AC3 coverage."""

from __future__ import annotations


def test_system_prompt_contains_persona():
    """AC3: system prompt contains the persona's full_content."""
    from application.services.stakeholder.prompt_builder import build_llm_messages

    persona_content = "# 剑锋\n\n## 背景\nCTO of the company..."
    history = []

    system, messages = build_llm_messages(
        persona_full_content=persona_content,
        persona_name="剑锋",
        history=history,
    )
    assert persona_content in system
    assert "剑锋" in system


def test_history_converted_to_llm_messages():
    """History messages are converted with correct roles."""
    from application.services.stakeholder.prompt_builder import build_llm_messages

    history = [
        {"sender_type": "user", "content": "Hello"},
        {"sender_type": "persona", "content": "Hi there"},
        {"sender_type": "user", "content": "How are you?"},
    ]

    system, messages = build_llm_messages(
        persona_full_content="# Persona",
        persona_name="Test",
        history=history,
    )
    assert len(messages) == 3
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"


def test_system_messages_skipped_in_history():
    """System messages in history are excluded from LLM context."""
    from application.services.stakeholder.prompt_builder import build_llm_messages

    history = [
        {"sender_type": "user", "content": "Hello"},
        {"sender_type": "system", "content": "Error occurred"},
        {"sender_type": "persona", "content": "Sorry about that"},
    ]

    system, messages = build_llm_messages(
        persona_full_content="# Persona",
        persona_name="Test",
        history=history,
    )
    assert len(messages) == 2  # system message excluded


def test_empty_history():
    """Empty history produces only system prompt, no messages."""
    from application.services.stakeholder.prompt_builder import build_llm_messages

    system, messages = build_llm_messages(
        persona_full_content="# Persona content",
        persona_name="Test",
        history=[],
    )
    assert len(system) > 0
    assert messages == []
