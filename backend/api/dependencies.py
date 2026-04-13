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
from application.ports.tts import TTSPort
from application.ports.stt import STTPort
from infrastructure.unit_of_work import SQLAlchemyUnitOfWork
from infrastructure.external.storage import get_storage
from infrastructure.external.llm import get_llm_client, get_anthropic_client
from infrastructure.external.voice import get_tts_client, get_stt_client
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


async def get_tts_port() -> TTSPort:
    client = get_tts_client()
    if client is None:
        raise RuntimeError(
            "TTS client not initialized. "
            "Set VOICE__TTS_API_KEY in environment or .env and restart."
        )
    return client


async def get_stt_port() -> STTPort:
    client = get_stt_client()
    if client is None:
        raise RuntimeError(
            "STT client not initialized. "
            "Set VOICE__STT_API_KEY in environment or .env and restart."
        )
    return client


def get_persona_loader() -> PersonaLoader:
    return PersonaLoader(persona_dir=settings.stakeholder.persona_dir)


async def get_persona_loader_with_v2(
    loader: PersonaLoader = Depends(get_persona_loader),
) -> PersonaLoader:
    """Story 2.8: make v2 DB personas visible to chat / battle flows.

    Merges v2 structured personas into the loader's cache once per request.
    PersonaLoader itself has a 30 s TTL so repeated calls within a single
    request are near-free.
    """
    async with SQLAlchemyUnitOfWork() as uow:
        try:
            await loader.refresh_from_db(uow.stakeholder_persona_repository)
        except Exception:
            # Best-effort: a broken DB shouldn't knock out the chat flow entirely.
            pass
    return loader


def get_persona_editor_service(
    loader: PersonaLoader = Depends(get_persona_loader),
) -> PersonaEditorService:
    return PersonaEditorService(persona_dir=settings.stakeholder.persona_dir, persona_loader=loader)


def get_chatroom_service(
    loader: PersonaLoader = Depends(get_persona_loader_with_v2),
) -> ChatRoomApplicationService:
    return ChatRoomApplicationService(uow_factory=SQLAlchemyUnitOfWork, persona_loader=loader)


async def get_stakeholder_chat_service(
    loader: PersonaLoader = Depends(get_persona_loader_with_v2),
    llm: LLMPort = Depends(get_stakeholder_llm_port),
) -> StakeholderChatService:
    from application.services.stakeholder.compression_service import CompressionService
    from application.services.stakeholder.dispatcher import Dispatcher

    dispatcher = Dispatcher(llm=llm, persona_loader=loader)
    compression = CompressionService(
        uow_factory=SQLAlchemyUnitOfWork,
        llm=llm,
        persona_loader=loader,
    )
    # TTS is optional — None if not configured
    tts = get_tts_client()
    return StakeholderChatService(
        uow_factory=SQLAlchemyUnitOfWork,
        persona_loader=loader,
        llm=llm,
        dispatcher=dispatcher,
        max_group_rounds=settings.stakeholder.max_group_rounds,
        compression_service=compression,
        tts=tts,
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


def get_organization_service():
    from application.services.stakeholder.organization_service import OrganizationService

    return OrganizationService(uow_factory=SQLAlchemyUnitOfWork)


async def get_growth_service(
    loader: PersonaLoader = Depends(get_persona_loader),
    llm: LLMPort = Depends(get_stakeholder_llm_port),
):
    from application.services.stakeholder.growth_service import GrowthService

    return GrowthService(uow_factory=SQLAlchemyUnitOfWork, llm=llm, persona_loader=loader)


async def get_battle_prep_service(
    loader: PersonaLoader = Depends(get_persona_loader_with_v2),
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


async def get_chat_service(
    llm: LLMPort = Depends(get_llm_port),
) -> ChatApplicationService:
    return ChatApplicationService(uow_factory=SQLAlchemyUnitOfWork, llm=llm)


# ---------------------------------------------------------------------------
# Speaker Detection dependency
# ---------------------------------------------------------------------------


async def get_speaker_detection_service(
    llm: LLMPort = Depends(get_stakeholder_llm_port),
):
    from application.services.stakeholder.speaker_detection_service import SpeakerDetectionService

    return SpeakerDetectionService(llm=llm)


# ---------------------------------------------------------------------------
# Persona Builder dependencies (Story 2.4 / 2.5)
# ---------------------------------------------------------------------------


class _UoWBoundStakeholderPersonaRepo:
    """Adapter that gives PersonaBuilderService a save method that creates
    its own UoW per call (the build runs across many seconds, so binding to
    a single request-scoped session would be unsafe)."""

    def __init__(self, uow_factory):
        self._uow_factory = uow_factory

    async def save_structured_persona(self, persona):
        async with self._uow_factory() as uow:
            await uow.stakeholder_persona_repository.save_structured_persona(persona)
            await uow.commit()

    async def get_by_id(self, persona_id: str):
        async with self._uow_factory() as uow:
            return await uow.stakeholder_persona_repository.get_by_id(persona_id)


def _load_stakeholder_prompt(name: str) -> str:
    """Load a prompt markdown file from application/services/stakeholder/prompts/."""
    from importlib.resources import files

    return (
        files("application.services.stakeholder.prompts").joinpath(name).read_text(encoding="utf-8")
    )


async def get_persona_builder_service(
    llm: LLMPort = Depends(get_stakeholder_llm_port),
):
    """Construct a PersonaBuilderService for one request (Story 2.5).

    Uses the singleton AgentSkillClient + Anthropic LLM; persistence is via
    a UoW-bound adapter so the builder can save without holding the request
    session open across the entire build.
    """
    from application.services.stakeholder.persona_build_cache import PersonaBuildCache
    from application.services.stakeholder.persona_builder_service import (
        PersonaBuilderService,
    )
    from infrastructure.external.agent_sdk.lifespan import get_agent_sdk_client
    from infrastructure.external.cache.redis_client import (
        _redis_client as _shared_redis,
    )

    agent_client = get_agent_sdk_client()
    repo = _UoWBoundStakeholderPersonaRepo(SQLAlchemyUnitOfWork)
    cache = PersonaBuildCache(redis=_shared_redis)
    return PersonaBuilderService(
        agent_client=agent_client,
        llm=llm,
        repo=repo,
        cache=cache,
        adversarialize_prompt=_load_stakeholder_prompt("adversarialize.md"),
        parse_prompt=_load_stakeholder_prompt("persona_markdown_to_json.md"),
    )


# ---------------------------------------------------------------------------
# Persona V2 editor dependencies (Story 2.7)
# ---------------------------------------------------------------------------


def get_persona_v2_service():
    """Construct a PersonaV2Service for one request (Story 2.7).

    Takes the SQLAlchemy UoW class as its own factory so the service can open
    and close a session per call.
    """
    from application.services.stakeholder.persona_v2_service import PersonaV2Service

    return PersonaV2Service(uow_factory=SQLAlchemyUnitOfWork)
