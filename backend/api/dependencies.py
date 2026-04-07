"""
API 依赖项
"""

from fastapi import Depends

from application.services.file_asset_service import FileAssetApplicationService
from application.services.idempotency_service import IdempotencyService
from application.services.conversation_service import ConversationApplicationService
from application.services.chat_service import ChatApplicationService
from application.services.stakeholder.chatroom_service import ChatRoomApplicationService
from application.services.stakeholder.persona_loader import PersonaLoader
from application.services.stakeholder.persona_editor_service import PersonaEditorService
from application.services.stakeholder.scenario_service import ScenarioApplicationService
from application.services.stakeholder.analysis_service import AnalysisService, AnalysisReaderService
from application.services.stakeholder.coaching_service import CoachingService
from application.services.stakeholder.stakeholder_chat_service import StakeholderChatService
from application.ports.storage import StoragePort
from application.ports.llm import LLMPort
from infrastructure.unit_of_work import SQLAlchemyUnitOfWork
from infrastructure.external.storage import get_storage
from infrastructure.external.llm import get_llm_client, get_anthropic_client
from infrastructure.adapters.storage_port import StorageProviderPortAdapter
from infrastructure.adapters.idempotency_store import RedisIdempotencyStore
from core.config import settings


async def get_storage_port(provider=Depends(get_storage)) -> StoragePort:
    return StorageProviderPortAdapter(provider)


async def get_file_asset_service(
    storage: StoragePort = Depends(get_storage_port),
) -> FileAssetApplicationService:
    return FileAssetApplicationService(uow_factory=SQLAlchemyUnitOfWork, storage=storage)


async def get_idempotency_service() -> IdempotencyService:
    if not settings.redis.url:

        class _NoopStore:
            async def get(self, *, scope: str, key: str):
                return None

            async def try_start(
                self, *, scope: str, key: str, request_hash: str, ttl_seconds: int
            ) -> bool:
                return True

            async def set_result(
                self, *, scope: str, key: str, request_hash: str, payload: dict, ttl_seconds: int
            ) -> None:
                return None

            async def release(self, *, scope: str, key: str) -> None:
                return None

        store = _NoopStore()
    else:
        store = RedisIdempotencyStore()
    return IdempotencyService(
        store=store,
        lock_ttl_seconds=settings.idempotency.lock_ttl_seconds,
        result_ttl_seconds=settings.idempotency.result_ttl_seconds,
    )


async def get_conversation_service() -> ConversationApplicationService:
    return ConversationApplicationService(uow_factory=SQLAlchemyUnitOfWork)


async def get_llm_port() -> LLMPort:
    client = get_llm_client()
    if client is None:
        raise RuntimeError(
            "LLM client not initialized. " "Set LLM__API_KEY in environment or .env and restart."
        )
    return client


async def get_stakeholder_llm_port() -> LLMPort:
    client = get_anthropic_client()
    if client is None:
        raise RuntimeError(
            "Anthropic client not initialized. "
            "Set STAKEHOLDER__ANTHROPIC_API_KEY in environment or .env and restart."
        )
    return client


def get_persona_loader() -> PersonaLoader:
    return PersonaLoader(persona_dir=settings.stakeholder.persona_dir)


def get_persona_editor_service(
    loader: PersonaLoader = Depends(get_persona_loader),
) -> PersonaEditorService:
    return PersonaEditorService(persona_dir=settings.stakeholder.persona_dir, persona_loader=loader)


def get_chatroom_service(
    loader: PersonaLoader = Depends(get_persona_loader),
) -> ChatRoomApplicationService:
    return ChatRoomApplicationService(uow_factory=SQLAlchemyUnitOfWork, persona_loader=loader)


async def get_stakeholder_chat_service(
    loader: PersonaLoader = Depends(get_persona_loader),
    llm: LLMPort = Depends(get_stakeholder_llm_port),
) -> StakeholderChatService:
    from application.services.stakeholder.dispatcher import Dispatcher

    dispatcher = Dispatcher(llm=llm, persona_loader=loader)
    return StakeholderChatService(
        uow_factory=SQLAlchemyUnitOfWork,
        persona_loader=loader,
        llm=llm,
        dispatcher=dispatcher,
        max_group_rounds=settings.stakeholder.max_group_rounds,
    )


async def get_analysis_service(
    loader: PersonaLoader = Depends(get_persona_loader),
    llm: LLMPort = Depends(get_stakeholder_llm_port),
) -> AnalysisService:
    return AnalysisService(uow_factory=SQLAlchemyUnitOfWork, llm=llm, persona_loader=loader)


def get_analysis_reader_service() -> AnalysisReaderService:
    """Read-only analysis service for list/get (no LLM or PersonaLoader needed)."""
    return AnalysisReaderService(uow_factory=SQLAlchemyUnitOfWork)


async def get_coaching_service(
    loader: PersonaLoader = Depends(get_persona_loader),
    llm: LLMPort = Depends(get_stakeholder_llm_port),
) -> CoachingService:
    return CoachingService(uow_factory=SQLAlchemyUnitOfWork, llm=llm, persona_loader=loader)


def get_scenario_service() -> ScenarioApplicationService:
    return ScenarioApplicationService(uow_factory=SQLAlchemyUnitOfWork)


async def get_chat_service(
    llm: LLMPort = Depends(get_llm_port),
) -> ChatApplicationService:
    return ChatApplicationService(uow_factory=SQLAlchemyUnitOfWork, llm=llm)
