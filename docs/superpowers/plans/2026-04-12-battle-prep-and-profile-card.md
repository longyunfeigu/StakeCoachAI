# 紧急备战模式 & 谈判力名片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two features to DaBoss: Battle Prep Mode (pre-meeting quick simulation with cheat sheet output) and Profile Card (6-dimension social sharing card generated from growth data).

**Architecture:** Both features build on existing DDD layers. Battle Prep adds a new application service (`BattlePrepService`) that orchestrates LLM calls, temporary persona creation, and room creation. Profile Card extends the existing `GrowthService`. Frontend adds 5 new components (dialog, cheat sheet, profile card) and modifies App.tsx sidebar + chat interface.

**Tech Stack:** FastAPI, SQLAlchemy, Anthropic Claude LLM, React 18 + TypeScript, Vite, html2canvas (new dependency)

**Spec:** `docs/superpowers/specs/2026-04-12-battle-prep-and-profile-card-design.md`

---

## File Structure

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `backend/application/services/stakeholder/battle_prep_service.py` | Battle Prep orchestration: generate_prep, start_battle, generate_cheat_sheet |

### Backend — Modified Files
| File | Changes |
|------|---------|
| `backend/domain/stakeholder/entity.py:15,33,38` | Add `"battle_prep"` to `_ROOM_TYPES`, update docstring and inline comment |
| `backend/application/services/stakeholder/dto.py` | Add 7 new DTOs: BattlePrepGenerateDTO, BattlePrepResultDTO, StartBattleDTO, TacticItem, CheatSheetDTO, ProfileTag, ProfileCardDTO. Update CreateChatRoomDTO type pattern. |
| `backend/application/services/stakeholder/growth_service.py` | Add `generate_profile_card()` method |
| `backend/api/routes/stakeholder.py` | Add 4 new endpoints + update export type_label + add 12-round backend guard for battle_prep rooms in send_message |
| `backend/application/services/stakeholder/stakeholder_chat_service.py` | Add battle_prep 12-round limit check in send_message |
| `backend/api/dependencies.py` | Add `get_battle_prep_service()` |

### Frontend — New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/components/BattlePrepDialog.tsx` | Three-step guided dialog (describe → preview persona → select training points) |
| `frontend/src/components/BattlePrepDialog.css` | Styles for battle prep dialog |
| `frontend/src/components/CheatSheet.tsx` | Cheat sheet display dialog with copy/download |
| `frontend/src/components/CheatSheet.css` | Styles for cheat sheet |
| `frontend/src/components/ProfileCard.tsx` | Card rendering component (white bg + tags + progress bars) |
| `frontend/src/components/ProfileCardDialog.tsx` | Dialog wrapper with download button |
| `frontend/src/components/ProfileCard.css` | Styles for profile card |

### Frontend — Modified Files
| File | Changes |
|------|---------|
| `frontend/src/services/api.ts` | Add types + 4 API functions: generateBattlePrep, startBattle, generateCheatSheet, generateProfileCard |
| `frontend/src/App.tsx` | Sidebar button, battle_prep room handling, round counter, cheat sheet trigger |
| `frontend/src/App.css` | battle-prep-btn styles |
| `frontend/src/components/GrowthDashboard.tsx` | Add "生成我的名片" button |
| `frontend/src/components/RoomList.tsx` | Filter out battle_prep rooms from regular list |

---

## Task 1: Domain & DTO Foundation

**Files:**
- Modify: `backend/domain/stakeholder/entity.py:15`
- Modify: `backend/application/services/stakeholder/dto.py`

- [ ] **Step 1: Extend ChatRoom type enum**

In `backend/domain/stakeholder/entity.py`:

Line 15, change:
```python
_ROOM_TYPES = {"private", "group"}
```
to:
```python
_ROOM_TYPES = {"private", "group", "battle_prep"}
```

Line 33, update docstring:
```python
"""A chat room for stakeholder simulation (private, group, or battle_prep)."""
```

Line 38, update inline comment:
```python
type: str  # private | group | battle_prep
```

- [ ] **Step 2: Update CreateChatRoomDTO type pattern**

In `backend/application/services/stakeholder/dto.py`, line 21, change:
```python
type: str = Field(..., pattern=r"^(private|group)$")
```
to:
```python
type: str = Field(..., pattern=r"^(private|group|battle_prep)$")
```

- [ ] **Step 3: Add Battle Prep DTOs**

Append to `backend/application/services/stakeholder/dto.py`:

```python
# ---------------------------------------------------------------------------
# Battle Prep DTOs
# ---------------------------------------------------------------------------


class BattlePrepGenerateDTO(BaseModel):
    """Input: user's meeting description."""
    description: str = Field(..., min_length=10, max_length=5000)


class BattlePrepResultDTO(BaseModel):
    """Output: AI-generated persona + scenario + training points."""
    persona_name: str
    persona_role: str
    persona_style: str
    scenario_context: str
    training_points: list[str]


class StartBattleDTO(BaseModel):
    """Input: confirmed config from user."""
    persona_name: str = Field(..., min_length=1, max_length=100)
    persona_role: str = Field(..., min_length=1, max_length=200)
    persona_style: str = Field(..., min_length=1, max_length=2000)
    scenario_context: str = Field(..., min_length=1, max_length=5000)
    selected_training_points: list[str] = Field(..., min_length=1, max_length=5)
    difficulty: str = Field(default="normal", pattern=r"^(easy|normal|hard)$")


class TacticItem(BaseModel):
    """A single tactic in the cheat sheet."""
    situation: str
    response: str


class CheatSheetDTO(BaseModel):
    """Output: cheat sheet for the meeting."""
    opening: str
    key_tactics: list[TacticItem]
    pitfalls: list[str]
    bottom_line: str


# ---------------------------------------------------------------------------
# Profile Card DTOs
# ---------------------------------------------------------------------------


class ProfileTag(BaseModel):
    """A tag on the profile card."""
    text: str
    type: str = Field(..., pattern=r"^(strength|weakness|trait)$")


class ProfileCardDTO(BaseModel):
    """Output: profile card data."""
    style_label: str
    tags: list[ProfileTag]
    summary: str
    scores: dict[str, float]
```

- [ ] **Step 4: Verify backend starts**

Run: `cd /Users/guwanhua/git/StakeCoachAI/backend && python -c "from application.services.stakeholder.dto import BattlePrepGenerateDTO, ProfileCardDTO; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd /Users/guwanhua/git/StakeCoachAI
git add backend/domain/stakeholder/entity.py backend/application/services/stakeholder/dto.py
git commit -m "feat: add battle_prep room type and DTOs for battle prep + profile card"
```

---

## Task 2: BattlePrepService — generate_prep

**Files:**
- Create: `backend/application/services/stakeholder/battle_prep_service.py`

- [ ] **Step 1: Create BattlePrepService with generate_prep**

Create `backend/application/services/stakeholder/battle_prep_service.py`:

```python
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
    """Orchestrates the battle prep workflow: generate → start → cheat sheet."""

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
        persona_dir = self._persona_dir
        now = datetime.now(timezone.utc).timestamp()
        cutoff = 24 * 60 * 60  # 24 hours

        for filename in os.listdir(persona_dir):
            if filename.startswith("bp-") and filename.endswith(".md"):
                filepath = os.path.join(persona_dir, filename)
                try:
                    age = now - os.path.getmtime(filepath)
                    if age > cutoff:
                        os.remove(filepath)
                        logger.info("Cleaned up old battle prep persona: %s", filename)
                except OSError:
                    pass

    async def generate_prep(self, description: str) -> BattlePrepResultDTO:
        """Step 1→2: User description → LLM generates persona + scenario + training points."""
        prompt = _GENERATE_PROMPT.format(description=description)
        messages = [LLMMessage(role="user", content=prompt)]
        response = await self._llm.generate(messages, temperature=0.4)

        raw = _strip_json_fences(response.content)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON for battle prep: %s", raw[:500])
            raise ValueError("AI 生成失败，请重试")

        # Ensure at least 2 training points
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
        """Step 3→Chat: Create temp persona + room → return room."""
        self._cleanup_old_personas()

        # Create temporary persona
        persona_id = f"bp-{uuid.uuid4().hex[:8]}"
        difficulty_instruction = _DIFFICULTY_PROMPTS.get(dto.difficulty, _DIFFICULTY_PROMPTS["normal"])

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

        # Create battle_prep room
        room = await self._chatroom_service.create_room(
            CreateChatRoomDTO(
                name=f"备战: {dto.persona_name}",
                type="battle_prep",
                persona_ids=[persona_id],
            )
        )

        return room

    async def generate_cheat_sheet(self, room_id: int) -> CheatSheetDTO:
        """Post-conversation: generate cheat sheet from conversation history."""
        # Load room and messages
        detail = await self._chatroom_service.get_room_detail(room_id, message_limit=200)
        room = detail.room
        messages = detail.messages

        if not messages:
            raise ValueError("对话记录为空，无法生成话术纸条")

        # Build conversation text
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

        # Extract scenario context and training points from persona content
        persona_id = room.persona_ids[0] if room.persona_ids else ""
        persona = self._persona_loader.get_persona(persona_id)
        scenario_context = ""
        training_points = ""
        if persona and persona.full_content:
            content = persona.full_content
            if "## 对话场景" in content:
                sc_section = content.split("## 对话场景")[1].split("##")[0]
                scenario_context = sc_section.strip()
            if "## 训练重点" in content:
                tp_section = content.split("## 训练重点")[1].split("##")[0]
                training_points = tp_section.strip()
            if not scenario_context:
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
                tactics.append(TacticItem(
                    situation=t.get("situation", ""),
                    response=t.get("response", ""),
                ))

        return CheatSheetDTO(
            opening=parsed.get("opening", ""),
            key_tactics=tactics,
            pitfalls=parsed.get("pitfalls", []),
            bottom_line=parsed.get("bottom_line", ""),
        )
```

- [ ] **Step 2: Verify import**

Run: `cd /Users/guwanhua/git/StakeCoachAI/backend && python -c "from application.services.stakeholder.battle_prep_service import BattlePrepService; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/guwanhua/git/StakeCoachAI
git add backend/application/services/stakeholder/battle_prep_service.py
git commit -m "feat: add BattlePrepService with generate_prep, start_battle, generate_cheat_sheet"
```

---

## Task 3: Profile Card — GrowthService Extension

**Files:**
- Modify: `backend/application/services/stakeholder/growth_service.py`

- [ ] **Step 1: Add profile card prompt and method to GrowthService**

Add to `backend/application/services/stakeholder/growth_service.py`, after the `_INSIGHT_SYSTEM_PROMPT` constant (around line 126):

```python
_PROFILE_CARD_PROMPT = """\
你是一个职场沟通分析师。请根据用户的多次沟通能力评估数据，生成一个简短的"沟通力画像"。

## 评估数据

{evaluation_data}

## 输出要求

输出严格 JSON，不要输出其他内容：

```json
{{
  "style_label": "2-6个字的风格标签（如：数据驱动型说服者、温和共情型领导者、逻辑攻坚型谈判手）",
  "tags": [
    {{"text": "#标签内容", "type": "strength 或 weakness 或 trait"}},
    {{"text": "#标签内容", "type": "strength 或 weakness 或 trait"}}
  ],
  "summary": "一句话点评（20-40字，指出最突出的优势和最需要提升的方向）"
}}
```

规则：
- style_label 像 MBTI 标签一样简短有辨识度，2-6 个字
- tags 3-4 个，优势用 strength、弱项用 weakness、中性特征用 trait
- summary 语气正向但诚实，不要空洞表扬
- 必须基于具体分数，不允许编造数据
"""
```

Then add the method to the `GrowthService` class:

```python
    async def generate_profile_card(self) -> Optional["ProfileCardDTO"]:
        """Generate a profile card from historical competency data."""
        from application.services.stakeholder.dto import ProfileCardDTO, ProfileTag

        async with self._uow_factory(readonly=True) as uow:
            evaluations = await uow.competency_evaluation_repository.list_all(limit=500)

        if len(evaluations) < 2:
            return ProfileCardDTO(
                style_label="",
                tags=[],
                summary="练习次数还不够，至少完成 2 次对话分析后才能生成沟通力名片。继续练习吧！",
                scores={},
            )

        # Calculate average scores per dimension
        dim_totals: dict[str, list[float]] = {}
        for ev in evaluations:
            for dim in COMPETENCY_DIMENSIONS:
                dim_data = ev.scores.get(dim, {})
                score = dim_data.get("score", 0) if isinstance(dim_data, dict) else 0
                if score > 0:
                    dim_totals.setdefault(dim, []).append(float(score))

        avg_scores: dict[str, float] = {}
        for dim in COMPETENCY_DIMENSIONS:
            vals = dim_totals.get(dim, [])
            avg_scores[dim] = round(sum(vals) / len(vals), 1) if vals else 0.0

        # Build evaluation summary for LLM
        dim_labels = {
            "persuasion": "说服力",
            "emotional_management": "情绪管理",
            "active_listening": "倾听回应",
            "structured_expression": "结构化表达",
            "conflict_resolution": "冲突处理",
            "stakeholder_alignment": "利益对齐",
        }

        lines = [f"共 {len(evaluations)} 次评估\n"]
        for dim in COMPETENCY_DIMENSIONS:
            label = dim_labels.get(dim, dim)
            avg = avg_scores[dim]
            vals = dim_totals.get(dim, [])
            if len(vals) >= 2:
                trend = "进步" if vals[-1] > vals[0] else ("退步" if vals[-1] < vals[0] else "稳定")
            else:
                trend = "数据不足"
            lines.append(f"- {label}: 平均 {avg}/5 ({trend})")

        # Include evidence from the most recent 3 evaluations
        recent_evals = evaluations[-3:]
        for i, ev in enumerate(recent_evals, 1):
            lines.append(f"\n### 最近第 {i} 次评估")
            for dim in COMPETENCY_DIMENSIONS:
                dim_data = ev.scores.get(dim, {})
                if isinstance(dim_data, dict):
                    evidence = dim_data.get("evidence", "")
                    if evidence:
                        lines.append(f"- {dim_labels.get(dim, dim)}: {evidence}")

        evaluation_data = "\n".join(lines)
        prompt = _PROFILE_CARD_PROMPT.format(evaluation_data=evaluation_data)

        llm_messages = [LLMMessage(role="user", content=prompt)]
        response = await self._llm.generate(llm_messages, temperature=0.4)

        raw_text = response.content.strip()
        if raw_text.startswith("```"):
            text_lines = raw_text.split("\n")
            text_lines = [l for l in text_lines if not l.strip().startswith("```")]
            raw_text = "\n".join(text_lines)

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON for profile card: %s", raw_text[:500])
            return None

        tags = []
        for t in parsed.get("tags", []):
            if isinstance(t, dict):
                tag_type = t.get("type", "trait")
                if tag_type not in ("strength", "weakness", "trait"):
                    tag_type = "trait"
                tags.append(ProfileTag(text=t.get("text", ""), type=tag_type))

        return ProfileCardDTO(
            style_label=parsed.get("style_label", "沟通探索者"),
            tags=tags,
            summary=parsed.get("summary", ""),
            scores=avg_scores,
        )
```

- [ ] **Step 2: Verify import**

Run: `cd /Users/guwanhua/git/StakeCoachAI/backend && python -c "from application.services.stakeholder.growth_service import GrowthService; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/guwanhua/git/StakeCoachAI
git add backend/application/services/stakeholder/growth_service.py
git commit -m "feat: add generate_profile_card() to GrowthService"
```

---

## Task 4: API Routes & Dependency Injection

**Files:**
- Modify: `backend/api/dependencies.py`
- Modify: `backend/api/routes/stakeholder.py`

- [ ] **Step 1: Add DI for BattlePrepService**

Add to `backend/api/dependencies.py`, after the `get_growth_service` function (around line 191):

```python
async def get_battle_prep_service(
    loader: PersonaLoader = Depends(get_persona_loader),
    editor: PersonaEditorService = Depends(get_persona_editor_service),
    llm: LLMPort = Depends(get_stakeholder_llm_port),
    chatroom_svc: ChatRoomApplicationService = Depends(get_chatroom_service),
):
    from application.services.stakeholder.battle_prep_service import BattlePrepService

    return BattlePrepService(
        uow_factory=SQLAlchemyUnitOfWork,
        llm=llm,
        chatroom_service=chatroom_svc,
        persona_editor=editor,
        persona_loader=loader,
        persona_dir=settings.stakeholder.persona_dir,
    )
```

Also add the import at the top of the file if not present — but since `BattlePrepService` is imported inline above, no top-level import needed (matches existing pattern for `GrowthService`, `OrganizationService`).

- [ ] **Step 2: Add API routes**

Add to `backend/api/routes/stakeholder.py`, before the Growth Dashboard section (around line 935):

```python
# ---------------------------------------------------------------------------
# Battle Prep endpoints
# ---------------------------------------------------------------------------


@router.post("/battle-prep/generate", summary="生成备战角色和场景")
async def generate_battle_prep(
    body: BattlePrepGenerateDTO,
    svc=Depends(get_battle_prep_service),
):
    try:
        result = await svc.generate_prep(body.description)
        return success_response(data=result.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/battle-prep/start", summary="开始备战对话", status_code=201)
async def start_battle(
    body: StartBattleDTO,
    svc=Depends(get_battle_prep_service),
):
    room = await svc.start_battle(body)
    return success_response(data=room.model_dump())


@router.post("/rooms/{room_id}/cheatsheet", summary="生成话术纸条")
async def generate_cheat_sheet(
    room_id: int,
    svc=Depends(get_battle_prep_service),
):
    try:
        sheet = await svc.generate_cheat_sheet(room_id)
        return success_response(data=sheet.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

Add the profile card route in the Growth Dashboard section (after the existing `generate_growth_insight` endpoint around line 955):

```python
@router.post("/growth/card", summary="生成沟通力名片")
async def generate_profile_card(
    svc=Depends(get_growth_service),
):
    result = await svc.generate_profile_card()
    if result is None:
        raise HTTPException(status_code=502, detail="名片生成失败，请重试")
    return success_response(data=result.model_dump())
```

Update imports at the top of `stakeholder.py` — add to the existing `from application.services.stakeholder.dto import` block:

```python
BattlePrepGenerateDTO,
StartBattleDTO,
```

And add the dependency import:
```python
from api.dependencies import (
    ...
    get_battle_prep_service,
)
```

- [ ] **Step 3: Add backend 12-round enforcement for battle_prep rooms**

In `backend/api/routes/stakeholder.py`, in the `send_message` route handler (around line 411), add a guard before calling `svc.send_message`:

```python
@router.post("/rooms/{room_id}/messages", summary="发送消息", status_code=201)
async def send_message(
    room_id: int,
    body: SendMessageDTO,
    background_tasks: BackgroundTasks,
    svc: StakeholderChatService = Depends(get_stakeholder_chat_service),
    chatroom_svc: ChatRoomApplicationService = Depends(get_chatroom_service),
):
    # Battle prep 12-round limit enforcement
    detail = await chatroom_svc.get_room_detail(room_id, message_limit=200)
    if detail.room.type == "battle_prep":
        user_msg_count = sum(1 for m in detail.messages if m.sender_type == "user")
        if user_msg_count >= 12:
            raise HTTPException(status_code=422, detail="备战对话已达到 12 轮上限，请结束备战生成话术纸条")

    msg, room = await svc.send_message(room_id, body.content)
    background_tasks.add_task(svc.generate_replies, room_id, room)
    return success_response(data=msg.model_dump())
```

Add `get_chatroom_service` to the dependencies import if not already present.

- [ ] **Step 4: Update export endpoint type_label**

In `backend/api/routes/stakeholder.py`, in the `export_room` function (around line 217), change:
```python
type_label = "群聊" if room.type == "group" else "私聊"
```
to:
```python
_type_labels = {"group": "群聊", "private": "私聊", "battle_prep": "备战"}
type_label = _type_labels.get(room.type, room.type)
```

Do the same in `export_room_html` (around line 274).

- [ ] **Step 4: Verify server starts**

Run: `cd /Users/guwanhua/git/StakeCoachAI/backend && python -c "from api.routes.stakeholder import router; print('Routes:', len(router.routes))"`
Expected: prints route count without errors

- [ ] **Step 5: Commit**

```bash
cd /Users/guwanhua/git/StakeCoachAI
git add backend/api/dependencies.py backend/api/routes/stakeholder.py
git commit -m "feat: add battle prep + profile card API endpoints and DI"
```

---

## Task 5: Frontend API Layer

**Files:**
- Modify: `frontend/src/services/api.ts`

- [ ] **Step 1: Add types and API functions**

Add to `frontend/src/services/api.ts`, update the `ChatRoom` interface type:

```typescript
export interface ChatRoom {
  id: number
  name: string
  type: 'private' | 'group' | 'battle_prep'
  persona_ids: string[]
  created_at: string | null
  last_message_at: string | null
}
```

Then append these types and functions at the end of the file:

```typescript
// ---------------------------------------------------------------------------
// Battle Prep
// ---------------------------------------------------------------------------

export interface BattlePrepResult {
  persona_name: string
  persona_role: string
  persona_style: string
  scenario_context: string
  training_points: string[]
}

export interface TacticItem {
  situation: string
  response: string
}

export interface CheatSheet {
  opening: string
  key_tactics: TacticItem[]
  pitfalls: string[]
  bottom_line: string
}

export async function generateBattlePrep(description: string): Promise<BattlePrepResult> {
  const resp = await fetch(`${API_BASE}/battle-prep/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description }),
  })
  if (!resp.ok) {
    const json = await resp.json().catch(() => null)
    throw new Error(json?.message || `生成失败: ${resp.status}`)
  }
  const json: ApiResponse<BattlePrepResult> = await resp.json()
  return json.data
}

export async function startBattle(data: {
  persona_name: string
  persona_role: string
  persona_style: string
  scenario_context: string
  selected_training_points: string[]
  difficulty: 'easy' | 'normal' | 'hard'
}): Promise<ChatRoom> {
  const resp = await fetch(`${API_BASE}/battle-prep/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!resp.ok) throw new Error(`Failed to start battle: ${resp.status}`)
  const json: ApiResponse<ChatRoom> = await resp.json()
  return json.data
}

export async function generateCheatSheet(roomId: number): Promise<CheatSheet> {
  const resp = await fetch(`${API_BASE}/rooms/${roomId}/cheatsheet`, {
    method: 'POST',
  })
  if (!resp.ok) {
    const json = await resp.json().catch(() => null)
    throw new Error(json?.message || `生成失败: ${resp.status}`)
  }
  const json: ApiResponse<CheatSheet> = await resp.json()
  return json.data
}

// ---------------------------------------------------------------------------
// Profile Card
// ---------------------------------------------------------------------------

export interface ProfileTag {
  text: string
  type: 'strength' | 'weakness' | 'trait'
}

export interface ProfileCard {
  style_label: string
  tags: ProfileTag[]
  summary: string
  scores: Record<string, number>
}

export async function generateProfileCard(): Promise<ProfileCard> {
  const resp = await fetch(`${API_BASE}/growth/card`, { method: 'POST' })
  if (!resp.ok) {
    const json = await resp.json().catch(() => null)
    throw new Error(json?.message || `生成失败: ${resp.status}`)
  }
  const json: ApiResponse<ProfileCard> = await resp.json()
  return json.data
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/guwanhua/git/StakeCoachAI
git add frontend/src/services/api.ts
git commit -m "feat: add battle prep + profile card API client functions"
```

---

## Task 6: BattlePrepDialog Component

**Files:**
- Create: `frontend/src/components/BattlePrepDialog.tsx`
- Create: `frontend/src/components/BattlePrepDialog.css`

- [ ] **Step 1: Create BattlePrepDialog.tsx**

Create `frontend/src/components/BattlePrepDialog.tsx` — a three-step guided dialog:
- Step 1: Large textarea for meeting description
- Step 2: Persona preview card (editable name/role/style) + difficulty selector (3 radio buttons)
- Step 3: Training point checkboxes + "开始备战" button

Key behaviors:
- Step 1→2 transition calls `generateBattlePrep(description)` with loading spinner
- Step 2 fields are editable (controlled inputs pre-filled from API result)
- Step 3 checkboxes start all checked, user can uncheck (min 1 required)
- "开始备战" calls `startBattle()` → returns roomId → calls `onStarted(roomId)`
- Props: `open: boolean`, `onClose: () => void`, `onStarted: (roomId: number) => void`

- [ ] **Step 2: Create BattlePrepDialog.css**

Style the dialog matching existing dialog patterns in the project (overlay + centered card). Key elements:
- `.battle-prep-overlay` — fullscreen overlay
- `.battle-prep-dialog` — centered card, max-width 560px
- `.battle-prep-step` — step container with transition
- `.battle-prep-textarea` — large input area
- `.persona-preview` — card with editable fields
- `.difficulty-selector` — radio group
- `.training-points` — checkbox list
- `.battle-prep-actions` — bottom button row

- [ ] **Step 3: Commit**

```bash
cd /Users/guwanhua/git/StakeCoachAI
git add frontend/src/components/BattlePrepDialog.tsx frontend/src/components/BattlePrepDialog.css
git commit -m "feat: add BattlePrepDialog three-step guided component"
```

---

## Task 7: CheatSheet Component

**Files:**
- Create: `frontend/src/components/CheatSheet.tsx`
- Create: `frontend/src/components/CheatSheet.css`

- [ ] **Step 1: Create CheatSheet.tsx**

Create `frontend/src/components/CheatSheet.tsx` — dialog displaying the cheat sheet:
- Header: scenario name + persona name
- Four sections: 开场白, 关键话术 (situation→response pairs), 避坑提醒, 底线策略
- Footer: "复制全文" button (copies as plain text via `navigator.clipboard`) + "下载图片" button (html2canvas)
- Props: `open: boolean`, `onClose: () => void`, `data: CheatSheet | null`, `personaName: string`

For the download button, use `html2canvas`:
```typescript
import html2canvas from 'html2canvas'

const handleDownload = async () => {
  const el = cardRef.current
  if (!el) return
  const canvas = await html2canvas(el, { scale: 2, backgroundColor: '#fff' })
  const link = document.createElement('a')
  link.download = '话术纸条.png'
  link.href = canvas.toDataURL('image/png')
  link.click()
}
```

- [ ] **Step 2: Create CheatSheet.css**

Styles for the cheat sheet dialog. Key: the cheat sheet card itself should be a self-contained div (ref'd for html2canvas), max-width 400px, clean layout with section dividers.

- [ ] **Step 3: Install html2canvas**

Run: `cd /Users/guwanhua/git/StakeCoachAI/frontend && npm install html2canvas`

- [ ] **Step 4: Commit**

```bash
cd /Users/guwanhua/git/StakeCoachAI
git add frontend/src/components/CheatSheet.tsx frontend/src/components/CheatSheet.css frontend/package.json frontend/package-lock.json
git commit -m "feat: add CheatSheet component with copy and image download"
```

---

## Task 8: ProfileCard & ProfileCardDialog Components

**Files:**
- Create: `frontend/src/components/ProfileCard.tsx`
- Create: `frontend/src/components/ProfileCardDialog.tsx`
- Create: `frontend/src/components/ProfileCard.css`

- [ ] **Step 1: Create ProfileCard.tsx**

Create `frontend/src/components/ProfileCard.tsx` — pure rendering component matching the confirmed visual design:
- White background, 360px width, rounded corners
- Header: DaBoss logo square + "DABOSS PROFILE" label + style_label title
- Tags row: colored badges (green=strength, orange=weakness, blue=trait)
- 6 progress bars: dimension name + bar + score. Bar color: >=3.5 purple gradient (#4f46e5→#7c3aed), <3.5 orange-red gradient (#f59e0b→#ef4444)
- Summary: gray rounded box with quote text
- Footer: "DaBoss · 测测你的职场沟通风格 →"

Use dimension label mapping:
```typescript
const DIMENSION_LABELS: Record<string, string> = {
  persuasion: '说服力',
  emotional_management: '情绪管理',
  active_listening: '倾听回应',
  structured_expression: '结构表达',
  conflict_resolution: '冲突处理',
  stakeholder_alignment: '利益对齐',
}
```

Props: `data: ProfileCard` (from api.ts type), `cardRef?: React.RefObject<HTMLDivElement>`

- [ ] **Step 2: Create ProfileCardDialog.tsx**

Create `frontend/src/components/ProfileCardDialog.tsx`:
- Overlay + centered dialog
- Title: "我的沟通力名片"
- Renders ProfileCard inside
- Bottom buttons: "下载图片" (html2canvas same pattern as CheatSheet)
- Props: `open: boolean`, `onClose: () => void`, `data: ProfileCard | null`

- [ ] **Step 3: Create ProfileCard.css**

Styles for both components. The card itself uses inline-friendly styles for html2canvas compatibility (avoid external fonts, complex filters). Use CSS custom properties for the gradient colors.

- [ ] **Step 4: Commit**

```bash
cd /Users/guwanhua/git/StakeCoachAI
git add frontend/src/components/ProfileCard.tsx frontend/src/components/ProfileCardDialog.tsx frontend/src/components/ProfileCard.css
git commit -m "feat: add ProfileCard and ProfileCardDialog with image download"
```

---

## Task 9: App.tsx Integration — Sidebar & Battle Prep Flow

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add state variables and imports**

Add imports at top of App.tsx:
```typescript
import { Zap, Flag } from 'lucide-react'
import BattlePrepDialog from './components/BattlePrepDialog'
import CheatSheetComponent from './components/CheatSheet'
import ProfileCardDialog from './components/ProfileCardDialog'
import {
  generateCheatSheet,
  type CheatSheet as CheatSheetData,
  type ProfileCard as ProfileCardData,
} from './services/api'
```

Add state variables in `App()`:
```typescript
const [showBattlePrep, setShowBattlePrep] = useState(false)
const [cheatSheetData, setCheatSheetData] = useState<CheatSheetData | null>(null)
const [cheatSheetPersona, setCheatSheetPersona] = useState('')
const [battlePrepRoundCount, setBattlePrepRoundCount] = useState(0)
const [battlePrepTimeout, setBattlePrepTimeout] = useState<ReturnType<typeof setTimeout> | null>(null)
```

- [ ] **Step 2: Add sidebar button**

In the sidebar JSX, above the "成长轨迹" button (around line 761), add:
```tsx
<button
  className="battle-prep-btn"
  onClick={() => setShowBattlePrep(true)}
>
  <Zap size={16} />
  <span>紧急备战</span>
</button>
```

- [ ] **Step 3: Add battle prep room handling in chat view**

In the chat header area, when `selectedRoom.room.type === 'battle_prep'`:
- Show training points as tags in header
- Show "备战模式 · 剩余 X 轮" indicator
- Add "结束备战" button next to send button

Track rounds: increment `battlePrepRoundCount` on each user message send. When count >= 12 or user clicks "结束备战", call `generateCheatSheet(roomId)` and show the CheatSheet dialog.

Handle 30-minute timeout: reset a setTimeout on each send, on timeout call generateCheatSheet.

- [ ] **Step 4: Add battle prep started handler**

```typescript
const handleBattlePrepStarted = async (roomId: number) => {
  setShowBattlePrep(false)
  setBattlePrepRoundCount(0)
  setRefreshKey((k) => k + 1)
  setSelectedRoomId(roomId)
  try {
    const detail = await fetchRoomDetail(roomId)
    setSelectedRoom(detail)
  } catch {
    setSelectedRoom(null)
  }
}
```

- [ ] **Step 5: Render dialogs**

Add at the end of the JSX (before closing `</div>`):
```tsx
<BattlePrepDialog
  open={showBattlePrep}
  onClose={() => setShowBattlePrep(false)}
  onStarted={handleBattlePrepStarted}
/>

<CheatSheetComponent
  open={cheatSheetData !== null}
  onClose={() => setCheatSheetData(null)}
  data={cheatSheetData}
  personaName={cheatSheetPersona}
/>
```

- [ ] **Step 6: Add battle-prep-btn CSS to App.css**

```css
.battle-prep-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 16px;
  margin-bottom: 4px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.2s;
}
.battle-prep-btn:hover {
  opacity: 0.9;
}
```

- [ ] **Step 7: Update room type badge**

In the chat header badge rendering (around line 785), extend:
```tsx
<span className={`room-type-badge ${selectedRoom.room.type}`}>
  {selectedRoom.room.type === 'private' ? '私聊' : selectedRoom.room.type === 'group' ? '群聊' : '备战'}
</span>
```

- [ ] **Step 8: Commit**

```bash
cd /Users/guwanhua/git/StakeCoachAI
git add frontend/src/App.tsx frontend/src/App.css
git commit -m "feat: integrate battle prep flow into App.tsx sidebar and chat view"
```

---

## Task 10: GrowthDashboard — Profile Card Integration

**Files:**
- Modify: `frontend/src/components/GrowthDashboard.tsx`

- [ ] **Step 1: Add profile card state and button**

Import at top:
```typescript
import { Share2 } from 'lucide-react'
import ProfileCardDialog from './ProfileCardDialog'
import { generateProfileCard, type ProfileCard as ProfileCardData } from '../services/api'
```

Add state:
```typescript
const [profileCard, setProfileCard] = useState<ProfileCardData | null>(null)
const [profileCardLoading, setProfileCardLoading] = useState(false)
const [showProfileCard, setShowProfileCard] = useState(false)
```

Add handler:
```typescript
const handleGenerateCard = async () => {
  setProfileCardLoading(true)
  try {
    const card = await generateProfileCard()
    setProfileCard(card)
    setShowProfileCard(true)
  } catch (e) {
    console.error(e)
  } finally {
    setProfileCardLoading(false)
  }
}
```

- [ ] **Step 2: Add button in JSX**

After the growth insight section (around line 286), add:
```tsx
<div className="growth-card-section">
  <button
    className="profile-card-btn"
    onClick={handleGenerateCard}
    disabled={profileCardLoading || data.overview.total_evaluations < 2}
    title={data.overview.total_evaluations < 2 ? `再完成 ${2 - data.overview.total_evaluations} 次练习即可解锁` : ''}
  >
    {profileCardLoading ? <Loader2 size={14} className="spin" /> : <Share2 size={14} />}
    {profileCardLoading ? '生成中...' : '生成我的名片'}
  </button>
</div>

<ProfileCardDialog
  open={showProfileCard}
  onClose={() => setShowProfileCard(false)}
  data={profileCard}
/>
```

- [ ] **Step 3: Add CSS for the button in GrowthDashboard.css**

```css
.growth-card-section {
  margin-top: 16px;
  text-align: center;
}
.profile-card-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.2s;
}
.profile-card-btn:hover:not(:disabled) {
  opacity: 0.9;
}
.profile-card-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

- [ ] **Step 4: Commit**

```bash
cd /Users/guwanhua/git/StakeCoachAI
git add frontend/src/components/GrowthDashboard.tsx frontend/src/components/GrowthDashboard.css
git commit -m "feat: add profile card generation button to GrowthDashboard"
```

---

## Task 11: RoomList Filter & Final Polish

**Files:**
- Modify: `frontend/src/components/RoomList.tsx`

- [ ] **Step 1: Filter battle_prep rooms from regular room list**

In `frontend/src/components/RoomList.tsx`, after fetching rooms, filter out battle_prep rooms:

```typescript
const regularRooms = rooms.filter(r => r.type !== 'battle_prep')
```

Use `regularRooms` instead of `rooms` in the render loop.

- [ ] **Step 2: Manual smoke test**

Start backend and frontend:
```bash
cd /Users/guwanhua/git/StakeCoachAI/backend && uv run uvicorn main:app --reload --port 8000 &
cd /Users/guwanhua/git/StakeCoachAI/frontend && npm run dev &
```

Test checklist:
1. Sidebar shows "紧急备战" button with purple gradient
2. Click → BattlePrepDialog opens with textarea
3. Enter description → loading → persona preview appears
4. Select difficulty + confirm → training points appear
5. Select points + start → room created, chat opens with "备战" badge
6. Send messages → round counter shows
7. Click "结束备战" or reach 12 rounds → cheat sheet dialog appears
8. Copy and download buttons work
9. Growth Dashboard → "生成我的名片" button visible (disabled if < 2 evaluations)
10. If >= 2 evaluations → click generates card → dialog with download works

- [ ] **Step 3: Final commit**

```bash
cd /Users/guwanhua/git/StakeCoachAI
git add frontend/src/components/RoomList.tsx
git commit -m "feat: filter battle_prep rooms from regular room list"
```
