# input: core.config.Settings, infrastructure.external.llm.anthropic_provider
# output: StakeholderSettings 配置测试, AnthropicProvider mock 测试
# owner: wanhua.gu
# pos: 测试层 - Story 1.1 配置与 Provider 验收测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Story 1.1: StakeholderSettings + AnthropicProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.config import Settings


def test_stakeholder_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1: StakeholderSettings has correct default values."""
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    s = Settings(_env_file=None)

    assert s.stakeholder.model == "claude-opus-4-0-20250514"
    assert s.stakeholder.max_group_rounds == 20
    assert s.stakeholder.persona_dir == "data/personas"
    assert s.stakeholder.anthropic_api_key is None
    assert s.stakeholder.anthropic_base_url is None


def test_stakeholder_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2: Environment variables correctly inject into StakeholderSettings."""
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("STAKEHOLDER__ANTHROPIC_API_KEY", "sk-ant-test-key")
    monkeypatch.setenv("STAKEHOLDER__ANTHROPIC_BASE_URL", "https://custom.api.com")
    monkeypatch.setenv("STAKEHOLDER__MODEL", "claude-sonnet-4-20250514")
    monkeypatch.setenv("STAKEHOLDER__MAX_GROUP_ROUNDS", "10")
    monkeypatch.setenv("STAKEHOLDER__PERSONA_DIR", "/custom/personas")

    s = Settings(_env_file=None)

    assert s.stakeholder.anthropic_api_key == "sk-ant-test-key"
    assert s.stakeholder.anthropic_base_url == "https://custom.api.com"
    assert s.stakeholder.model == "claude-sonnet-4-20250514"
    assert s.stakeholder.max_group_rounds == 10
    assert s.stakeholder.persona_dir == "/custom/personas"


def test_app_starts_without_stakeholder_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC5: App starts normally when STAKEHOLDER__ANTHROPIC_API_KEY is not set."""
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    # Explicitly ensure no stakeholder env vars
    monkeypatch.delenv("STAKEHOLDER__ANTHROPIC_API_KEY", raising=False)

    s = Settings(_env_file=None)

    # Settings created successfully
    assert s.stakeholder.anthropic_api_key is None
    # Other settings still functional
    assert s.SECRET_KEY == "test-secret"


@pytest.mark.asyncio
async def test_anthropic_provider_generate_mock() -> None:
    """AC3: AnthropicProvider.generate() calls Anthropic SDK and returns LLMResponse."""
    from application.ports.llm import LLMMessage, LLMResponse
    from infrastructure.external.llm.anthropic_provider import AnthropicProvider

    # Create provider with mock client
    provider = AnthropicProvider(
        api_key="sk-ant-test",
        default_model="claude-opus-4-0-20250514",
    )

    # Mock the internal Anthropic client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Hello from Claude")]
    mock_response.model = "claude-opus-4-0-20250514"
    mock_response.usage = MagicMock(
        input_tokens=10,
        output_tokens=20,
    )
    mock_response.stop_reason = "end_turn"

    provider._client = AsyncMock()
    provider._client.messages.create = AsyncMock(return_value=mock_response)

    messages = [
        LLMMessage(role="system", content="You are a helpful assistant"),
        LLMMessage(role="user", content="Hello"),
    ]

    result = await provider.generate(messages)

    assert isinstance(result, LLMResponse)
    assert result.content == "Hello from Claude"
    assert result.model == "claude-opus-4-0-20250514"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 20
    assert result.total_tokens == 30
    assert result.finish_reason == "end_turn"

    # Verify SDK was called with correct params
    provider._client.messages.create.assert_called_once()
    call_kwargs = provider._client.messages.create.call_args
    assert call_kwargs.kwargs["model"] == "claude-opus-4-0-20250514"
