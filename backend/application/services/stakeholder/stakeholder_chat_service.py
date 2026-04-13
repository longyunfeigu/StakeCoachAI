# input: AbstractUnitOfWork, LLMPort, PersonaLoader, Dispatcher, CompressionService, prompt_builder, RoomEventBus
# output: StakeholderChatService 私聊 + 群聊消息发送与 AI 流式回复编排 + SSE 事件推送（含 streaming_delta）+ 后台历史压缩, _extract_mentions() @提及解析 + Story 2.8 v1/v2 prompt 分流
# owner: wanhua.gu
# pos: 应用层服务 - 利益相关者消息用例编排（私聊 + 群聊多轮调度 + 三区压缩上下文）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Application service for stakeholder chat messaging with SSE events.

Handles both private (1:1) and group chat orchestration.
Group chat uses the Dispatcher to decide which personas reply and in what order.

Architecture: User message is saved and committed immediately. AI reply generation
runs as a background task using streaming LLM output, with each reply committed
in its own UoW transaction. Incremental text is pushed to the frontend via
``streaming_delta`` SSE events for real-time display.
"""

from __future__ import annotations

import asyncio
import logging
import json
import re
import uuid
from typing import Callable

from application.ports.llm import LLMMessage
from application.services.stakeholder.dto import MessageDTO
from application.services.stakeholder.prompt_builder import (
    build_compressed_group_llm_messages,
    build_compressed_group_llm_messages_v2,
    build_compressed_llm_messages,
    build_compressed_llm_messages_v2,
    build_org_context,
)
from core.config import settings
from application.services.stakeholder.sse import room_event_bus
from domain.common.exceptions import BusinessException
from domain.common.unit_of_work import AbstractUnitOfWork
from domain.stakeholder.entity import ChatRoom, Message
from shared.codes import BusinessCode

logger = logging.getLogger(__name__)


def _extract_mentions(content: str, persona_loader) -> list[str]:
    """Extract @mentioned persona IDs from message content.

    Matches @name or @id against known personas. Returns list of persona IDs.
    Uses PersonaLoader's cached name→id map to avoid repeated disk scans.
    """
    raw_mentions = re.findall(r"@([\w\u4e00-\u9fff]{1,50})", content)
    if not raw_mentions:
        return []

    name_to_id = persona_loader.get_name_to_id_map()

    mentioned_ids: list[str] = []
    for mention in raw_mentions:
        pid = name_to_id.get(mention)
        if pid and pid not in mentioned_ids:
            mentioned_ids.append(pid)
    return mentioned_ids


_EMOTION_RE = re.compile(r"\s*<!--emotion:\s*(\{.*?\})\s*-->\s*$", re.DOTALL)


def _extract_emotion(content: str) -> tuple[str, int | None, str | None]:
    """Extract emotion tag from the end of LLM reply content.

    Returns:
        (cleaned_content, score, label) — score/label are None if not found.
    """
    m = _EMOTION_RE.search(content)
    if not m:
        return content, None, None
    try:
        data = json.loads(m.group(1))
        score = int(data.get("score", 0))
        score = max(-5, min(5, score))
        label = str(data.get("label", ""))[:20] or None
    except (json.JSONDecodeError, ValueError, TypeError):
        return content[: m.start()].rstrip(), None, None
    return content[: m.start()].rstrip(), score, label


class StakeholderChatService:
    """Orchestrates sending user messages and generating persona replies."""

    def __init__(
        self,
        uow_factory: Callable[..., AbstractUnitOfWork],
        persona_loader,
        llm,
        dispatcher=None,
        max_group_rounds: int = 20,
        compression_service=None,
        tts=None,
    ) -> None:
        self._uow_factory = uow_factory
        self._persona_loader = persona_loader
        self._llm = llm
        self._dispatcher = dispatcher
        self._max_group_rounds = max_group_rounds
        self._compression = compression_service
        self._tts = tts  # Optional TTSPort for voice synthesis

    async def send_message(self, room_id: int, content: str) -> tuple[MessageDTO, ChatRoom]:
        """Save user message (committed immediately). Returns (dto, room) for background reply generation."""

        async with self._uow_factory() as uow:
            room = await uow.chat_room_repository.get_by_id(room_id)
            if room is None:
                raise BusinessException(
                    code=BusinessCode.CHATROOM_NOT_FOUND,
                    message=f"Chat room {room_id} not found",
                    error_type="ChatRoomNotFound",
                    details={"room_id": room_id},
                )

            user_msg = Message(
                id=None,
                room_id=room_id,
                sender_type="user",
                sender_id="user",
                content=content,
            )
            saved_user_msg = await uow.stakeholder_message_repository.create(user_msg)
            await uow.chat_room_repository.update_last_message_at(room_id, saved_user_msg.timestamp)
            user_dto = MessageDTO.model_validate(saved_user_msg)

            # Publish user message event via SSE
            await room_event_bus.publish(room_id, "message", user_dto.model_dump(mode="json"))

        return user_dto, room

    async def _load_org_context(self, persona_id: str) -> str | None:
        """Load organization context for a persona, if it belongs to one."""
        persona = self._persona_loader.get_persona(persona_id)
        org_id = getattr(persona, "organization_id", None) if persona else None
        if not org_id:
            return None

        async with self._uow_factory(readonly=True) as uow:
            org = await uow.organization_repository.get_by_id(org_id)
            if not org:
                return None

            team = None
            team_id = getattr(persona, "team_id", None)
            if team_id:
                team = await uow.team_repository.get_by_id(team_id)

            rels = await uow.persona_relationship_repository.list_by_organization(org_id)

        # Filter relationships involving this persona
        my_rels: list[dict] = []
        for r in rels:
            if r.from_persona_id == persona_id:
                target = self._persona_loader.get_persona(r.to_persona_id)
                my_rels.append(
                    {
                        "persona_name": target.name if target else r.to_persona_id,
                        "relationship_type": r.relationship_type,
                        "description": r.description,
                    }
                )
            elif r.to_persona_id == persona_id:
                source = self._persona_loader.get_persona(r.from_persona_id)
                # Invert relationship type for the reverse direction
                inv = {
                    "superior": "subordinate",
                    "subordinate": "superior",
                    "peer": "peer",
                    "cross_department": "cross_department",
                }
                my_rels.append(
                    {
                        "persona_name": source.name if source else r.from_persona_id,
                        "relationship_type": inv.get(r.relationship_type, r.relationship_type),
                        "description": r.description,
                    }
                )

        return (
            build_org_context(
                org_name=org.name,
                org_context_prompt=org.context_prompt,
                team_name=team.name if team else "",
                team_description=team.description if team else "",
                relationships=my_rels if my_rels else None,
            )
            or None
        )

    async def _load_scenario_context(self, room: ChatRoom) -> str | None:
        """Load scenario context_prompt for a room, if it has a scenario_id."""
        if not room.scenario_id:
            return None
        async with self._uow_factory(readonly=True) as uow:
            scenario = await uow.scenario_repository.get_by_id(room.scenario_id)
            return scenario.context_prompt if scenario else None

    async def generate_replies(self, room_id: int, room: ChatRoom) -> None:
        """Background task: route to private or group chat reply generation."""
        try:
            scenario_context = await self._load_scenario_context(room)

            if room.type == "group" and self._dispatcher:
                await self._orchestrate_group_chat(room, scenario_context=scenario_context)
            else:
                persona_id = room.persona_ids[0] if room.persona_ids else None
                if persona_id:
                    await self._generate_reply(
                        room_id,
                        persona_id,
                        scenario_context=scenario_context,
                    )
        except asyncio.CancelledError:
            logger.warning("Reply generation cancelled for room %d", room_id)
        except Exception:
            logger.exception("Background reply generation failed for room %d", room_id)

    async def _generate_reply(
        self,
        room_id: int,
        persona_id: str,
        *,
        group_mode: bool = False,
        is_mentioned: bool = False,
        scenario_context: str | None = None,
        cached_history: list[dict[str, str]] | None = None,
    ) -> tuple[bool, dict[str, str] | None]:
        """Generate and save a persona reply using LLM, emitting SSE events.

        Each reply runs in its own UoW transaction so it's committed independently.

        Args:
            cached_history: Pre-loaded history dicts to avoid redundant DB queries
                during group chat orchestration. When provided, skips DB history load.

        Returns:
            (success, saved_msg_dict) — saved_msg_dict can be appended to cached_history
            by the caller to keep the cache up-to-date without another DB round-trip.
        """
        persona = self._persona_loader.get_persona(persona_id)
        if persona is None:
            logger.warning("Persona %s not found, skipping reply", persona_id)
            return False, None

        # Load org context (non-blocking, returns None if persona has no org)
        org_ctx = await self._load_org_context(persona_id)

        # Emit typing start
        await room_event_bus.publish(
            room_id, "typing", {"persona_id": persona_id, "status": "start"}
        )

        try:
            async with self._uow_factory() as uow:
                # Use cached history if provided (group chat), otherwise load from DB
                if cached_history is not None:
                    history = cached_history
                else:
                    history_entities = await uow.stakeholder_message_repository.list_by_room_id(
                        room_id, limit=200
                    )
                    history = [
                        {
                            "sender_type": m.sender_type,
                            "sender_id": m.sender_id,
                            "content": m.content,
                        }
                        for m in history_entities
                    ]

                # Load room for compression state
                room = await uow.chat_room_repository.get_by_id(room_id)

                # Build prompt (group vs private) with three-zone compression
                window_size = settings.stakeholder.context_window_size
                summary = room.context_summary if room else None

                # Story 2.8: branch on schema_version. v2 personas use the
                # 5-layer structured builder; v1 (markdown) keep the legacy path.
                is_v2 = getattr(persona, "schema_version", 1) >= 2
                if group_mode:
                    if is_v2:
                        system_prompt, llm_messages = build_compressed_group_llm_messages_v2(
                            persona=persona,
                            persona_id=persona_id,
                            history=history,
                            context_summary=summary,
                            context_window_size=window_size,
                            is_mentioned=is_mentioned,
                            scenario_context=scenario_context,
                            org_context=org_ctx,
                        )
                    else:
                        system_prompt, llm_messages = build_compressed_group_llm_messages(
                            persona_full_content=persona.full_content,
                            persona_name=persona.name,
                            persona_id=persona_id,
                            history=history,
                            context_summary=summary,
                            context_window_size=window_size,
                            is_mentioned=is_mentioned,
                            scenario_context=scenario_context,
                            org_context=org_ctx,
                        )
                else:
                    if is_v2:
                        system_prompt, llm_messages = build_compressed_llm_messages_v2(
                            persona=persona,
                            history=history,
                            context_summary=summary,
                            context_window_size=window_size,
                            scenario_context=scenario_context,
                            org_context=org_ctx,
                        )
                    else:
                        system_prompt, llm_messages = build_compressed_llm_messages(
                            persona_full_content=persona.full_content,
                            persona_name=persona.name,
                            history=history,
                            context_summary=summary,
                            context_window_size=window_size,
                            scenario_context=scenario_context,
                            org_context=org_ctx,
                        )

                # Stream LLM response, pushing incremental deltas via SSE
                reply_content = None
                try:
                    all_messages = [LLMMessage(role="system", content=system_prompt)]
                    all_messages.extend(
                        LLMMessage(role=m["role"], content=m["content"]) for m in llm_messages
                    )
                    chunks: list[str] = []

                    # Set up TTS pipeline if voice is enabled for this persona
                    tts_enabled = self._tts is not None and persona.voice_id is not None
                    sentence_buf = None
                    tts_tasks: list[asyncio.Task] = []
                    audio_index = 0
                    tts_reply_id = ""
                    if tts_enabled:
                        from application.services.stakeholder.sentence_buffer import SentenceBuffer

                        sentence_buf = SentenceBuffer()
                        tts_reply_id = uuid.uuid4().hex[:12]

                    async for chunk in self._llm.stream(all_messages):
                        if chunk.content:
                            chunks.append(chunk.content)
                            await room_event_bus.publish(
                                room_id,
                                "streaming_delta",
                                {"persona_id": persona_id, "delta": chunk.content},
                            )

                            # Feed to SentenceBuffer for TTS
                            if sentence_buf is not None:
                                sentence = sentence_buf.feed(chunk.content)
                                if sentence:
                                    task = asyncio.create_task(
                                        self._synthesize_and_push(
                                            room_id,
                                            persona_id,
                                            persona,
                                            sentence,
                                            audio_index,
                                            tts_reply_id,
                                        )
                                    )
                                    tts_tasks.append(task)
                                    audio_index += 1

                    # Flush remaining sentence for TTS
                    if sentence_buf is not None:
                        remaining = sentence_buf.flush()
                        if remaining:
                            task = asyncio.create_task(
                                self._synthesize_and_push(
                                    room_id,
                                    persona_id,
                                    persona,
                                    remaining,
                                    audio_index,
                                    tts_reply_id,
                                )
                            )
                            tts_tasks.append(task)

                    # Wait for all TTS tasks to finish before continuing
                    if tts_tasks:
                        await asyncio.gather(*tts_tasks, return_exceptions=True)

                    reply_content = "".join(chunks) if chunks else None
                except Exception as exc:
                    logger.error(
                        "LLM stream failed for room %d, persona %s: %s: %s",
                        room_id,
                        persona_id,
                        type(exc).__name__,
                        exc,
                    )

                if reply_content:
                    cleaned, emotion_score, emotion_label = _extract_emotion(reply_content)
                    reply_msg = Message(
                        id=None,
                        room_id=room_id,
                        sender_type="persona",
                        sender_id=persona_id,
                        content=cleaned,
                        emotion_score=emotion_score,
                        emotion_label=emotion_label,
                    )
                else:
                    reply_msg = Message(
                        id=None,
                        room_id=room_id,
                        sender_type="system",
                        sender_id="system",
                        content="AI 回复生成失败，请稍后重试。",
                    )

                saved_reply = await uow.stakeholder_message_repository.create(reply_msg)
                await uow.chat_room_repository.update_last_message_at(
                    room_id, saved_reply.timestamp
                )

                # Emit final message first, then typing stop (avoids flash)
                reply_dto = MessageDTO.model_validate(saved_reply)
                await room_event_bus.publish(room_id, "message", reply_dto.model_dump(mode="json"))
                await room_event_bus.publish(
                    room_id, "typing", {"persona_id": persona_id, "status": "stop"}
                )

            # Return dict for caller to append to cached_history
            saved_msg_dict = {
                "sender_type": saved_reply.sender_type,
                "sender_id": saved_reply.sender_id,
                "content": saved_reply.content,
            }

            # Trigger background compression (fire-and-forget, non-blocking).
            # In group_mode, compression is triggered once at the end of
            # _orchestrate_group_chat instead of after each persona reply.
            if self._compression and reply_content and not group_mode:
                asyncio.create_task(
                    self._safe_compress(room_id),
                    name=f"compress-room-{room_id}",
                )

            return reply_content is not None, saved_msg_dict

        except Exception:
            # Ensure typing indicator is cleared even on unexpected errors
            await room_event_bus.publish(
                room_id, "typing", {"persona_id": persona_id, "status": "stop"}
            )
            logger.exception(
                "Unexpected error in _generate_reply for room %d, persona %s",
                room_id,
                persona_id,
            )
            return False, None

    async def _synthesize_and_push(
        self,
        room_id: int,
        persona_id: str,
        persona,
        text: str,
        index: int,
        reply_id: str = "",
    ) -> None:
        """Synthesize a sentence via TTS and push audio chunks via SSE.

        Runs as a concurrent task alongside LLM generation so that
        TTS for sentence N happens while LLM generates sentence N+1.
        """
        import base64

        from application.ports.tts import TTSConfig

        # Strip emotion tags — they arrive as trailing <!--emotion:{...}-->
        # and must not be spoken aloud.
        text = _EMOTION_RE.sub("", text).strip()
        if not text:
            return

        try:
            config = TTSConfig(
                voice_id=persona.voice_id,
                speed=persona.voice_speed,
            )
            # Accumulate all streaming chunks into a complete mp3 per sentence.
            # Individual chunks are mp3 fragments that browsers can't decode alone.
            audio_parts: list[bytes] = []
            async for audio_bytes in self._tts.synthesize_stream(text, config):
                audio_parts.append(audio_bytes)

            if audio_parts:
                complete_audio = b"".join(audio_parts)
                await room_event_bus.publish(
                    room_id,
                    "audio_chunk",
                    {
                        "persona_id": persona_id,
                        "data": base64.b64encode(complete_audio).decode("ascii"),
                        "sentence_index": index,
                        "reply_id": reply_id,
                        "sentence_final": True,
                    },
                )
        except Exception:
            logger.exception(
                "TTS synthesis failed for room %d, persona %s, sentence %d",
                room_id,
                persona_id,
                index,
            )

    async def _safe_compress(self, room_id: int) -> None:
        """Run compression in background, swallowing errors."""
        try:
            await self._compression.maybe_compress(room_id)
        except Exception:
            logger.exception("Background compression failed for room %d", room_id)

    async def _orchestrate_group_chat(
        self, room: ChatRoom, *, scenario_context: str | None = None
    ) -> None:
        """Orchestrate multi-round group chat using the Dispatcher.

        Flow: decide_responders → [generate_reply → check_followup → loop]
              → round_end. Stops when no followups or max_group_rounds reached.

        History is loaded ONCE from DB at the start, then updated incrementally
        as each persona reply is generated — avoiding O(n²) redundant queries.
        """
        room_id = room.id

        # Load history ONCE for the entire orchestration round
        async with self._uow_factory(readonly=True) as uow:
            history_entities = await uow.stakeholder_message_repository.list_by_room_id(
                room_id, limit=200
            )
            history = [
                {"sender_type": m.sender_type, "sender_id": m.sender_id, "content": m.content}
                for m in history_entities
            ]

        # Get user's latest message for dispatcher
        user_msgs = [h for h in history if h["sender_type"] == "user"]
        user_message = user_msgs[-1]["content"] if user_msgs else ""

        # Extract @mentions from user message (only those in this room)
        room_pid_set = set(room.persona_ids)
        mentioned_ids = [
            mid
            for mid in _extract_mentions(user_message, self._persona_loader)
            if mid in room_pid_set
        ]

        # Decide first batch of responders
        first_batch = await self._dispatcher.decide_responders(
            user_message=user_message,
            history=history,
            persona_ids=room.persona_ids,
            mentioned_ids=mentioned_ids,
        )

        # Collect dispatcher decisions for transparency
        dispatch_log: list[dict] = []

        if not first_batch:
            await room_event_bus.publish(
                room_id,
                "round_end",
                {
                    "dispatch_log": [],
                    "total_replies": 0,
                    "max_rounds_reached": False,
                },
            )
            return

        # Record initial batch decision
        dispatch_log.append(
            {
                "phase": "initial",
                "responders": [
                    {"persona_id": r["persona_id"], "reason": r.get("reason", "")}
                    for r in first_batch
                ],
            }
        )

        # Build response queue: start with first batch
        response_queue = list(first_batch)
        already_responded: set[str] = set()
        # Track all queued persona IDs to prevent duplicates
        queued_ids: set[str] = {r["persona_id"] for r in first_batch}
        round_count = 0
        max_rounds_reached = False

        while response_queue:
            responder = response_queue.pop(0)
            persona_id = responder["persona_id"]

            # Check max rounds
            if round_count >= self._max_group_rounds:
                max_rounds_reached = True
                break

            # Generate reply with cached history (no redundant DB load)
            success, saved_msg_dict = await self._generate_reply(
                room_id,
                persona_id,
                group_mode=True,
                is_mentioned=(persona_id in mentioned_ids),
                scenario_context=scenario_context,
                cached_history=history,
            )

            round_count += 1
            already_responded.add(persona_id)

            if not success:
                break

            # Incrementally update cached history with the new reply
            if saved_msg_dict:
                history.append(saved_msg_dict)
                # Keep history within the 200-message window
                if len(history) > 200:
                    history = history[-200:]

            last_reply = history[-1]

            # Check for followup responders (uses same cached history)
            followups = await self._dispatcher.check_followup(
                last_reply=last_reply,
                history=history,
                persona_ids=room.persona_ids,
                already_responded=already_responded,
            )

            # Record followup decisions and add to queue
            new_followups = []
            for f in followups:
                pid = f["persona_id"]
                if pid not in already_responded and pid not in queued_ids:
                    response_queue.append(f)
                    queued_ids.add(pid)
                    new_followups.append(f)

            if new_followups:
                dispatch_log.append(
                    {
                        "phase": "followup",
                        "trigger_persona_id": persona_id,
                        "responders": [
                            {"persona_id": f["persona_id"], "reason": f.get("reason", "")}
                            for f in new_followups
                        ],
                    }
                )

        # If max rounds reached, insert system message
        if max_rounds_reached:
            async with self._uow_factory() as uow:
                sys_msg = Message(
                    id=None,
                    room_id=room_id,
                    sender_type="system",
                    sender_id="system",
                    content=f"本轮对话已达到最大轮次上限（{self._max_group_rounds}），请发送新消息继续讨论。",
                )
                saved_sys = await uow.stakeholder_message_repository.create(sys_msg)
                await uow.chat_room_repository.update_last_message_at(room_id, saved_sys.timestamp)
                sys_dto = MessageDTO.model_validate(saved_sys)
                await room_event_bus.publish(room_id, "message", sys_dto.model_dump(mode="json"))

        # Trigger background compression once after all group replies
        if self._compression and round_count > 0:
            asyncio.create_task(
                self._safe_compress(room_id),
                name=f"compress-room-{room_id}",
            )

        # Always emit round_end with dispatch transparency data
        await room_event_bus.publish(
            room_id,
            "round_end",
            {
                "dispatch_log": dispatch_log,
                "total_replies": round_count,
                "max_rounds_reached": max_rounds_reached,
            },
        )
