# input: shared.codes.BusinessCode
# output: 对话领域异常类
# owner: unknown
# pos: 领域层 - 对话聚合异常定义；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Domain exceptions for the conversation aggregate."""

from __future__ import annotations

from typing import Optional

from domain.common.exceptions import BusinessException
from shared.codes import BusinessCode


class ConversationNotFoundException(BusinessException):
    def __init__(self, conversation_id: Optional[int] = None):
        details = {"conversation_id": conversation_id} if conversation_id is not None else None
        super().__init__(
            code=BusinessCode.CONVERSATION_NOT_FOUND,
            message="Conversation not found",
            error_type="ConversationNotFound",
            details=details,
            message_key="conversation.not_found",
        )


class ConversationArchivedException(BusinessException):
    def __init__(self, conversation_id: Optional[int] = None):
        details = {"conversation_id": conversation_id} if conversation_id is not None else None
        super().__init__(
            code=BusinessCode.CONVERSATION_ARCHIVED,
            message="Conversation is archived",
            error_type="ConversationArchived",
            details=details,
            message_key="conversation.archived",
        )


class RunNotFoundException(BusinessException):
    def __init__(self, run_id: Optional[int] = None):
        details = {"run_id": run_id} if run_id is not None else None
        super().__init__(
            code=BusinessCode.RUN_NOT_FOUND,
            message="Run not found",
            error_type="RunNotFound",
            details=details,
            message_key="run.not_found",
        )


class AgentConfigNotFoundException(BusinessException):
    def __init__(self, config_id: Optional[int] = None):
        details = {"config_id": config_id} if config_id is not None else None
        super().__init__(
            code=BusinessCode.AGENT_CONFIG_NOT_FOUND,
            message="Agent config not found",
            error_type="AgentConfigNotFound",
            details=details,
            message_key="agent_config.not_found",
        )


class AgentConfigNameExistsException(BusinessException):
    def __init__(self, name: str):
        super().__init__(
            code=BusinessCode.AGENT_CONFIG_NAME_EXISTS,
            message=f"Agent config name '{name}' already exists",
            error_type="AgentConfigNameExists",
            details={"name": name},
            field="name",
            message_key="agent_config.name.exists",
        )


class LLMProviderException(BusinessException):
    def __init__(self, message: str = "LLM provider error", *, details: Optional[dict] = None):
        super().__init__(
            code=BusinessCode.LLM_PROVIDER_ERROR,
            message=message,
            error_type="LLMProviderError",
            details=details,
            message_key="llm.provider.error",
        )


class LLMTimeoutException(BusinessException):
    def __init__(self):
        super().__init__(
            code=BusinessCode.LLM_TIMEOUT,
            message="LLM request timed out",
            error_type="LLMTimeout",
            message_key="llm.timeout",
        )
