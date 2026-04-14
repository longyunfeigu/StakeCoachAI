"""Tests for SpeakerDetectionService — speaker detection from transcripts."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from application.ports.llm import LLMResponse
from application.services.stakeholder.dto import DetectedSpeakerDTO
from application.services.stakeholder.speaker_detection_service import SpeakerDetectionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm_response(content: str) -> LLMResponse:
    return LLMResponse(
        content=content,
        model="fake",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        finish_reason="end_turn",
    )


def _build_service(llm_response_content: str) -> SpeakerDetectionService:
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = _make_llm_response(llm_response_content)
    return SpeakerDetectionService(llm=mock_llm)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_speakers_happy_path():
    """Three speakers detected, sorted by dominance desc then turns desc."""
    llm_json = json.dumps(
        [
            {
                "name": "Lu Jianfeng",
                "role": "CTO",
                "speaking_turns": 15,
                "dominance_level": "high",
                "sample_quote": "这个方案不行，必须重新设计。",
            },
            {
                "name": "Zhang Wei",
                "role": "产品经理",
                "speaking_turns": 10,
                "dominance_level": "medium",
                "sample_quote": "用户反馈显示这个功能很重要。",
            },
            {
                "name": "Li Na",
                "role": "开发工程师",
                "speaking_turns": 5,
                "dominance_level": "low",
                "sample_quote": "技术上我们可以实现。",
            },
        ],
        ensure_ascii=False,
    )

    svc = _build_service(llm_json)
    speakers = await svc.detect(["@Lu Jianfeng  00:09:23\n一些对话内容"])

    assert len(speakers) == 3
    assert all(isinstance(s, DetectedSpeakerDTO) for s in speakers)

    # Verify sorting: high first, then medium, then low
    assert speakers[0].name == "Lu Jianfeng"
    assert speakers[0].dominance_level == "high"
    assert speakers[0].speaking_turns == 15
    assert speakers[0].role == "CTO"

    assert speakers[1].name == "Zhang Wei"
    assert speakers[1].dominance_level == "medium"

    assert speakers[2].name == "Li Na"
    assert speakers[2].dominance_level == "low"


@pytest.mark.asyncio
async def test_detect_speakers_single_speaker():
    """Single speaker transcript returns one-element array."""
    llm_json = json.dumps(
        [
            {
                "name": "Wang Fang",
                "role": "项目经理",
                "speaking_turns": 20,
                "dominance_level": "high",
                "sample_quote": "下周必须交付。",
            },
        ],
        ensure_ascii=False,
    )

    svc = _build_service(llm_json)
    speakers = await svc.detect(["@Wang Fang  00:01:00\n下周必须交付。"])

    assert len(speakers) == 1
    assert speakers[0].name == "Wang Fang"
    assert speakers[0].speaking_turns == 20
    assert speakers[0].sample_quote == "下周必须交付。"


@pytest.mark.asyncio
async def test_detect_speakers_invalid_json():
    """LLM returns garbage text — graceful empty list, no exception."""
    svc = _build_service("Sorry, I cannot parse this transcript properly...")
    speakers = await svc.detect(["@Someone  00:00:00\nHello"])

    assert speakers == []


@pytest.mark.asyncio
async def test_detect_speakers_sorting_within_same_dominance():
    """Within the same dominance level, higher speaking_turns come first."""
    llm_json = json.dumps(
        [
            {
                "name": "A",
                "role": "",
                "speaking_turns": 3,
                "dominance_level": "medium",
                "sample_quote": "quote A",
            },
            {
                "name": "B",
                "role": "",
                "speaking_turns": 8,
                "dominance_level": "medium",
                "sample_quote": "quote B",
            },
        ],
        ensure_ascii=False,
    )

    svc = _build_service(llm_json)
    speakers = await svc.detect(["transcript"])

    assert len(speakers) == 2
    assert speakers[0].name == "B"
    assert speakers[1].name == "A"


@pytest.mark.asyncio
async def test_detect_speakers_non_list_json():
    """LLM returns valid JSON but not an array — graceful empty list."""
    svc = _build_service('{"error": "no speakers found"}')
    speakers = await svc.detect(["@Someone  00:00:00\nHello"])

    assert speakers == []
