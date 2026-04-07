# input: ConversationApplicationService 依赖注入
# output: 对话 + Agent 配置 CRUD HTTP 端点
# owner: unknown
# pos: 表示层路由 - 对话管理与 Agent 配置 CRUD API；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Conversation and AgentConfig CRUD routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_conversation_service
from application.dto import (
    AgentConfigDTO,
    ConversationDTO,
    CreateAgentConfigDTO,
    CreateConversationDTO,
    MessageDTO_Agent,
    RunDTO,
    UpdateAgentConfigDTO,
    UpdateConversationDTO,
)
from application.services.conversation_service import ConversationApplicationService
from core.config import settings
from core.i18n import t
from core.response import (
    PaginatedData,
    Response as ApiResponse,
    paginated_response,
    success_response,
)

# TODO: Add authentication dependency (get_current_user) to all routes
# when user/auth module is implemented. Currently matches project baseline
# where no routes require auth (see files.py, storage.py).
router = APIRouter(tags=["对话管理"])


# ── Conversations ──────────────────────────────────────────────────


@router.post(
    "/conversations",
    summary="创建对话",
    response_model=ApiResponse[ConversationDTO],
)
async def create_conversation(
    payload: CreateConversationDTO,
    service: ConversationApplicationService = Depends(get_conversation_service),
):
    conv = await service.create_conversation(payload)
    return success_response(conv, message=t("ok"))


@router.get(
    "/conversations",
    summary="对话列表",
    response_model=ApiResponse[PaginatedData[ConversationDTO]],
)
async def list_conversations(
    page: int = Query(1, ge=1),
    size: int = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    status: Optional[str] = Query(default=None),
    service: ConversationApplicationService = Depends(get_conversation_service),
):
    skip = (page - 1) * size
    items, total = await service.list_conversations(status=status, skip=skip, limit=size)
    return paginated_response(items=items, total=total, page=page, size=size)


@router.get(
    "/conversations/{conversation_id}",
    summary="对话详情",
    response_model=ApiResponse[ConversationDTO],
)
async def get_conversation(
    conversation_id: int,
    service: ConversationApplicationService = Depends(get_conversation_service),
):
    conv = await service.get_conversation(conversation_id)
    return success_response(conv, message=t("ok"))


@router.patch(
    "/conversations/{conversation_id}",
    summary="更新对话",
    response_model=ApiResponse[ConversationDTO],
)
async def update_conversation(
    conversation_id: int,
    payload: UpdateConversationDTO,
    service: ConversationApplicationService = Depends(get_conversation_service),
):
    conv = await service.update_conversation(conversation_id, payload)
    return success_response(conv, message=t("ok"))


@router.delete(
    "/conversations/{conversation_id}",
    summary="删除对话（软删除）",
    response_model=ApiResponse[ConversationDTO],
)
async def delete_conversation(
    conversation_id: int,
    service: ConversationApplicationService = Depends(get_conversation_service),
):
    conv = await service.delete_conversation(conversation_id)
    return success_response(conv, message=t("ok"))


@router.get(
    "/conversations/{conversation_id}/messages",
    summary="消息历史",
    response_model=ApiResponse[PaginatedData[MessageDTO_Agent]],
)
async def list_messages(
    conversation_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(default=100, ge=1, le=500),
    service: ConversationApplicationService = Depends(get_conversation_service),
):
    skip = (page - 1) * size
    items, total = await service.list_messages(conversation_id, skip=skip, limit=size)
    return paginated_response(items=items, total=total, page=page, size=size)


@router.get(
    "/conversations/{conversation_id}/runs",
    summary="Run 列表",
    response_model=ApiResponse[list[RunDTO]],
)
async def list_runs(
    conversation_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: ConversationApplicationService = Depends(get_conversation_service),
):
    items = await service.list_runs(conversation_id, skip=skip, limit=limit)
    return success_response(items, message=t("ok"))


# ── Agent Configs ──────────────────────────────────────────────────


@router.post(
    "/agent-configs",
    summary="创建 Agent 配置",
    response_model=ApiResponse[AgentConfigDTO],
)
async def create_agent_config(
    payload: CreateAgentConfigDTO,
    service: ConversationApplicationService = Depends(get_conversation_service),
):
    config = await service.create_agent_config(payload)
    return success_response(config, message=t("ok"))


@router.get(
    "/agent-configs",
    summary="Agent 配置列表",
    response_model=ApiResponse[PaginatedData[AgentConfigDTO]],
)
async def list_agent_configs(
    page: int = Query(1, ge=1),
    size: int = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    service: ConversationApplicationService = Depends(get_conversation_service),
):
    skip = (page - 1) * size
    items, total = await service.list_agent_configs(skip=skip, limit=size)
    return paginated_response(items=items, total=total, page=page, size=size)


@router.get(
    "/agent-configs/{config_id}",
    summary="Agent 配置详情",
    response_model=ApiResponse[AgentConfigDTO],
)
async def get_agent_config(
    config_id: int,
    service: ConversationApplicationService = Depends(get_conversation_service),
):
    config = await service.get_agent_config(config_id)
    return success_response(config, message=t("ok"))


@router.patch(
    "/agent-configs/{config_id}",
    summary="更新 Agent 配置",
    response_model=ApiResponse[AgentConfigDTO],
)
async def update_agent_config(
    config_id: int,
    payload: UpdateAgentConfigDTO,
    service: ConversationApplicationService = Depends(get_conversation_service),
):
    config = await service.update_agent_config(config_id, payload)
    return success_response(config, message=t("ok"))


@router.delete(
    "/agent-configs/{config_id}",
    summary="删除 Agent 配置",
    response_model=ApiResponse[dict],
)
async def delete_agent_config(
    config_id: int,
    service: ConversationApplicationService = Depends(get_conversation_service),
):
    await service.delete_agent_config(config_id)
    return success_response({"deleted": True}, message=t("ok"))
