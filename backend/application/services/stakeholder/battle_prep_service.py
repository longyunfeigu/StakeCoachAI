# input: AbstractUnitOfWork, LLMPort, ChatRoomApplicationService, PersonaEditorService, PersonaLoader
# output: BattlePrepService 备战模式编排服务
# owner: wanhua.gu
# pos: 应用层服务 - 紧急备战模式（角色生成、对话启动、话术纸条）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Battle Prep service: pre-meeting quick simulation workflow."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from application.ports.llm import LLMMessage, LLMPort
from application.services.stakeholder.dto import (
    BattlePrepResultDTO,
    CheatSheetDTO,
    ChatRoomDTO,
    CreateChatRoomDTO,
    CreatePersonaDTO,
    StartBattleDTO,
    TacticItem,
)
from application.services.stakeholder.chatroom_service import ChatRoomApplicationService
from application.services.stakeholder.persona_editor_service import PersonaEditorService
from application.services.stakeholder.persona_loader import PersonaLoader
from domain.common.unit_of_work import AbstractUnitOfWork

logger = logging.getLogger(__name__)

_GENERATE_PROMPT = """\
你是一个职场沟通模拟助手。用户即将参加一个重要会议，请根据用户的描述，生成模拟对话所需的角色和场景。

## 用户描述

{description}

## 输出要求

输出严格 JSON，不要输出其他内容：

```json
{{
  "persona_name": "对方的称呼（如：张总、李经理）",
  "persona_role": "对方的职位（如：技术副总裁）",
  "persona_style": "对方的沟通风格描述（100-200字，包含性格特点、决策偏好、常见反应模式）",
  "scenario_context": "对话场景背景（100-200字，包含会议目的、核心矛盾点、双方立场）",
  "training_points": ["训练重点1", "训练重点2", "训练重点3"]
}}
```

规则：
- persona_style 要具体，不要泛泛描述，要像真人一样有个性
- training_points 必须 2-3 个，每个是一个具体的沟通挑战（如"如何应对对方用预算紧张来拒绝"）
- scenario_context 要包含冲突焦点
"""

_CHEAT_SHEET_PROMPT = """\
你是一个职场沟通教练。用户刚完成了一场模拟对话练习，请根据对话记录生成一份简洁实用的"话术纸条"，用户可以带进真实会议。

## 对话场景

{scenario_context}

## 训练重点

{training_points}

## 对话记录

{conversation}

## 输出要求

输出严格 JSON，不要输出其他内容：

```json
{{
  "opening": "建议的开场白（1-2句话，直接可用）",
  "key_tactics": [
    {{"situation": "对方可能说/做的事", "response": "你应该这样回应（直接可用的话术）"}},
    {{"situation": "...", "response": "..."}}
  ],
  "pitfalls": ["避免说的话或做的事1", "避免说的话或做的事2"],
  "bottom_line": "如果主要目标达不成，退而求其次的策略（1-2句话）"
}}
```

规则：
- opening 必须是直接能说出口的话，不是抽象建议
- key_tactics 针对每个训练重点至少 1 条，每条 response 是直接可用的话术
- pitfalls 从对话中用户的实际失误提炼，2-4 条
- bottom_line 要具体可操作
"""

_DIFFICULTY_PROMPTS = {
    "easy": "你态度相对友好，愿意倾听，但会提出合理的质疑。",
    "normal": "你按照画像正常沟通，会质疑不充分的论点，但不会刻意刁难。",
    "hard": "你非常强势，会频繁打断、质疑数据来源、用情绪施压。",
}


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences from LLM output."""
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        raw = "\n".join(lines)
    return raw


class BattlePrepService:
    """Orchestrates the battle prep workflow: generate -> start -> cheat sheet."""

    def __init__(
        self,
        uow_factory: Callable[..., AbstractUnitOfWork],
        llm: LLMPort,
        chatroom_service: ChatRoomApplicationService,
        persona_editor: PersonaEditorService,
        persona_loader: PersonaLoader,
        persona_dir: str,
    ) -> None:
        self._uow_factory = uow_factory
        self._llm = llm
        self._chatroom_service = chatroom_service
        self._persona_editor = persona_editor
        self._persona_loader = persona_loader
        self._persona_dir = persona_dir

    def _cleanup_old_personas(self) -> None:
        """Delete temporary bp-* persona files older than 24 hours."""
        now = datetime.now(timezone.utc).timestamp()
        cutoff = 24 * 60 * 60

        for filename in os.listdir(self._persona_dir):
            if filename.startswith("bp-") and filename.endswith(".md"):
                filepath = os.path.join(self._persona_dir, filename)
                try:
                    age = now - os.path.getmtime(filepath)
                    if age > cutoff:
                        os.remove(filepath)
                        logger.info("Cleaned up old battle prep persona: %s", filename)
                except OSError:
                    pass

    async def generate_prep(self, description: str) -> BattlePrepResultDTO:
        """Step 1->2: User description -> LLM generates persona + scenario + training points."""
        prompt = _GENERATE_PROMPT.format(description=description)
        messages = [LLMMessage(role="user", content=prompt)]
        response = await self._llm.generate(messages, temperature=0.4)

        raw = _strip_json_fences(response.content)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON for battle prep: %s", raw[:500])
            raise ValueError("AI 生成失败，请重试")

        points = parsed.get("training_points", [])
        if len(points) < 2:
            defaults = ["如何有效开场", "如何应对对方质疑"]
            points = points + defaults[: 2 - len(points)]

        return BattlePrepResultDTO(
            persona_name=parsed.get("persona_name", "对方"),
            persona_role=parsed.get("persona_role", "管理者"),
            persona_style=parsed.get("persona_style", ""),
            scenario_context=parsed.get("scenario_context", ""),
            training_points=points[:5],
        )

    async def start_battle(self, dto: StartBattleDTO) -> ChatRoomDTO:
        """Step 3->Chat: Create temp persona + room -> return room."""
        self._cleanup_old_personas()

        persona_id = f"bp-{uuid.uuid4().hex[:8]}"
        difficulty_instruction = _DIFFICULTY_PROMPTS.get(
            dto.difficulty, _DIFFICULTY_PROMPTS["normal"]
        )

        persona_content = (
            f"---\ntemporary: true\n---\n\n"
            f"# {dto.persona_name}\n\n"
            f"**职位**: {dto.persona_role}\n\n"
            f"## 沟通风格\n\n{dto.persona_style}\n\n"
            f"## 对话场景\n\n{dto.scenario_context}\n\n"
            f"## 难度指令\n\n{difficulty_instruction}\n\n"
            f"## 训练重点\n\n"
            f"用户选择了以下训练重点，请在对话中重点围绕这些方面施压和互动：\n"
        )
        for point in dto.selected_training_points:
            persona_content += f"- {point}\n"

        persona_content += (
            "\n## 备战模式特殊指令\n\n"
            "这是一场限时备战练习（最多12轮）。"
            "当你认为所有训练重点都已经充分讨论过（通常在第6轮之后），"
            "你可以自然地结束对话（如'我觉得这个方案基本可以，我们就这么定了'）。"
            "但如果用户还有明显未覆盖的训练重点，继续施压。"
        )

        self._persona_editor.create_persona(
            CreatePersonaDTO(
                id=persona_id,
                name=dto.persona_name,
                role=dto.persona_role,
                avatar_color="#6366f1",
                content=persona_content,
            )
        )

        room = await self._chatroom_service.create_room(
            CreateChatRoomDTO(
                name=f"备战: {dto.persona_name}",
                type="battle_prep",
                persona_ids=[persona_id],
            )
        )

        return room

    async def create_room_from_persona(self, persona_id: str) -> ChatRoomDTO:
        """Story 2.8 (AC1): create a private chatroom using an existing persona.

        Unlike start_battle (which creates a brand new temp bp-* persona), this
        reuses an already-persisted persona (v1 markdown or v2 DB). Called from
        the Persona Editor page's "开始演练" button.
        """
        persona = self._persona_loader.get_persona(persona_id)
        if persona is None:
            raise ValueError(f"Persona {persona_id} not found")
        return await self._chatroom_service.create_room(
            CreateChatRoomDTO(
                name=f"演练: {persona.name}",
                type="private",
                persona_ids=[persona_id],
            )
        )

    async def generate_cheat_sheet(self, room_id: int) -> CheatSheetDTO:
        """Post-conversation: generate cheat sheet from conversation history."""
        detail = await self._chatroom_service.get_room_detail(room_id, message_limit=200)
        room = detail.room
        messages = detail.messages

        if not messages:
            raise ValueError("对话记录为空，无法生成话术纸条")

        lines: list[str] = []
        for msg in messages:
            if msg.sender_type == "system":
                continue
            if msg.sender_type == "user":
                lines.append(f"[用户]: {msg.content}")
            else:
                p = self._persona_loader.get_persona(msg.sender_id)
                name = p.name if p else msg.sender_id
                lines.append(f"[{name}]: {msg.content}")

        conversation_text = "\n\n".join(lines)

        persona_id = room.persona_ids[0] if room.persona_ids else ""
        persona = self._persona_loader.get_persona(persona_id)
        scenario_context = ""
        training_points = ""
        if persona:
            scenario_context = f"与 {persona.name}（{persona.role}）的备战对话"

        prompt = _CHEAT_SHEET_PROMPT.format(
            scenario_context=scenario_context,
            training_points=training_points or "（未指定）",
            conversation=conversation_text,
        )

        llm_messages = [LLMMessage(role="user", content=prompt)]
        response = await self._llm.generate(llm_messages, temperature=0.3)

        raw = _strip_json_fences(response.content)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON for cheat sheet: %s", raw[:500])
            raise ValueError("话术纸条生成失败，请重试")

        tactics = []
        for t in parsed.get("key_tactics", []):
            if isinstance(t, dict):
                tactics.append(
                    TacticItem(
                        situation=t.get("situation", ""),
                        response=t.get("response", ""),
                    )
                )

        return CheatSheetDTO(
            opening=parsed.get("opening", ""),
            key_tactics=tactics,
            pitfalls=parsed.get("pitfalls", []),
            bottom_line=parsed.get("bottom_line", ""),
        )
