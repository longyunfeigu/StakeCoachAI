# input: DefensePrepService (via dependencies)
# output: defense-prep API 路由 (sessions CRUD + start + report)
# owner: wanhua.gu
# pos: 表示层 - 答辩准备 API 路由；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Defense prep API routes."""
from __future__ import annotations
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from api.dependencies import get_defense_prep_service
from application.services.defense_prep_service import DefensePrepService
from core.response import success_response
from domain.defense_prep.scenario import ScenarioType

router = APIRouter(prefix="/defense-prep", tags=["Defense Prep"])

_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
_ALLOWED_EXTENSIONS = {".pptx", ".pdf", ".docx", ".txt", ".md"}


@router.post("/sessions")
async def create_session(
    file: UploadFile = File(...),
    persona_ids: str = Form(...),  # comma-separated
    scenario_type: str = Form(...),
    service: DefensePrepService = Depends(get_defense_prep_service),
):
    from pathlib import Path

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件格式: {ext}")
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(400, "文件大小不能超过 20MB")
    try:
        st = ScenarioType(scenario_type)
    except ValueError:
        raise HTTPException(400, f"无效的场景类型: {scenario_type}")

    # Parse and validate persona_ids
    pid_list = [p.strip() for p in persona_ids.split(",") if p.strip()]
    if not pid_list:
        raise HTTPException(400, "至少需要选择一位答辩官")
    if len(pid_list) > 5:
        raise HTTPException(400, "最多选择 5 位答辩官")
    if len(pid_list) != len(set(pid_list)):
        raise HTTPException(400, "答辩官不能重复选择")

    session = await service.create_session(
        file_content=content,
        filename=file.filename or "document",
        persona_ids=pid_list,
        scenario_type=st,
    )
    return success_response(
        {
            "id": session.id,
            "persona_ids": session.persona_ids,
            "scenario_type": session.scenario_type.value,
            "document_title": session.document_summary.title,
            "status": session.status,
            "created_at": session.created_at.isoformat() if session.created_at else None,
        }
    )


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: int, service: DefensePrepService = Depends(get_defense_prep_service)
):
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    data = {
        "id": session.id,
        "persona_ids": session.persona_ids,
        "scenario_type": session.scenario_type.value,
        "document_title": session.document_summary.title,
        "status": session.status,
        "room_id": session.room_id,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }
    if session.question_strategy:
        data["question_strategy"] = {
            "questions": [
                {
                    "question": q.question,
                    "dimension": q.dimension,
                    "difficulty": q.difficulty,
                    "asked_by": q.asked_by,
                }
                for q in session.question_strategy.questions
            ]
        }
    return success_response(data)


@router.post("/sessions/{session_id}/start")
async def start_session(
    session_id: int, service: DefensePrepService = Depends(get_defense_prep_service)
):
    try:
        session = await service.start_session(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return success_response(
        {
            "id": session.id,
            "room_id": session.room_id,
            "status": session.status,
            "question_strategy": {
                "questions": [
                    {
                        "question": q.question,
                        "dimension": q.dimension,
                        "difficulty": q.difficulty,
                        "asked_by": q.asked_by,
                    }
                    for q in (
                        session.question_strategy.questions if session.question_strategy else []
                    )
                ]
            },
        }
    )


@router.get("/sessions/{session_id}/report")
async def get_report(
    session_id: int, service: DefensePrepService = Depends(get_defense_prep_service)
):
    try:
        report = await service.generate_report(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return success_response(report)
