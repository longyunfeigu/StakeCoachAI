# input: AbstractUnitOfWork, LLMPort, PersonaLoader
# output: CoachingService 交互式复盘 Coach 服务 + 实时求助 Live Coaching（无状态流式）
# owner: wanhua.gu
# pos: 应用层服务 - 基于分析报告的交互式 AI Coach 复盘对话（流式 SSE）+ 对话中途实时教练建议；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Application service for interactive coaching sessions based on analysis reports,
and stateless live coaching for mid-conversation advice.

After a conversation analysis report is generated, users can start a coaching
dialogue where an AI Coach asks probing questions about their decisions.
Coach replies are streamed via SSE events (message_delta / message_complete / done).

Live coaching (``prepare_live_advice`` / ``stream_live_advice``) is a lightweight,
stateless mode: no DB writes, no CoachingSession. The frontend keeps the coaching
exchange in memory and sends the full history on each follow-up request.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Callable, Optional

from application.ports.llm import LLMMessage, LLMPort
from application.services.stakeholder.analysis_service import _build_conversation_text
from application.services.stakeholder.prompt_builder import build_org_context
from application.services.stakeholder.dto import (
    CoachingMessageDTO,
    CoachingSessionDTO,
    CoachingSessionSummaryDTO,
)
from domain.common.exceptions import BusinessException
from domain.common.unit_of_work import AbstractUnitOfWork
from domain.stakeholder.entity import CoachingMessage, CoachingSession
from shared.codes import BusinessCode

logger = logging.getLogger(__name__)


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_coaching_system_prompt(
    report_summary: str,
    report_content: dict,
    conversation_text: str,
    org_context: str = "",
) -> str:
    """Build the system prompt for the coaching LLM."""
    # Format resistance ranking
    resistance_lines: list[str] = []
    for r in report_content.get("resistance_ranking", []):
        name = r.get("persona_name", r.get("persona_id", "?"))
        score = r.get("score", 0)
        reason = r.get("reason", "")
        resistance_lines.append(f"- {name} (分数: {score}): {reason}")
    resistance_text = "\n".join(resistance_lines) if resistance_lines else "（无数据）"

    # Format effective arguments
    arg_lines: list[str] = []
    for a in report_content.get("effective_arguments", []):
        arg_lines.append(
            f"- 论点: {a.get('argument', '')} → 影响: {a.get('target_persona', '')} — {a.get('effectiveness', '')}"
        )
    args_text = "\n".join(arg_lines) if arg_lines else "（未发现有效论点）"

    # Format communication suggestions
    sug_lines: list[str] = []
    for s in report_content.get("communication_suggestions", []):
        name = s.get("persona_name", s.get("persona_id", "?"))
        sug_lines.append(f"- [{s.get('priority', 'medium')}] {name}: {s.get('suggestion', '')}")
    suggestions_text = "\n".join(sug_lines) if sug_lines else "（无建议）"

    prompt = (
        "你是一位专业的沟通复盘教练。以下是用户与利益相关者的模拟对话分析报告。\n\n"
        f"## 分析摘要\n{report_summary}\n\n"
        f"## 阻力排名\n{resistance_text}\n\n"
        f"## 有效论点\n{args_text}\n\n"
        f"## 沟通建议\n{suggestions_text}\n\n"
        f"## 原始对话摘要\n{conversation_text}\n\n"
    )

    if org_context:
        prompt += f"{org_context}\n\n"

    prompt += (
        "## 你的任务\n"
        "1. 基于分析报告，向用户提出有针对性的反思问题\n"
        "2. 聚焦于阻力最大的角色和无效论点——用户在哪些关键时刻可以做得更好？\n"
        "3. 引导用户思考替代策略，而非直接给答案\n"
        "4. 每次回复以一个具体问题结尾，推动用户深入思考\n"
        "5. 语气温和但有挑战性，像资深导师\n"
        "6. 如果用户的回答展现了好的思路，给予肯定并追问如何在实际场景中应用\n"
        "7. 从组织政治角度给出建议（例：「在向上级汇报前，建议先和某某对齐」）\n"
    )
    return prompt


def _build_live_coaching_system_prompt(
    conversation_text: str,
    org_context: str = "",
) -> str:
    """Build the system prompt for live mid-conversation coaching."""
    prompt = (
        "你是一位实时沟通顾问，正在旁观用户与利益相关者的模拟对话。\n"
        "用户在对话中遇到困难，暂停来向你求助。\n\n"
        f"## 当前对话上下文\n{conversation_text}\n\n"
    )

    if org_context:
        prompt += f"{org_context}\n\n"

    prompt += (
        "## 你的任务\n"
        "1. 简要分析对方最后一条发言的意图和潜台词\n"
        "2. 给出 2-3 个回应策略，说明每种的优劣\n"
        "3. 推荐最适合的策略，附上可以直接使用的回应示例\n"
        "4. 语气像坐在旁边的资深同事——快速、直接、实用\n"
        "5. 保持简洁，用户需要尽快回去继续对话\n"
    )
    return prompt


class CoachingService:
    """Orchestrates interactive coaching sessions with streaming LLM responses."""

    def __init__(
        self,
        uow_factory: Callable[..., AbstractUnitOfWork],
        llm: LLMPort,
        persona_loader,
    ) -> None:
        self._uow_factory = uow_factory
        self._llm = llm
        self._persona_loader = persona_loader

    async def _build_room_org_context(self, room_id: int) -> str:
        """Build combined org context for all personas in a room."""
        async with self._uow_factory(readonly=True) as uow:
            room = await uow.chat_room_repository.get_by_id(room_id)
            if not room:
                return ""

            # Find first persona with an org_id
            org_id = None
            for pid in room.persona_ids:
                persona = self._persona_loader.get_persona(pid)
                p_org_id = getattr(persona, "organization_id", None) if persona else None
                if p_org_id:
                    org_id = p_org_id
                    break

            if not org_id:
                return ""

            org = await uow.organization_repository.get_by_id(org_id)
            if not org:
                return ""

            rels = await uow.persona_relationship_repository.list_by_organization(org_id)

        # Build a summary of all relationships
        rel_dicts: list[dict] = []
        for r in rels:
            from_p = self._persona_loader.get_persona(r.from_persona_id)
            to_p = self._persona_loader.get_persona(r.to_persona_id)
            rel_dicts.append(
                {
                    "persona_name": f"{from_p.name if from_p else r.from_persona_id} → {to_p.name if to_p else r.to_persona_id}",
                    "relationship_type": r.relationship_type,
                    "description": r.description,
                }
            )

        return build_org_context(
            org_name=org.name,
            org_context_prompt=org.context_prompt,
            relationships=rel_dicts if rel_dicts else None,
        )

    async def prepare_start_session(self, room_id: int, report_id: int) -> dict:
        """Validate inputs and prepare context for streaming.

        Must be awaited BEFORE creating StreamingResponse so that
        BusinessException is raised while the HTTP response hasn't started yet.
        """
        # 1. Load report and validate
        async with self._uow_factory(readonly=True) as uow:
            report = await uow.analysis_report_repository.get_by_id(report_id)
            if report is None or report.room_id != room_id:
                raise BusinessException(
                    code=BusinessCode.ANALYSIS_REPORT_NOT_FOUND,
                    message=f"Analysis report {report_id} not found for room {room_id}",
                    error_type="AnalysisReportNotFound",
                    details={"report_id": report_id, "room_id": room_id},
                )

            # 2. Load original conversation history (last 30 non-system messages)
            history_entities = await uow.stakeholder_message_repository.list_by_room_id(
                room_id, limit=200
            )

        history = [
            {
                "sender_type": m.sender_type,
                "sender_id": m.sender_id,
                "content": m.content,
                "emotion_score": m.emotion_score,
                "emotion_label": m.emotion_label,
            }
            for m in history_entities
        ]
        non_system = [h for h in history if h["sender_type"] != "system"]
        conversation_text = _build_conversation_text(non_system[-30:], self._persona_loader)

        # 3. Build org context + coaching system prompt
        org_ctx = await self._build_room_org_context(room_id)
        system_prompt = _build_coaching_system_prompt(
            report_summary=report.summary,
            report_content=report.content,
            conversation_text=conversation_text,
            org_context=org_ctx,
        )

        # 4. Create session entity
        async with self._uow_factory() as uow:
            session = CoachingSession(
                id=None,
                room_id=room_id,
                report_id=report_id,
            )
            session = await uow.coaching_session_repository.create(session)

        return {
            "session_id": session.id,
            "report_id": report_id,
            "system_prompt": system_prompt,
        }

    async def stream_opening(self, ctx: dict) -> AsyncIterator[str]:
        """Stream the Coach's opening message (call after prepare_start_session).

        Yields SSE events: session_created → message_delta* → message_complete → done.
        """
        session_id = ctx["session_id"]
        yield _sse_event(
            "session_created", {"session_id": session_id, "report_id": ctx["report_id"]}
        )

        llm_messages = [
            LLMMessage(role="system", content=ctx["system_prompt"]),
            LLMMessage(
                role="user",
                content="请开始复盘引导。先简要总结我在对话中的表现，然后针对我最大的改进空间提出第一个反思问题。",
            ),
        ]

        full_content = ""
        try:
            async for chunk in self._llm.stream(llm_messages):
                if chunk.content:
                    full_content += chunk.content
                    yield _sse_event("message_delta", {"content": chunk.content})
        except Exception as exc:
            logger.error("Coaching LLM stream failed: %s", exc)
            yield _sse_event("error", {"message": "Coach 回复生成失败"})

        # Persist coach message
        if full_content:
            async with self._uow_factory() as uow:
                coach_msg = CoachingMessage(
                    id=None,
                    session_id=session_id,
                    role="coach",
                    content=full_content,
                )
                saved = await uow.coaching_message_repository.create(coach_msg)
            yield _sse_event(
                "message_complete",
                {
                    "message_id": saved.id,
                    "role": "coach",
                    "content": full_content,
                },
            )

        yield _sse_event("done", {})

    async def prepare_send_message(self, room_id: int, session_id: int, content: str) -> dict:
        """Validate session and save user message.

        Must be awaited BEFORE creating StreamingResponse so that
        BusinessException is raised while the HTTP response hasn't started yet.
        """
        # 1. Validate session
        async with self._uow_factory() as uow:
            session = await uow.coaching_session_repository.get_by_id(session_id)
            if session is None or session.room_id != room_id:
                raise BusinessException(
                    code=BusinessCode.COACHING_SESSION_NOT_FOUND,
                    message=f"Coaching session {session_id} not found",
                    error_type="CoachingSessionNotFound",
                    details={"session_id": session_id},
                )
            if session.status != "active":
                raise BusinessException(
                    code=BusinessCode.COACHING_SESSION_NOT_FOUND,
                    message="Coaching session is no longer active",
                    error_type="CoachingSessionCompleted",
                    details={"session_id": session_id, "status": session.status},
                )

            # 2. Save user message
            user_msg = CoachingMessage(
                id=None,
                session_id=session_id,
                role="user",
                content=content,
            )
            await uow.coaching_message_repository.create(user_msg)

        # 3. Load session history + report for context
        async with self._uow_factory(readonly=True) as uow:
            messages = await uow.coaching_message_repository.list_by_session_id(session_id)
            report = await uow.analysis_report_repository.get_by_id(session.report_id)

            history_entities = await uow.stakeholder_message_repository.list_by_room_id(
                session.room_id, limit=200
            )

        history = [
            {
                "sender_type": m.sender_type,
                "sender_id": m.sender_id,
                "content": m.content,
                "emotion_score": m.emotion_score,
                "emotion_label": m.emotion_label,
            }
            for m in history_entities
        ]
        non_system = [h for h in history if h["sender_type"] != "system"]
        conversation_text = _build_conversation_text(non_system[-30:], self._persona_loader)

        # 4. Build LLM messages
        org_ctx = await self._build_room_org_context(session.room_id)
        system_prompt = _build_coaching_system_prompt(
            report_summary=report.summary if report else "",
            report_content=report.content if report else {},
            conversation_text=conversation_text,
            org_context=org_ctx,
        )

        llm_messages = [LLMMessage(role="system", content=system_prompt)]
        for msg in messages:
            role = "assistant" if msg.role == "coach" else "user"
            llm_messages.append(LLMMessage(role=role, content=msg.content))

        return {"session_id": session_id, "llm_messages": llm_messages}

    async def stream_reply(self, ctx: dict) -> AsyncIterator[str]:
        """Stream Coach reply (call after prepare_send_message).

        Yields SSE events: message_delta* → message_complete → done.
        """
        session_id = ctx["session_id"]
        llm_messages = ctx["llm_messages"]

        full_content = ""
        try:
            async for chunk in self._llm.stream(llm_messages):
                if chunk.content:
                    full_content += chunk.content
                    yield _sse_event("message_delta", {"content": chunk.content})
        except Exception as exc:
            logger.error("Coaching LLM stream failed: %s", exc)
            yield _sse_event("error", {"message": "Coach 回复生成失败"})

        # Persist coach reply
        if full_content:
            async with self._uow_factory() as uow:
                coach_msg = CoachingMessage(
                    id=None,
                    session_id=session_id,
                    role="coach",
                    content=full_content,
                )
                saved = await uow.coaching_message_repository.create(coach_msg)
            yield _sse_event(
                "message_complete",
                {
                    "message_id": saved.id,
                    "role": "coach",
                    "content": full_content,
                },
            )

        yield _sse_event("done", {})

    async def get_session(self, session_id: int) -> Optional[CoachingSessionDTO]:
        """Get a coaching session with full message history."""
        async with self._uow_factory(readonly=True) as uow:
            session = await uow.coaching_session_repository.get_by_id(session_id)
            if session is None:
                return None
            messages = await uow.coaching_message_repository.list_by_session_id(session_id)

        return CoachingSessionDTO(
            id=session.id,
            room_id=session.room_id,
            report_id=session.report_id,
            status=session.status,
            messages=[
                CoachingMessageDTO(
                    id=m.id,
                    session_id=m.session_id,
                    role=m.role,
                    content=m.content,
                    created_at=m.created_at,
                )
                for m in messages
            ],
            created_at=session.created_at,
            completed_at=session.completed_at,
        )

    async def list_sessions(
        self, room_id: int, *, skip: int = 0, limit: int = 50
    ) -> list[CoachingSessionSummaryDTO]:
        """List coaching sessions for a room."""
        async with self._uow_factory(readonly=True) as uow:
            sessions = await uow.coaching_session_repository.list_by_room_id(
                room_id, skip=skip, limit=limit
            )

        return [
            CoachingSessionSummaryDTO(
                id=s.id,
                room_id=s.room_id,
                report_id=s.report_id,
                status=s.status,
                created_at=s.created_at,
            )
            for s in sessions
        ]

    # ------------------------------------------------------------------
    # Live coaching (stateless, no DB writes)
    # ------------------------------------------------------------------

    async def prepare_live_advice(self, room_id: int) -> dict:
        """Build context for a live coaching stream. No DB writes."""
        async with self._uow_factory(readonly=True) as uow:
            room = await uow.chat_room_repository.get_by_id(room_id)
            if room is None:
                raise BusinessException(
                    code=BusinessCode.CHATROOM_NOT_FOUND,
                    message=f"Chat room {room_id} not found",
                    error_type="ChatRoomNotFound",
                    details={"room_id": room_id},
                )
            history_entities = await uow.stakeholder_message_repository.list_by_room_id(
                room_id, limit=200
            )

        history = [
            {
                "sender_type": m.sender_type,
                "sender_id": m.sender_id,
                "content": m.content,
                "emotion_score": m.emotion_score,
                "emotion_label": m.emotion_label,
            }
            for m in history_entities
        ]
        non_system = [h for h in history if h["sender_type"] != "system"]
        if not non_system:
            raise BusinessException(
                code=BusinessCode.ANALYSIS_NO_MESSAGES,
                message="No messages to coach on",
                error_type="NoMessages",
                details={"room_id": room_id},
            )

        conversation_text, _ = _build_conversation_text(non_system[-30:], self._persona_loader)
        org_ctx = await self._build_room_org_context(room_id)
        system_prompt = _build_live_coaching_system_prompt(conversation_text, org_ctx)

        return {"room_id": room_id, "system_prompt": system_prompt}

    async def stream_live_advice(
        self, ctx: dict, coaching_history: list[dict] | None = None
    ) -> AsyncIterator[str]:
        """Stream live coaching advice via SSE. Stateless — no DB writes.

        Args:
            ctx: Result of ``prepare_live_advice``.
            coaching_history: Previous coaching exchanges as
                ``[{"role": "assistant"|"user", "content": "..."}]``.
                Omit or pass empty list for the opening advice.
        """
        llm_messages = [LLMMessage(role="system", content=ctx["system_prompt"])]

        if coaching_history:
            for msg in coaching_history:
                llm_messages.append(LLMMessage(role=msg["role"], content=msg["content"]))
        else:
            llm_messages.append(
                LLMMessage(
                    role="user",
                    content="我在对话中卡住了，请分析对方最后的发言并给我建议。",
                )
            )

        full_content = ""
        try:
            async for chunk in self._llm.stream(llm_messages):
                if chunk.content:
                    full_content += chunk.content
                    yield _sse_event("message_delta", {"content": chunk.content})
        except Exception as exc:
            logger.error("Live coaching LLM stream failed: %s", exc)
            yield _sse_event("error", {"message": "实时教练回复生成失败"})

        if full_content:
            yield _sse_event("message_complete", {"role": "assistant", "content": full_content})

        yield _sse_event("done", {})
