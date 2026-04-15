import pytest
from unittest.mock import AsyncMock, MagicMock
from application.services.defense_prep_service import DefensePrepService
from domain.defense_prep.value_objects import DocumentSummary, PlannedQuestion
from domain.defense_prep.scenario import ScenarioType


@pytest.fixture
def mock_deps():
    uow = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.defense_session_repository = AsyncMock()
    uow.commit = AsyncMock()
    llm = AsyncMock()
    parser = AsyncMock()
    chatroom_svc = AsyncMock()
    persona_loader = MagicMock()
    return uow, llm, parser, chatroom_svc, persona_loader


class TestDefensePrepService:
    @pytest.mark.asyncio
    async def test_create_session_parses_doc_and_persists(self, mock_deps):
        uow, llm, parser, chatroom_svc, persona_loader = mock_deps
        parser.parse.return_value = DocumentSummary(
            title="Q1报告", sections=[], key_data=["30%"], raw_text="full text"
        )
        uow.defense_session_repository.create.side_effect = lambda s: setattr(s, "id", 1) or s

        service = DefensePrepService(
            uow_factory=lambda: uow,
            llm=llm,
            document_parser=parser,
            chatroom_service=chatroom_svc,
            persona_loader=persona_loader,
        )
        session = await service.create_session(
            file_content=b"fake pptx bytes",
            filename="Q1报告.pptx",
            persona_ids=["persona-001", "persona-002"],
            scenario_type=ScenarioType.PERFORMANCE_REVIEW,
        )
        parser.parse.assert_called_once_with(b"fake pptx bytes", "Q1报告.pptx")
        uow.defense_session_repository.create.assert_called_once()
        assert session.id == 1
        assert session.persona_ids == ["persona-001", "persona-002"]
        assert session.status == "preparing"


class TestInterleaveByDimension:
    def test_interleaves_questions_by_dimension(self, mock_deps):
        uow, llm, parser, chatroom_svc, persona_loader = mock_deps
        service = DefensePrepService(
            uow_factory=lambda: uow,
            llm=llm,
            document_parser=parser,
            chatroom_service=chatroom_svc,
            persona_loader=persona_loader,
        )
        questions = [
            PlannedQuestion(question="Q1", dimension="business", asked_by="p1"),
            PlannedQuestion(question="Q2", dimension="tech", asked_by="p1"),
            PlannedQuestion(question="Q3", dimension="business", asked_by="p2"),
            PlannedQuestion(question="Q4", dimension="tech", asked_by="p2"),
        ]
        result = service._interleave_by_dimension(questions)
        assert result[0].question == "Q1"
        assert result[1].question == "Q3"
        assert result[2].question == "Q2"
        assert result[3].question == "Q4"

    def test_handles_single_persona(self, mock_deps):
        uow, llm, parser, chatroom_svc, persona_loader = mock_deps
        service = DefensePrepService(
            uow_factory=lambda: uow,
            llm=llm,
            document_parser=parser,
            chatroom_service=chatroom_svc,
            persona_loader=persona_loader,
        )
        questions = [
            PlannedQuestion(question="Q1", dimension="a", asked_by="p1"),
            PlannedQuestion(question="Q2", dimension="b", asked_by="p1"),
        ]
        result = service._interleave_by_dimension(questions)
        assert len(result) == 2
