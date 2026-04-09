# input: AbstractUnitOfWork, LLMPort, PersonaLoader
# output: AnalysisService 对话分析报告生成服务, AnalysisReaderService 只读报告查询服务
# owner: wanhua.gu
# pos: 应用层服务 - 利益相关者对话分析（AnalysisService=LLM 生成, AnalysisReaderService=只读查询）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Application service for generating stakeholder conversation analysis reports.

Uses LLM to analyze the full conversation history and produce structured insights:
- Resistance ranking: who opposed the most and why
- Effective arguments: which user arguments shifted attitudes
- Communication suggestions: actionable advice per persona
"""

from __future__ import annotations

import json
import logging
from typing import Callable, Optional

from application.ports.llm import LLMMessage, LLMPort
from application.services.stakeholder.prompt_builder import build_org_context
from application.services.stakeholder.dto import (
    AnalysisContentDTO,
    AnalysisReportDTO,
    AnalysisReportSummaryDTO,
)
from domain.common.exceptions import BusinessException
from domain.common.unit_of_work import AbstractUnitOfWork
from domain.stakeholder.entity import AnalysisReport
from shared.codes import BusinessCode

logger = logging.getLogger(__name__)

_ANALYSIS_SYSTEM_PROMPT = """\
你是一位专业的沟通策略分析师。请分析以下利益相关者模拟对话，输出严格 JSON 格式的分析报告。

## 参与角色

{persona_profiles}

## 对话记录

{conversation}

## 输出要求

请从三个维度分析，并输出以下 JSON 结构（不要输出其他内容，只输出 JSON）：

```json
{{
  "summary": "一段 50-100 字的整体分析摘要",
  "resistance_ranking": [
    {{
      "persona_id": "角色ID",
      "persona_name": "角色名称",
      "score": -5到5的整数（-5=强烈反对, 0=中立, 5=强烈支持）,
      "reason": "该角色为什么持这个态度，基于对话中的具体表现",
      "message_indices": [1, 3, 7]
    }}
  ],
  "effective_arguments": [
    {{
      "argument": "用户使用的具体论点",
      "target_persona": "这个论点主要影响了哪个角色",
      "effectiveness": "为什么这个论点有效，对方态度有什么变化",
      "message_indices": [5, 6]
    }}
  ],
  "communication_suggestions": [
    {{
      "persona_id": "角色ID",
      "persona_name": "角色名称",
      "suggestion": "针对这个角色的具体沟通建议",
      "priority": "high/medium/low"
    }}
  ]
}}
```

分析要点：
- resistance_ranking 按阻力从大到小排序（score 从低到高）
- effective_arguments 只列出确实产生了效果的论点，如果没有则为空数组
- communication_suggestions 要具体可操作，不要笼统的建议
- 基于对话中的情绪变化（emotion_score）和实际发言内容做判断
- message_indices 必须引用对话记录中 [#N] 的序号，列出支撑该结论的关键消息（通常 1-3 条最相关的）
"""


def _build_conversation_text(history: list[dict], persona_loader) -> tuple[str, dict[int, int]]:
    """Format conversation history into readable text for LLM analysis.

    Returns:
        Tuple of (conversation_text, message_id_map) where message_id_map
        maps 1-based sequence numbers to database message IDs.
    """
    lines: list[str] = []
    message_id_map: dict[int, int] = {}
    seq = 0
    for msg in history:
        sender_type = msg["sender_type"]
        if sender_type == "system":
            continue

        seq += 1
        msg_id = msg.get("id")
        if msg_id is not None:
            message_id_map[seq] = msg_id

        sender_id = msg["sender_id"]
        content = msg["content"]
        emotion = ""
        if msg.get("emotion_score") is not None:
            emotion = f" [情绪: {msg.get('emotion_label', '未知')}({msg['emotion_score']})]"

        if sender_type == "user":
            lines.append(f"[#{seq}] [用户]{emotion}: {content}")
        elif sender_type == "persona":
            p = persona_loader.get_persona(sender_id) if persona_loader else None
            name = p.name if p else sender_id
            lines.append(f"[#{seq}] [{name}]{emotion}: {content}")

    return "\n\n".join(lines), message_id_map


def _build_persona_profiles(persona_ids: list[str], persona_loader, org_context: str = "") -> str:
    """Build persona profile summaries for the analysis prompt."""
    profiles: list[str] = []
    for pid in persona_ids:
        p = persona_loader.get_persona(pid)
        if p:
            profiles.append(f"- **{p.name}** ({pid}): {p.role}")
    text = "\n".join(profiles) if profiles else "（无角色信息）"
    if org_context:
        text += f"\n\n{org_context}"
    return text


class AnalysisService:
    """Generates and persists LLM-powered conversation analysis reports."""

    def __init__(
        self,
        uow_factory: Callable[..., AbstractUnitOfWork],
        llm: LLMPort,
        persona_loader,
    ) -> None:
        self._uow_factory = uow_factory
        self._llm = llm
        self._persona_loader = persona_loader

    async def generate_report(self, room_id: int) -> AnalysisReportDTO:
        """Generate a new analysis report for the given room."""

        # 1. Load room and messages
        async with self._uow_factory(readonly=True) as uow:
            room = await uow.chat_room_repository.get_by_id(room_id)
            if room is None:
                raise BusinessException(
                    code=BusinessCode.CHATROOM_NOT_FOUND,
                    message=f"Chat room {room_id} not found",
                    error_type="ChatRoomNotFound",
                    details={"room_id": room_id},
                )

            messages = await uow.stakeholder_message_repository.list_by_room_id(room_id, limit=200)

        if not messages:
            raise BusinessException(
                code=BusinessCode.ANALYSIS_NO_MESSAGES,
                message="No messages to analyze",
                error_type="NoMessages",
                details={"room_id": room_id},
            )

        # 2. Build analysis prompt
        history = [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "sender_id": m.sender_id,
                "content": m.content,
                "emotion_score": m.emotion_score,
                "emotion_label": m.emotion_label,
            }
            for m in messages
        ]

        conversation_text, message_id_map = _build_conversation_text(history, self._persona_loader)

        # Build org context for analysis if any persona belongs to an org
        org_ctx = ""
        for pid in room.persona_ids:
            p = self._persona_loader.get_persona(pid)
            p_org_id = getattr(p, "organization_id", None) if p else None
            if p_org_id:
                async with self._uow_factory(readonly=True) as uow:
                    org = await uow.organization_repository.get_by_id(p_org_id)
                    if org:
                        rels = await uow.persona_relationship_repository.list_by_organization(
                            p.organization_id
                        )
                        rel_dicts = []
                        for r in rels:
                            fp = self._persona_loader.get_persona(r.from_persona_id)
                            tp = self._persona_loader.get_persona(r.to_persona_id)
                            rel_dicts.append(
                                {
                                    "persona_name": f"{fp.name if fp else r.from_persona_id} → {tp.name if tp else r.to_persona_id}",
                                    "relationship_type": r.relationship_type,
                                    "description": r.description,
                                }
                            )
                        org_ctx = build_org_context(
                            org_name=org.name,
                            org_context_prompt=org.context_prompt,
                            relationships=rel_dicts if rel_dicts else None,
                        )
                break

        persona_profiles = _build_persona_profiles(room.persona_ids, self._persona_loader, org_ctx)

        system_prompt = _ANALYSIS_SYSTEM_PROMPT.format(
            persona_profiles=persona_profiles,
            conversation=conversation_text,
        )

        # 3. Call LLM
        llm_messages = [LLMMessage(role="user", content=system_prompt)]
        response = await self._llm.generate(llm_messages, temperature=0.3)

        # 4. Parse response
        raw_text = response.content.strip()
        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            # Remove first line (```json) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw_text = "\n".join(lines)

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON for analysis: %s", raw_text[:500])
            raise BusinessException(
                code=BusinessCode.ANALYSIS_PARSE_ERROR,
                message="Failed to parse analysis report from LLM",
                error_type="AnalysisParseError",
                details={"room_id": room_id},
            )

        summary = parsed.get("summary", "分析完成")
        content_data = {
            "resistance_ranking": parsed.get("resistance_ranking", []),
            "effective_arguments": parsed.get("effective_arguments", []),
            "communication_suggestions": parsed.get("communication_suggestions", []),
            "message_id_map": {str(k): v for k, v in message_id_map.items()},
        }

        # 5. Validate with Pydantic (lenient: drop invalid items)
        try:
            content_dto = AnalysisContentDTO.model_validate(content_data)
        except Exception:
            logger.warning("Partial validation failure, using raw content")
            content_dto = AnalysisContentDTO(
                resistance_ranking=[],
                effective_arguments=[],
                communication_suggestions=[],
            )

        # 6. Persist
        report = AnalysisReport(
            id=None,
            room_id=room_id,
            summary=summary,
            content=content_dto.model_dump(),
        )

        async with self._uow_factory() as uow:
            saved = await uow.analysis_report_repository.create(report)

        return AnalysisReportDTO(
            id=saved.id,
            room_id=saved.room_id,
            summary=saved.summary,
            content=content_dto,
            created_at=saved.created_at,
        )

    async def get_report(self, report_id: int) -> Optional[AnalysisReportDTO]:
        """Get a single analysis report by ID."""
        async with self._uow_factory(readonly=True) as uow:
            report = await uow.analysis_report_repository.get_by_id(report_id)

        if report is None:
            return None

        content_dto = AnalysisContentDTO.model_validate(report.content)
        return AnalysisReportDTO(
            id=report.id,
            room_id=report.room_id,
            summary=report.summary,
            content=content_dto,
            created_at=report.created_at,
        )

    async def list_reports(
        self, room_id: int, *, skip: int = 0, limit: int = 50
    ) -> list[AnalysisReportSummaryDTO]:
        """List analysis reports for a room (summary only)."""
        async with self._uow_factory(readonly=True) as uow:
            reports = await uow.analysis_report_repository.list_by_room_id(
                room_id, skip=skip, limit=limit
            )

        return [
            AnalysisReportSummaryDTO(
                id=r.id,
                room_id=r.room_id,
                summary=r.summary,
                created_at=r.created_at,
            )
            for r in reports
        ]


class AnalysisReaderService:
    """Read-only service for querying existing analysis reports.

    Unlike AnalysisService, this does NOT require LLM or PersonaLoader
    dependencies — it only reads persisted reports from the database.
    """

    def __init__(self, uow_factory: Callable[..., AbstractUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def get_report(self, report_id: int) -> Optional[AnalysisReportDTO]:
        """Get a single analysis report by ID."""
        async with self._uow_factory(readonly=True) as uow:
            report = await uow.analysis_report_repository.get_by_id(report_id)

        if report is None:
            return None

        content_dto = AnalysisContentDTO.model_validate(report.content)
        return AnalysisReportDTO(
            id=report.id,
            room_id=report.room_id,
            summary=report.summary,
            content=content_dto,
            created_at=report.created_at,
        )

    async def list_reports(
        self, room_id: int, *, skip: int = 0, limit: int = 50
    ) -> list[AnalysisReportSummaryDTO]:
        """List analysis reports for a room (summary only)."""
        async with self._uow_factory(readonly=True) as uow:
            reports = await uow.analysis_report_repository.list_by_room_id(
                room_id, skip=skip, limit=limit
            )

        return [
            AnalysisReportSummaryDTO(
                id=r.id,
                room_id=r.room_id,
                summary=r.summary,
                created_at=r.created_at,
            )
            for r in reports
        ]
