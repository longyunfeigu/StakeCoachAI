"""Speaker detection service — extracts speakers from meeting transcripts via LLM."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from application.ports.llm import LLMMessage, LLMPort
from application.services.stakeholder.dto import DetectedSpeakerDTO

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "detect_speakers.md"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


class SpeakerDetectionService:
    """Detect speakers from transcript materials using a single LLM call."""

    def __init__(self, *, llm: LLMPort) -> None:
        self._llm = llm
        self._system_prompt = _load_prompt()

    async def detect(self, materials: list[str]) -> list[DetectedSpeakerDTO]:
        """Analyse *materials* and return detected speakers sorted by dominance."""
        combined = "\n\n---\n\n".join(materials)
        messages = [
            LLMMessage(role="system", content=self._system_prompt),
            LLMMessage(role="user", content=combined),
        ]

        resp = await self._llm.generate(messages, temperature=0.2)
        raw = resp.content.strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON for speaker detection: %.200s", raw)
            return []

        if not isinstance(parsed, list):
            logger.warning("LLM returned non-list JSON for speaker detection")
            return []

        speakers: list[DetectedSpeakerDTO] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            try:
                speakers.append(DetectedSpeakerDTO(**item))
            except Exception:  # noqa: BLE001
                logger.warning("Skipping malformed speaker entry: %s", item)

        # Sort: dominance_level desc (high > medium > low), then speaking_turns desc
        _dominance_order = {"high": 0, "medium": 1, "low": 2}
        speakers.sort(key=lambda s: (_dominance_order.get(s.dominance_level, 1), -s.speaking_turns))

        return speakers
