# input: PersonaLoader, PersonaEditorService, ChatRoomApplicationService, StakeholderChatService, ScenarioApplicationService, AnalysisService, GrowthService, PersonaBuilderService (via dependencies)
# output: stakeholder API 路由 (personas CRUD + rooms + messages + scenarios CRUD + analysis reports + growth dashboard + Story 2.5 SSE persona/build + Story 2.7 v2 GET/PATCH)
# owner: wanhua.gu
# pos: 表示层 - 利益相关者聊天 API 路由（角色 + 聊天室 + 消息 + 场景 + persona 构建 SSE）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Stakeholder chat API routes."""

from __future__ import annotations

import asyncio
import time
from datetime import timezone
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from starlette.responses import Response, StreamingResponse

from api.dependencies import (
    get_analysis_service,
    get_analysis_reader_service,
    get_battle_prep_service,
    get_chatroom_service,
    get_coaching_service,
    get_growth_service,
    get_organization_service,
    get_persona_builder_service,
    get_persona_editor_service,
    get_persona_loader,
    get_persona_loader_with_v2,
    get_persona_v2_service,
    get_scenario_service,
    get_stakeholder_chat_service,
)
from application.services.stakeholder.chatroom_service import ChatRoomApplicationService
from application.services.stakeholder.dto import (
    BattlePrepGenerateDTO,
    CreateChatRoomDTO,
    CreateOrganizationDTO,
    CreatePersonaDTO,
    CreateRelationshipDTO,
    CreateScenarioDTO,
    CreateTeamDTO,
    PersonaBuildRequestDTO,
    PersonaPatchV2DTO,
    SendMessageDTO,
    StartBattleDTO,
    UpdateOrganizationDTO,
    UpdatePersonaDTO,
    UpdateRelationshipDTO,
    UpdateScenarioDTO,
    UpdateTeamDTO,
)
from application.services.stakeholder.organization_service import OrganizationService
from application.services.stakeholder.persona_editor_service import PersonaEditorService
from application.services.stakeholder.persona_loader import PersonaLoader
from application.services.stakeholder.scenario_service import ScenarioApplicationService
from application.services.stakeholder.sse import format_sse, room_event_bus
from application.services.stakeholder.analysis_service import AnalysisService, AnalysisReaderService
from application.services.stakeholder.coaching_service import CoachingService
from application.services.stakeholder.stakeholder_chat_service import StakeholderChatService
from core.response import success_response

router = APIRouter(prefix="/stakeholder", tags=["Stakeholder Chat"])


# ---------------------------------------------------------------------------
# Persona endpoints (existing)
# ---------------------------------------------------------------------------


@router.get("/personas", summary="获取所有角色列表")
async def list_personas(
    loader: PersonaLoader = Depends(get_persona_loader_with_v2),
):
    personas = loader.list_personas()
    return success_response(
        data=[
            {
                "id": p.id,
                "name": p.name,
                "role": p.role,
                "avatar_color": p.avatar_color,
                "organization_id": p.organization_id,
                "team_id": p.team_id,
                "parse_status": p.parse_status,
            }
            for p in personas
        ]
    )


@router.get("/personas/{persona_id}", summary="获取角色详情")
async def get_persona(
    persona_id: str,
    loader: PersonaLoader = Depends(get_persona_loader_with_v2),
):
    persona = loader.get_persona(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    body = loader._strip_frontmatter(persona.full_content)
    return success_response(
        data={
            "id": persona.id,
            "name": persona.name,
            "role": persona.role,
            "avatar_color": persona.avatar_color,
            "organization_id": persona.organization_id,
            "team_id": persona.team_id,
            "profile_summary": persona.profile_summary,
            "content": body,
            "parse_status": persona.parse_status,
        }
    )


# ---------------------------------------------------------------------------
# Persona editor endpoints (Feature 5)
# ---------------------------------------------------------------------------


@router.post("/personas", summary="创建角色", status_code=201)
async def create_persona(
    body: CreatePersonaDTO,
    editor: PersonaEditorService = Depends(get_persona_editor_service),
):
    try:
        editor.create_persona(body)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return success_response(data={"id": body.id})


@router.put("/personas/{persona_id}", summary="更新角色")
async def update_persona(
    persona_id: str,
    body: UpdatePersonaDTO,
    editor: PersonaEditorService = Depends(get_persona_editor_service),
):
    try:
        editor.update_persona(persona_id, body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return success_response(data={"id": persona_id})


@router.delete("/personas/{persona_id}", summary="删除角色")
async def delete_persona_endpoint(
    persona_id: str,
    editor: PersonaEditorService = Depends(get_persona_editor_service),
):
    try:
        editor.delete_persona(persona_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return success_response(data={"id": persona_id})


# ---------------------------------------------------------------------------
# Persona V2 endpoints (Story 2.7 — 5-layer editor)
# ---------------------------------------------------------------------------


@router.get("/personas/{persona_id}/v2", summary="获取 v2 5-layer 画像 + 证据 (Story 2.7)")
async def get_persona_v2_endpoint(
    persona_id: str,
    svc=Depends(get_persona_v2_service),
):
    from application.services.stakeholder.persona_v2_service import (
        PersonaNotFoundError,
    )

    try:
        dto = await svc.get_v2(persona_id)
    except PersonaNotFoundError:
        raise HTTPException(status_code=404, detail="Persona not found")
    return success_response(data=dto.model_dump(mode="json"))


@router.patch("/personas/{persona_id}/v2", summary="部分更新 v2 5-layer 画像 (Story 2.7)")
async def patch_persona_v2_endpoint(
    persona_id: str,
    body: PersonaPatchV2DTO,
    svc=Depends(get_persona_v2_service),
):
    from application.services.stakeholder.persona_v2_service import (
        PersonaNotFoundError,
        PersonaNotV2Error,
    )

    try:
        dto = await svc.patch_v2(persona_id, body)
    except PersonaNotFoundError:
        raise HTTPException(status_code=404, detail="Persona not found")
    except PersonaNotV2Error:
        raise HTTPException(
            status_code=409,
            detail={"code": "NOT_V2", "message": "Persona is legacy v1 — migrate first"},
        )
    return success_response(data=dto.model_dump(mode="json"))


@router.post(
    "/personas/{persona_id}/start-battle",
    summary="从已有 persona 开演练 (Story 2.8)",
    status_code=201,
)
async def start_battle_from_persona(
    persona_id: str,
    svc=Depends(get_battle_prep_service),
):
    try:
        room = await svc.create_room_from_persona(persona_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Persona not found")
    return success_response(data=room.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# ChatRoom endpoints (Story 2.1)
# ---------------------------------------------------------------------------


@router.post("/rooms", summary="创建聊天室", status_code=201)
async def create_room(
    body: CreateChatRoomDTO,
    svc: ChatRoomApplicationService = Depends(get_chatroom_service),
):
    room = await svc.create_room(body)
    return success_response(data=room.model_dump())


@router.get("/rooms", summary="获取聊天室列表")
async def list_rooms(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    svc: ChatRoomApplicationService = Depends(get_chatroom_service),
):
    rooms = await svc.list_rooms(skip=skip, limit=limit)
    return success_response(data=[r.model_dump() for r in rooms])


@router.delete("/rooms/{room_id}", summary="删除聊天室")
async def delete_room(
    room_id: int,
    svc: ChatRoomApplicationService = Depends(get_chatroom_service),
):
    deleted = await svc.delete_room(room_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Room not found")
    return success_response(data=None)


@router.get("/rooms/{room_id}", summary="获取聊天室详情及消息历史")
async def get_room_detail(
    room_id: int,
    limit: int = Query(50, ge=1, le=200),
    svc: ChatRoomApplicationService = Depends(get_chatroom_service),
):
    detail = await svc.get_room_detail(room_id, message_limit=limit)
    return success_response(data=detail.model_dump())


# ---------------------------------------------------------------------------
# Export endpoint
# ---------------------------------------------------------------------------


@router.get("/rooms/{room_id}/export", summary="导出聊天记录为 Markdown")
async def export_room(
    room_id: int,
    svc: ChatRoomApplicationService = Depends(get_chatroom_service),
    loader: PersonaLoader = Depends(get_persona_loader),
):
    detail = await svc.get_room_detail(room_id, message_limit=9999)
    room = detail.room
    msgs = detail.messages

    # Build markdown
    lines: list[str] = []
    _type_labels = {"group": "群聊", "private": "私聊", "battle_prep": "备战"}
    type_label = _type_labels.get(room.type, room.type)
    persona_names = []
    for pid in room.persona_ids:
        p = loader.get_persona(pid)
        persona_names.append(p.name if p else pid)
    lines.append(f"# {room.name}")
    lines.append(f"{type_label} | 参与者: {', '.join(persona_names)}\n")
    lines.append("---\n")

    for msg in msgs:
        ts = ""
        if msg.timestamp:
            t = msg.timestamp
            if t.tzinfo is not None:
                t = t.astimezone(timezone.utc).replace(tzinfo=None)
            ts = t.strftime("%Y-%m-%d %H:%M")

        if msg.sender_type == "user":
            sender = "我"
        elif msg.sender_type == "persona":
            p = loader.get_persona(msg.sender_id)
            sender = p.name if p else msg.sender_id
        else:
            sender = "系统"

        lines.append(f"**{sender}** ({ts}):\n")
        lines.append(f"{msg.content}\n")

    content = "\n".join(lines)
    filename = f"{room.name}.md"

    from urllib.parse import quote

    encoded = quote(filename)
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
        },
    )


@router.get("/rooms/{room_id}/export/html", summary="导出聊天记录为 HTML")
async def export_room_html(
    room_id: int,
    svc: ChatRoomApplicationService = Depends(get_chatroom_service),
    loader: PersonaLoader = Depends(get_persona_loader),
):
    import re
    from html import escape
    from urllib.parse import quote

    detail = await svc.get_room_detail(room_id, message_limit=9999)
    room = detail.room
    msgs = detail.messages

    _type_labels = {"group": "群聊", "private": "私聊", "battle_prep": "备战"}
    type_label = _type_labels.get(room.type, room.type)
    persona_names = []
    persona_colors: dict[str, str] = {}
    for pid in room.persona_ids:
        p = loader.get_persona(pid)
        persona_names.append(p.name if p else pid)
        if p:
            persona_colors[pid] = p.avatar_color or "#999"

    mention_re = re.compile(r"(@[\w\u4e00-\u9fff]+)")
    bold_re = re.compile(r"\*\*(.+?)\*\*")

    def _render_inline(text: str, is_user: bool = False) -> str:
        """Escape HTML, then render @mentions and **bold**."""
        html = escape(text)
        # @mentions
        mention_cls = "mention-hl mention-hl-user" if is_user else "mention-hl"
        html = mention_re.sub(lambda m: f'<span class="{mention_cls}">{m.group()}</span>', html)
        # **bold**
        html = bold_re.sub(r"<strong>\1</strong>", html)
        return html

    # Build message HTML
    msg_html_parts: list[str] = []
    for msg in msgs:
        ts = ""
        if msg.timestamp:
            t = msg.timestamp
            if t.tzinfo is not None:
                t = t.astimezone(timezone.utc).replace(tzinfo=None)
            ts = t.strftime("%Y-%m-%d %H:%M")

        is_user = msg.sender_type == "user"
        if is_user:
            sender = "我"
        elif msg.sender_type == "persona":
            p = loader.get_persona(msg.sender_id)
            sender = p.name if p else msg.sender_id
        else:
            sender = "系统"

        content_html = _render_inline(msg.content, is_user=is_user)
        # Convert newlines to <br> for display
        content_html = content_html.replace("\n", "<br>")

        color = persona_colors.get(msg.sender_id, "")

        if msg.sender_type == "system":
            msg_html_parts.append(
                f'<div class="msg msg-system">'
                f'<div class="bubble bubble-system">{content_html}</div>'
                f'<div class="ts">{escape(ts)}</div></div>'
            )
        elif is_user:
            msg_html_parts.append(
                f'<div class="msg msg-user">'
                f'<div class="bubble bubble-user">{content_html}</div>'
                f'<div class="ts ts-right">{escape(ts)}</div></div>'
            )
        else:
            border_style = f' style="border-left:3px solid {escape(color)}"' if color else ""
            name_style = f' style="color:{escape(color)}"' if color else ""
            msg_html_parts.append(
                f'<div class="msg msg-persona">'
                f'<div class="sender"{name_style}>{escape(sender)}</div>'
                f'<div class="bubble bubble-persona"{border_style}>{content_html}</div>'
                f'<div class="ts">{escape(ts)}</div></div>'
            )

    from datetime import datetime as _dt

    messages_block = "\n".join(msg_html_parts)
    detail_export_time = _dt.now().strftime("%Y-%m-%d %H:%M")
    participants = escape(", ".join(persona_names))
    room_name = escape(room.name)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{room_name} - 聊天记录</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;background:#f3f4f6;color:#333;line-height:1.6}}
.container{{max-width:800px;margin:0 auto;background:#fff;min-height:100vh;box-shadow:0 0 20px rgba(0,0,0,.08)}}
.header{{background:#4f46e5;color:#fff;padding:20px 24px}}
.header h1{{font-size:20px;margin-bottom:4px}}
.header .meta{{font-size:13px;opacity:.85}}
.badge{{display:inline-block;background:rgba(255,255,255,.2);padding:2px 8px;border-radius:10px;font-size:12px;margin-left:8px}}
.messages{{padding:16px 24px}}
.msg{{margin-bottom:16px;display:flex;flex-direction:column}}
.msg-user{{align-items:flex-end}}
.msg-persona,.msg-system{{align-items:flex-start}}
.msg-system{{align-items:center}}
.sender{{font-size:13px;font-weight:600;margin-bottom:2px;padding-left:4px}}
.bubble{{padding:10px 14px;border-radius:12px;max-width:70%;font-size:14px;line-height:1.6;word-break:break-word}}
.bubble-user{{background:#4f46e5;color:#fff;border-bottom-right-radius:4px}}
.bubble-persona{{background:#fff;border:1px solid #e5e7eb;border-bottom-left-radius:4px}}
.bubble-system{{background:#fef9c3;color:#854d0e;font-size:13px;border-radius:8px}}
.ts{{font-size:11px;color:#aaa;margin-top:2px;padding:0 4px}}
.ts-right{{text-align:right}}
.mention-hl{{color:#4f46e5;font-weight:600;background:rgba(79,70,229,.1);padding:1px 4px;border-radius:3px}}
.mention-hl-user{{color:#fff;background:rgba(255,255,255,.2)}}
.footer{{text-align:center;padding:20px;color:#aaa;font-size:12px;border-top:1px solid #f0f0f0}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>{room_name}<span class="badge">{escape(type_label)}</span></h1>
<div class="meta">参与者: {participants}</div>
</div>
<div class="messages">
{messages_block}
</div>
<div class="footer">导出时间: {detail_export_time}</div>
</div>
</body>
</html>"""

    filename = f"{room.name}.html"
    encoded = quote(filename)
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
        },
    )


# ---------------------------------------------------------------------------
# Message endpoints (Story 2.2)
# ---------------------------------------------------------------------------


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
            raise HTTPException(
                status_code=422,
                detail="备战对话已达到 12 轮上限，请结束备战生成话术纸条",
            )

    msg, room = await svc.send_message(room_id, body.content)
    background_tasks.add_task(svc.generate_replies, room_id, room)
    return success_response(data=msg.model_dump())


# ---------------------------------------------------------------------------
# SSE Stream endpoint (Story 2.3)
# ---------------------------------------------------------------------------


@router.get("/rooms/{room_id}/stream", summary="SSE 实时推送")
async def stream_room(room_id: int):
    """Subscribe to real-time events for a chat room via Server-Sent Events."""

    async def event_generator():
        queue = room_event_bus.subscribe(room_id)
        try:
            while True:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield format_sse(event, data)
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            room_event_bus.unsubscribe(room_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Voice WebSocket endpoint (Story 2.4)
# ---------------------------------------------------------------------------


@router.websocket("/rooms/{room_id}/voice")
async def voice_ws(
    websocket: WebSocket,
    room_id: int,
    svc: StakeholderChatService = Depends(get_stakeholder_chat_service),
):
    """WebSocket for voice message input.

    Client sends audio chunks while speaking, then a speech_end signal.
    Server transcribes the audio and auto-sends as a text message,
    triggering the normal persona reply flow (including TTS via SSE).

    Protocol:
      Client → Server:
        { "type": "audio_chunk", "data": "<base64 audio>" }
        { "type": "speech_end" }
      Server → Client:
        { "type": "transcription", "text": "...", "is_final": false }
        { "type": "transcription", "text": "...", "is_final": true }
        { "type": "error", "message": "..." }
    """
    await websocket.accept()

    import base64
    import logging

    import httpx

    from infrastructure.external.voice import get_stt_client

    logger = logging.getLogger(__name__)
    stt = get_stt_client()

    async def send_voice_json(payload: dict) -> bool:
        try:
            await websocket.send_json(payload)
            return True
        except WebSocketDisconnect:
            return False
        except Exception as exc:
            logger.debug(
                "voice_websocket_send_failed room_id=%s error=%s",
                room_id,
                exc,
            )
            return False

    if stt is None:
        await send_voice_json({"type": "error", "message": "STT service not configured"})
        await websocket.close(code=1011)
        return

    audio_buffer = bytearray()

    try:
        while True:
            raw = await websocket.receive_json()
            msg_type = raw.get("type")

            if msg_type == "audio_chunk":
                # Accumulate audio data
                audio_b64 = raw.get("data", "")
                if audio_b64:
                    audio_buffer.extend(base64.b64decode(audio_b64))

            elif msg_type == "speech_end":
                if not audio_buffer:
                    if not await send_voice_json(
                        {"type": "error", "message": "No audio data received"}
                    ):
                        break
                    continue

                # Transcribe accumulated audio
                try:
                    audio_format = raw.get("format", "webm")
                    result = await stt.transcribe(
                        bytes(audio_buffer),
                        language="zh",
                        audio_format=audio_format,
                    )
                    text = result.text.strip()

                    if not await send_voice_json(
                        {"type": "transcription", "text": text, "is_final": True}
                    ):
                        break

                    # Auto-send as text message if transcription is not empty
                    if text:
                        msg, room = await svc.send_message(room_id, text)
                        # Generate replies in background (TTS audio will come via SSE)
                        asyncio.create_task(svc.generate_replies(room_id, room))

                except httpx.TimeoutException as exc:
                    logger.warning(
                        "STT transcription timed out for room %d: %s",
                        room_id,
                        exc.__class__.__name__,
                    )
                    if not await send_voice_json(
                        {
                            "type": "error",
                            "message": "语音识别服务连接超时，请检查 STT 网络或稍后重试",
                        }
                    ):
                        break
                except Exception as exc:
                    logger.exception("STT transcription failed for room %d", room_id)
                    if not await send_voice_json(
                        {"type": "error", "message": f"Transcription failed: {exc}"}
                    ):
                        break
                finally:
                    audio_buffer.clear()

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Voice WebSocket error for room %d", room_id)


# ---------------------------------------------------------------------------
# Scenario endpoints (Feature 6)
# ---------------------------------------------------------------------------


@router.post("/scenarios", summary="创建场景模板", status_code=201)
async def create_scenario(
    body: CreateScenarioDTO,
    svc: ScenarioApplicationService = Depends(get_scenario_service),
):
    scenario = await svc.create_scenario(body)
    return success_response(data=scenario.model_dump())


@router.get("/scenarios", summary="获取场景模板列表")
async def list_scenarios(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    svc: ScenarioApplicationService = Depends(get_scenario_service),
):
    scenarios = await svc.list_scenarios(skip=skip, limit=limit)
    return success_response(data=[s.model_dump() for s in scenarios])


@router.get("/scenarios/{scenario_id}", summary="获取场景模板详情")
async def get_scenario(
    scenario_id: int,
    svc: ScenarioApplicationService = Depends(get_scenario_service),
):
    scenario = await svc.get_scenario(scenario_id)
    return success_response(data=scenario.model_dump())


@router.put("/scenarios/{scenario_id}", summary="更新场景模板")
async def update_scenario(
    scenario_id: int,
    body: UpdateScenarioDTO,
    svc: ScenarioApplicationService = Depends(get_scenario_service),
):
    scenario = await svc.update_scenario(scenario_id, body)
    return success_response(data=scenario.model_dump())


@router.delete("/scenarios/{scenario_id}", summary="删除场景模板")
async def delete_scenario(
    scenario_id: int,
    svc: ScenarioApplicationService = Depends(get_scenario_service),
):
    deleted = await svc.delete_scenario(scenario_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return success_response(data=None)


# ---------------------------------------------------------------------------
# Analysis Report endpoints
# ---------------------------------------------------------------------------


@router.post("/rooms/{room_id}/analysis", summary="生成对话分析报告", status_code=201)
async def generate_analysis(
    room_id: int,
    background_tasks: BackgroundTasks,
    svc: AnalysisService = Depends(get_analysis_service),
    growth_svc=Depends(get_growth_service),
):
    report = await svc.generate_report(room_id)
    # Auto-trigger competency evaluation in background
    background_tasks.add_task(growth_svc.evaluate_competency, report.id)
    return success_response(data=report.model_dump())


@router.get("/rooms/{room_id}/analysis", summary="获取对话分析报告列表")
async def list_analysis_reports(
    room_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    svc: AnalysisReaderService = Depends(get_analysis_reader_service),
):
    reports = await svc.list_reports(room_id, skip=skip, limit=limit)
    return success_response(data=[r.model_dump() for r in reports])


@router.get("/rooms/{room_id}/analysis/{report_id}", summary="获取分析报告详情")
async def get_analysis_report(
    room_id: int,
    report_id: int,
    svc: AnalysisReaderService = Depends(get_analysis_reader_service),
):
    report = await svc.get_report(report_id)
    if report is None or report.room_id != room_id:
        raise HTTPException(status_code=404, detail="Analysis report not found")
    return success_response(data=report.model_dump())


# ---------------------------------------------------------------------------
# Coaching endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/rooms/{room_id}/analysis/{report_id}/coaching",
    summary="开始复盘对话",
    status_code=201,
)
async def start_coaching(
    room_id: int,
    report_id: int,
    svc: CoachingService = Depends(get_coaching_service),
):
    """Create a coaching session and stream the Coach's opening message (SSE)."""
    # Validate & prepare before streaming so exceptions become normal HTTP errors
    ctx = await svc.prepare_start_session(room_id, report_id)
    return StreamingResponse(
        svc.stream_opening(ctx),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Live coaching endpoints (stateless, no DB writes)
# ---------------------------------------------------------------------------


@router.post(
    "/rooms/{room_id}/coaching/live",
    summary="实时求助教练",
)
async def start_live_coaching(
    room_id: int,
    svc: CoachingService = Depends(get_coaching_service),
):
    """Stream live coaching advice based on current conversation context (SSE)."""
    ctx = await svc.prepare_live_advice(room_id)
    return StreamingResponse(
        svc.stream_live_advice(ctx),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/rooms/{room_id}/coaching/live/reply",
    summary="实时教练追问",
)
async def send_live_coaching_reply(
    room_id: int,
    body: dict,
    svc: CoachingService = Depends(get_coaching_service),
):
    """Follow-up question to live coach. Frontend sends full coaching history."""
    content = body.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message content is required")
    coaching_history: list[dict] = body.get("history", [])
    # Append the new user message to history
    coaching_history.append({"role": "user", "content": content})
    ctx = await svc.prepare_live_advice(room_id)
    return StreamingResponse(
        svc.stream_live_advice(ctx, coaching_history=coaching_history),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/rooms/{room_id}/coaching/{session_id}/messages",
    summary="发送复盘消息",
)
async def send_coaching_message(
    room_id: int,
    session_id: int,
    body: dict,
    svc: CoachingService = Depends(get_coaching_service),
):
    """Send a user message and stream the Coach's reply (SSE)."""
    content = body.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message content is required")
    # Validate & prepare before streaming so exceptions become normal HTTP errors
    ctx = await svc.prepare_send_message(room_id, session_id, content)
    return StreamingResponse(
        svc.stream_reply(ctx),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/rooms/{room_id}/coaching/{session_id}", summary="获取复盘会话详情")
async def get_coaching_session(
    room_id: int,
    session_id: int,
    svc: CoachingService = Depends(get_coaching_service),
):
    session = await svc.get_session(session_id)
    if session is None or session.room_id != room_id:
        raise HTTPException(status_code=404, detail="Coaching session not found")
    return success_response(data=session.model_dump())


@router.get("/rooms/{room_id}/coaching", summary="获取复盘会话列表")
async def list_coaching_sessions(
    room_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    svc: CoachingService = Depends(get_coaching_service),
):
    sessions = await svc.list_sessions(room_id, skip=skip, limit=limit)
    return success_response(data=[s.model_dump() for s in sessions])


# ---------------------------------------------------------------------------
# Organization endpoints
# ---------------------------------------------------------------------------


@router.post("/organizations", status_code=201, summary="创建组织")
async def create_organization(
    body: CreateOrganizationDTO,
    svc: OrganizationService = Depends(get_organization_service),
):
    org = await svc.create_organization(body)
    return success_response(data=org.model_dump())


@router.get("/organizations", summary="列出所有组织")
async def list_organizations(
    svc: OrganizationService = Depends(get_organization_service),
):
    orgs = await svc.list_organizations()
    return success_response(data=[o.model_dump() for o in orgs])


@router.get("/organizations/{org_id}", summary="获取组织详情（含团队）")
async def get_organization(
    org_id: int,
    svc: OrganizationService = Depends(get_organization_service),
):
    detail = await svc.get_organization(org_id)
    return success_response(data=detail.model_dump())


@router.put("/organizations/{org_id}", summary="更新组织")
async def update_organization(
    org_id: int,
    body: UpdateOrganizationDTO,
    svc: OrganizationService = Depends(get_organization_service),
):
    org = await svc.update_organization(org_id, body)
    return success_response(data=org.model_dump())


@router.delete("/organizations/{org_id}", summary="删除组织")
async def delete_organization(
    org_id: int,
    svc: OrganizationService = Depends(get_organization_service),
):
    await svc.delete_organization(org_id)
    return success_response(data=None)


# ---------------------------------------------------------------------------
# Team endpoints
# ---------------------------------------------------------------------------


@router.post("/organizations/{org_id}/teams", status_code=201, summary="创建团队")
async def create_team(
    org_id: int,
    body: CreateTeamDTO,
    svc: OrganizationService = Depends(get_organization_service),
):
    team = await svc.create_team(org_id, body)
    return success_response(data=team.model_dump())


@router.get("/organizations/{org_id}/teams", summary="列出团队")
async def list_teams(
    org_id: int,
    svc: OrganizationService = Depends(get_organization_service),
):
    teams = await svc.list_teams(org_id)
    return success_response(data=[t.model_dump() for t in teams])


@router.put("/organizations/{org_id}/teams/{team_id}", summary="更新团队")
async def update_team(
    org_id: int,
    team_id: int,
    body: UpdateTeamDTO,
    svc: OrganizationService = Depends(get_organization_service),
):
    team = await svc.update_team(org_id, team_id, body)
    return success_response(data=team.model_dump())


@router.delete("/organizations/{org_id}/teams/{team_id}", summary="删除团队")
async def delete_team(
    org_id: int,
    team_id: int,
    svc: OrganizationService = Depends(get_organization_service),
):
    await svc.delete_team(org_id, team_id)
    return success_response(data=None)


# ---------------------------------------------------------------------------
# Persona Relationship endpoints
# ---------------------------------------------------------------------------


@router.post("/organizations/{org_id}/relationships", status_code=201, summary="创建角色关系")
async def create_relationship(
    org_id: int,
    body: CreateRelationshipDTO,
    svc: OrganizationService = Depends(get_organization_service),
):
    rel = await svc.create_relationship(org_id, body)
    return success_response(data=rel.model_dump())


@router.get("/organizations/{org_id}/relationships", summary="列出角色关系")
async def list_relationships(
    org_id: int,
    svc: OrganizationService = Depends(get_organization_service),
):
    rels = await svc.list_relationships(org_id)
    return success_response(data=[r.model_dump() for r in rels])


@router.put("/organizations/{org_id}/relationships/{rel_id}", summary="更新角色关系")
async def update_relationship(
    org_id: int,
    rel_id: int,
    body: UpdateRelationshipDTO,
    svc: OrganizationService = Depends(get_organization_service),
):
    rel = await svc.update_relationship(org_id, rel_id, body)
    return success_response(data=rel.model_dump())


@router.delete("/organizations/{org_id}/relationships/{rel_id}", summary="删除角色关系")
async def delete_relationship(
    org_id: int,
    rel_id: int,
    svc: OrganizationService = Depends(get_organization_service),
):
    await svc.delete_relationship(org_id, rel_id)
    return success_response(data=None)


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


# ---------------------------------------------------------------------------
# Growth Dashboard endpoints
# ---------------------------------------------------------------------------


@router.get("/growth/dashboard", summary="获取成长轨迹 Dashboard 数据")
async def get_growth_dashboard(
    svc=Depends(get_growth_service),
):
    dashboard = await svc.get_dashboard()
    return success_response(data=dashboard.model_dump())


@router.post("/growth/insight", summary="生成跨 session 成长洞察")
async def generate_growth_insight(
    svc=Depends(get_growth_service),
):
    insight = await svc.generate_insight()
    return success_response(data=insight.model_dump())


@router.post("/growth/card", summary="生成沟通力名片")
async def generate_profile_card(
    svc=Depends(get_growth_service),
):
    result = await svc.generate_profile_card()
    if result is None:
        raise HTTPException(status_code=502, detail="名片生成失败，请重试")
    return success_response(data=result.model_dump())


# ---------------------------------------------------------------------------
# Persona Builder SSE endpoint (Story 2.5)
# ---------------------------------------------------------------------------

# AC6: char-count approximation of token budget. ~2 chars per token avg
# (CJK-heavy traffic) → 200k tokens ≈ 400k chars.
_PERSONA_BUILD_CHAR_LIMIT = 400_000
_PERSONA_BUILD_HEARTBEAT_S = 30.0


def _persona_build_sse_payload(
    *, seq: int, type_: str, ts: float, data: dict
) -> str:
    """Serialize one BuildEvent envelope as SSE (per AC3)."""
    import json

    body = {"seq": seq, "type": type_, "ts": ts, "data": data}
    return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"


@router.post("/persona/build", summary="从素材构建画像 (Story 2.5 SSE)")
async def build_persona_stream(
    body: PersonaBuildRequestDTO,
    svc=Depends(get_persona_builder_service),
):
    """SSE: 流式返回 PersonaBuilderService.build() 事件。

    AC2 事件类型：workspace_ready | agent_tool_use | agent_message |
    parse_done | adversarialize_start | adversarialize_done |
    persist_done | heartbeat | error
    AC3 envelope: {seq, type, ts, data}, seq monotonic from 1
    AC4 heartbeat 每 30s
    AC6 materials > 400k chars → 413 + MATERIAL_TOO_LARGE
    AC7 materials 为空 → 400 + MATERIAL_EMPTY
    AC9 客户端断开后 producer 仍跑完并落库
    """
    # AC7: empty materials check (DTO 强制 ≥1 个，但 element 可能是空字符串)
    cleaned = [m for m in body.materials if m and m.strip()]
    if not cleaned:
        raise HTTPException(
            status_code=400,
            detail={"code": "MATERIAL_EMPTY", "message": "materials must not be empty"},
        )

    # AC6: char-count token approximation
    total_chars = sum(len(m) for m in cleaned)
    if total_chars > _PERSONA_BUILD_CHAR_LIMIT:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "MATERIAL_TOO_LARGE",
                "message": (
                    f"materials too large: {total_chars} chars "
                    f"(limit ≈ {_PERSONA_BUILD_CHAR_LIMIT} chars / 200k tokens)"
                ),
            },
        )

    # 临时使用匿名 user_id（项目尚无 get_current_user 认证依赖）
    user_id = "anonymous"

    # Decoupled producer/consumer so client disconnect does NOT abort the
    # underlying build (AC9). Producer runs in its own task and pushes to a
    # queue; the SSE generator is a pure consumer.
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    sentinel_done = ("__done__", None)

    async def _producer() -> None:
        try:
            async for ev in svc.build(
                user_id=user_id,
                materials=cleaned,
                name=body.name,
                role=body.role,
                target_persona_id=body.target_persona_id,
            ):
                await queue.put(("event", ev))
        except Exception as exc:  # noqa: BLE001 — relayed to client as error event
            # PersonaBuilderService already emits its own error event before
            # raising. We push a fallback error in case it didn't.
            await queue.put(
                (
                    "fallback_error",
                    {
                        "error_code": getattr(exc, "error_code", "BUILD_FAILED"),
                        "message": f"{type(exc).__name__}: {exc}",
                    },
                )
            )
        finally:
            await queue.put(sentinel_done)

    producer_task = asyncio.create_task(_producer())

    async def event_stream():
        seen_error = False
        next_heartbeat_seq = 10_000  # heartbeat seq pool — separate from build seq
        try:
            while True:
                try:
                    kind, payload = await asyncio.wait_for(
                        queue.get(), timeout=_PERSONA_BUILD_HEARTBEAT_S
                    )
                except asyncio.TimeoutError:
                    # AC4: heartbeat
                    next_heartbeat_seq += 1
                    yield _persona_build_sse_payload(
                        seq=next_heartbeat_seq,
                        type_="heartbeat",
                        ts=time.time(),
                        data={},
                    )
                    continue

                if kind == "__done__":
                    break

                if kind == "event":
                    yield _persona_build_sse_payload(
                        seq=payload.seq,
                        type_=payload.type,
                        ts=payload.ts,
                        data=payload.data,
                    )
                    if payload.type == "error":
                        seen_error = True
                elif kind == "fallback_error" and not seen_error:
                    next_heartbeat_seq += 1
                    yield _persona_build_sse_payload(
                        seq=next_heartbeat_seq,
                        type_="error",
                        ts=time.time(),
                        data=payload,
                    )
        except asyncio.CancelledError:
            # AC9: client disconnected — producer keeps running in background
            # to completion (it has its own try/finally + PersonaBuildCache write).
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
