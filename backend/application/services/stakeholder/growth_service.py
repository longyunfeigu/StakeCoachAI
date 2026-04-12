# input: AbstractUnitOfWork, LLMPort, PersonaLoader
# output: GrowthService 能力评估 + Dashboard 聚合 + 成长洞察服务 + 沟通力画像生成
# owner: wanhua.gu
# pos: 应用层服务 - LLM-as-Judge 多维能力评估、Dashboard 数据聚合、跨 session 成长洞察；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Growth tracking service: competency evaluation, dashboard, and insights."""

from __future__ import annotations

import json
import logging
from typing import Callable, Optional

from application.ports.llm import LLMMessage, LLMPort
from application.services.stakeholder.dto import (
    CompetencyEvaluationDTO,
    DimensionScoreDTO,
    DimensionTrendPointDTO,
    GrowthDashboardDTO,
    GrowthInsightDTO,
    GrowthOverviewDTO,
)
from domain.common.unit_of_work import AbstractUnitOfWork
from domain.stakeholder.competency_entity import COMPETENCY_DIMENSIONS, CompetencyEvaluation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM-as-Judge Rubric Prompt
# ---------------------------------------------------------------------------

_JUDGE_SYSTEM_PROMPT = """\
你是一位专业的沟通能力评估师。请根据以下 Rubric 对用户在利益相关者模拟对话中的沟通表现打分。

## 参与角色

{persona_profiles}

## 对话记录

{conversation}

## 评分维度与标准

### 说服力 (persuasion)
- 1分：无有效论点，纯粹陈述观点
- 2分：有论点但缺乏支撑证据
- 3分：有论点和部分证据，但逻辑链不完整
- 4分：论点清晰、证据充分，有说服力
- 5分：论点精准、多角度论证、预判反驳

### 情绪管理 (emotional_management)
- 1分：明显情绪失控或强烈防守性回答
- 2分：在压力下偶尔失控
- 3分：基本保持冷静但有防守倾向
- 4分：压力下保持冷静，积极回应
- 5分：将对方压力转化为建设性对话

### 倾听回应 (active_listening)
- 1分：完全忽视对方观点，自说自话
- 2分：偶尔提及对方观点但未真正回应
- 3分：能复述对方观点但回应不够深入
- 4分：准确理解并回应对方关切，有追问
- 5分：深度倾听，挖掘对方未明确表达的需求

### 结构化表达 (structured_expression)
- 1分：表达混乱，没有逻辑结构
- 2分：有一定结构但铺垫过长，重点不突出
- 3分：基本清晰，先说结论但论述不够精炼
- 4分：结构清晰，结论先行，论据有序
- 5分：表达精准，金字塔结构，适配听众认知

### 冲突处理 (conflict_resolution)
- 1分：回避冲突或激化矛盾
- 2分：被动应对，缺乏策略
- 3分：能识别分歧但解决方案不够创造性
- 4分：主动管理冲突，提出双赢方案
- 5分：将冲突转化为建设性讨论，达成共识

### 利益对齐 (stakeholder_alignment)
- 1分：只关注自身诉求，忽视对方利益
- 2分：意识到对方利益但未主动对齐
- 3分：尝试寻找共同利益但不够精准
- 4分：准确识别共同利益并以此为锚点推进
- 5分：创造性地重构问题框架，实现多方利益最大化

## 输出要求

输出严格 JSON，不要输出其他内容：

```json
{{
  "persuasion": {{"score": 1-5, "evidence": "引用对话原文", "suggestion": "具体改进建议"}},
  "emotional_management": {{"score": 1-5, "evidence": "...", "suggestion": "..."}},
  "active_listening": {{"score": 1-5, "evidence": "...", "suggestion": "..."}},
  "structured_expression": {{"score": 1-5, "evidence": "...", "suggestion": "..."}},
  "conflict_resolution": {{"score": 1-5, "evidence": "...", "suggestion": "..."}},
  "stakeholder_alignment": {{"score": 1-5, "evidence": "...", "suggestion": "..."}}
}}
```

评分规则：
- evidence 必须引用对话中的具体内容，不要编造
- score 必须是 1-5 整数
- suggestion 必须具体可操作
- 如果对话太短无法判断某个维度，给 3 分并在 evidence 中说明
"""

_INSIGHT_SYSTEM_PROMPT = """\
你是一位资深的沟通教练。请根据用户在多次利益相关者模拟对话中的能力评估数据，\
生成一份简洁的成长洞察分析（200-400 字）。

## 评估数据

{evaluation_data}

## 要求

1. 识别用户最强和最弱的维度
2. 发现跨 session 的趋势（进步、退步、停滞）
3. 识别反复出现的模式（如"一被质疑就防守性回答"）
4. 给出 1-2 条最重要的下次练习建议
5. 必须引用具体分数变化，不允许编造数据
6. 语气鼓励但直接，不要空洞的表扬

直接输出分析文本，不要输出 JSON 或 Markdown 标题。
"""

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


# ---------------------------------------------------------------------------
# Helpers (reuse patterns from analysis_service)
# ---------------------------------------------------------------------------


def _build_conversation_text(history: list[dict], persona_loader) -> str:
    lines: list[str] = []
    for msg in history:
        sender_type = msg["sender_type"]
        if sender_type == "system":
            continue
        sender_id = msg["sender_id"]
        content = msg["content"]
        emotion = ""
        if msg.get("emotion_score") is not None:
            emotion = f" [情绪: {msg.get('emotion_label', '未知')}({msg['emotion_score']})]"
        if sender_type == "user":
            lines.append(f"[用户]{emotion}: {content}")
        elif sender_type == "persona":
            p = persona_loader.get_persona(sender_id) if persona_loader else None
            name = p.name if p else sender_id
            lines.append(f"[{name}]{emotion}: {content}")
    return "\n\n".join(lines)


def _build_persona_profiles(persona_ids: list[str], persona_loader) -> str:
    profiles: list[str] = []
    for pid in persona_ids:
        p = persona_loader.get_persona(pid)
        if p:
            profiles.append(f"- **{p.name}** ({pid}): {p.role}")
    return "\n".join(profiles) if profiles else "（无角色信息）"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class GrowthService:
    """Competency evaluation, dashboard aggregation, and growth insights."""

    def __init__(
        self,
        uow_factory: Callable[..., AbstractUnitOfWork],
        llm: LLMPort,
        persona_loader,
    ) -> None:
        self._uow_factory = uow_factory
        self._llm = llm
        self._persona_loader = persona_loader

    # ------------------------------------------------------------------
    # 1. Competency Evaluation (LLM-as-Judge)
    # ------------------------------------------------------------------

    async def evaluate_competency(self, report_id: int) -> Optional[CompetencyEvaluation]:
        """Evaluate user competency for a given analysis report.

        Idempotent: skips if evaluation already exists for report_id.
        """
        # Check idempotency
        async with self._uow_factory(readonly=True) as uow:
            existing = await uow.competency_evaluation_repository.get_by_report_id(report_id)
            if existing:
                logger.info(
                    "Competency evaluation already exists for report %d, skipping", report_id
                )
                return existing

        # Load report + room + messages
        async with self._uow_factory(readonly=True) as uow:
            report = await uow.analysis_report_repository.get_by_id(report_id)
            if report is None:
                logger.error("Report %d not found for competency evaluation", report_id)
                return None

            room = await uow.chat_room_repository.get_by_id(report.room_id)
            if room is None:
                logger.error("Room %d not found for competency evaluation", report.room_id)
                return None

            messages = await uow.stakeholder_message_repository.list_by_room_id(
                report.room_id, limit=200
            )

        if not messages:
            logger.warning("No messages in room %d for competency evaluation", report.room_id)
            return None

        # Build prompt
        history = [
            {
                "sender_type": m.sender_type,
                "sender_id": m.sender_id,
                "content": m.content,
                "emotion_score": m.emotion_score,
                "emotion_label": m.emotion_label,
            }
            for m in messages
        ]

        conversation_text = _build_conversation_text(history, self._persona_loader)
        persona_profiles = _build_persona_profiles(room.persona_ids, self._persona_loader)

        prompt = _JUDGE_SYSTEM_PROMPT.format(
            persona_profiles=persona_profiles,
            conversation=conversation_text,
        )

        # Call LLM
        llm_messages = [LLMMessage(role="user", content=prompt)]
        response = await self._llm.generate(llm_messages, temperature=0.2)

        # Parse JSON
        raw_text = response.content.strip()
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            raw_text = "\n".join(lines)

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON for competency eval: %s", raw_text[:500])
            return None

        # Validate and compute overall score
        scores: dict = {}
        total = 0
        count = 0
        for dim in COMPETENCY_DIMENSIONS:
            dim_data = parsed.get(dim, {})
            score = dim_data.get("score", 3)
            score = max(1, min(5, int(score)))
            scores[dim] = {
                "score": score,
                "evidence": str(dim_data.get("evidence", "")),
                "suggestion": str(dim_data.get("suggestion", "")),
            }
            total += score
            count += 1

        overall_score = round(total / count, 2) if count > 0 else 0.0

        # Persist
        evaluation = CompetencyEvaluation(
            id=None,
            report_id=report_id,
            room_id=report.room_id,
            scores=scores,
            overall_score=overall_score,
        )

        async with self._uow_factory() as uow:
            saved = await uow.competency_evaluation_repository.create(evaluation)

        logger.info(
            "Competency evaluation created for report %d, overall=%.2f",
            report_id,
            overall_score,
        )
        return saved

    # ------------------------------------------------------------------
    # 2. Dashboard Aggregation
    # ------------------------------------------------------------------

    async def get_dashboard(self) -> GrowthDashboardDTO:
        """Aggregate all competency evaluations into dashboard data."""
        async with self._uow_factory(readonly=True) as uow:
            rooms = await uow.chat_room_repository.list_rooms(limit=200)
            evaluations = await uow.competency_evaluation_repository.list_all(limit=500)

        room_map = {r.id: r.name for r in rooms}

        # Build evaluation DTOs
        eval_dtos: list[CompetencyEvaluationDTO] = []
        for ev in evaluations:
            dim_scores = {}
            for dim_key, dim_val in ev.scores.items():
                if isinstance(dim_val, dict):
                    dim_scores[dim_key] = DimensionScoreDTO(
                        score=dim_val.get("score", 3),
                        evidence=dim_val.get("evidence", ""),
                        suggestion=dim_val.get("suggestion", ""),
                    )
            eval_dtos.append(
                CompetencyEvaluationDTO(
                    id=ev.id,
                    report_id=ev.report_id,
                    room_id=ev.room_id,
                    room_name=room_map.get(ev.room_id, ""),
                    scores=dim_scores,
                    overall_score=ev.overall_score,
                    created_at=ev.created_at,
                )
            )

        # Overview
        total_evaluations = len(eval_dtos)
        avg_score = (
            round(sum(e.overall_score for e in eval_dtos) / total_evaluations, 2)
            if total_evaluations > 0
            else 0.0
        )
        latest_score = eval_dtos[-1].overall_score if eval_dtos else 0.0

        overview = GrowthOverviewDTO(
            total_sessions=len(rooms),
            total_evaluations=total_evaluations,
            avg_overall_score=avg_score,
            latest_score=latest_score,
        )

        # Dimension trends
        dimension_trends: dict[str, list[DimensionTrendPointDTO]] = {}
        for dim in COMPETENCY_DIMENSIONS:
            points: list[DimensionTrendPointDTO] = []
            for ev in eval_dtos:
                dim_dto = ev.scores.get(dim)
                if dim_dto:
                    points.append(DimensionTrendPointDTO(date=ev.created_at, score=dim_dto.score))
            dimension_trends[dim] = points

        return GrowthDashboardDTO(
            overview=overview,
            evaluations=eval_dtos,
            dimension_trends=dimension_trends,
        )

    # ------------------------------------------------------------------
    # 3. Growth Insight (cross-session LLM analysis)
    # ------------------------------------------------------------------

    async def generate_insight(self) -> GrowthInsightDTO:
        """Generate LLM-powered cross-session growth insight."""
        async with self._uow_factory(readonly=True) as uow:
            evaluations = await uow.competency_evaluation_repository.list_all(limit=500)
            rooms = await uow.chat_room_repository.list_rooms(limit=200)

        if len(evaluations) < 2:
            return GrowthInsightDTO(
                insight="练习次数还不够，至少完成 2 次对话分析后才能生成成长洞察。继续练习吧！"
            )

        room_map = {r.id: r.name for r in rooms}

        # Build evaluation data summary for prompt
        lines: list[str] = []
        for i, ev in enumerate(evaluations, 1):
            room_name = room_map.get(ev.room_id, f"Room {ev.room_id}")
            date_str = ev.created_at.strftime("%Y-%m-%d %H:%M") if ev.created_at else "unknown"
            lines.append(f"### 第 {i} 次评估 ({room_name}, {date_str})")
            lines.append(f"总分: {ev.overall_score}")
            for dim in COMPETENCY_DIMENSIONS:
                dim_data = ev.scores.get(dim, {})
                score = dim_data.get("score", "N/A")
                evidence = dim_data.get("evidence", "")
                suggestion = dim_data.get("suggestion", "")
                dim_label = {
                    "persuasion": "说服力",
                    "emotional_management": "情绪管理",
                    "active_listening": "倾听回应",
                    "structured_expression": "结构化表达",
                    "conflict_resolution": "冲突处理",
                    "stakeholder_alignment": "利益对齐",
                }.get(dim, dim)
                lines.append(f"- {dim_label}: {score}/5")
                # Include evidence/suggestion only for recent 3 evaluations
                if i > len(evaluations) - 3:
                    if evidence:
                        lines.append(f"  证据: {evidence}")
                    if suggestion:
                        lines.append(f"  建议: {suggestion}")
            lines.append("")

        evaluation_data = "\n".join(lines)
        prompt = _INSIGHT_SYSTEM_PROMPT.format(evaluation_data=evaluation_data)

        llm_messages = [LLMMessage(role="user", content=prompt)]
        response = await self._llm.generate(llm_messages, temperature=0.4)

        return GrowthInsightDTO(insight=response.content.strip())

    # ------------------------------------------------------------------
    # 4. Profile Card Generation
    # ------------------------------------------------------------------

    async def generate_profile_card(self):
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

        # Include evidence from recent evaluations
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
