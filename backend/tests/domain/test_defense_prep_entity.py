import pytest
from domain.defense_prep.entity import DefenseSession, DefenseSessionStatus
from domain.defense_prep.value_objects import (
    DocumentSummary,
    Section,
    QuestionStrategy,
    PlannedQuestion,
)
from domain.defense_prep.scenario import ScenarioType, SCENARIO_CONFIGS


class TestDefenseSession:
    def test_create_valid_session(self):
        summary = DocumentSummary(
            title="Q1 述职报告",
            sections=[Section(title="业绩", bullet_points=["营收增长30%"])],
            key_data=["30%", "500万"],
            raw_text="完整文本内容",
        )
        session = DefenseSession(
            id=None,
            persona_ids=["persona-001"],
            scenario_type=ScenarioType.PERFORMANCE_REVIEW,
            document_summary=summary,
        )
        assert session.status == DefenseSessionStatus.PREPARING
        assert session.room_id is None
        assert session.question_strategy is None
        assert session.created_at is not None

    def test_invalid_status_raises(self):
        from domain.common.exceptions import DomainValidationException

        summary = DocumentSummary(title="test", sections=[], key_data=[], raw_text="text")
        with pytest.raises(DomainValidationException):
            DefenseSession(
                id=None,
                persona_ids=["p1"],
                scenario_type=ScenarioType.GENERAL,
                document_summary=summary,
                status="bogus",
            )

    def test_transition_to_in_progress(self):
        summary = DocumentSummary(title="test", sections=[], key_data=[], raw_text="text")
        session = DefenseSession(
            id=1,
            persona_ids=["p1"],
            scenario_type=ScenarioType.PROPOSAL_REVIEW,
            document_summary=summary,
        )
        session.start(room_id=42)
        assert session.status == DefenseSessionStatus.IN_PROGRESS
        assert session.room_id == 42

    def test_transition_to_completed(self):
        summary = DocumentSummary(title="test", sections=[], key_data=[], raw_text="text")
        session = DefenseSession(
            id=1,
            persona_ids=["p1"],
            scenario_type=ScenarioType.GENERAL,
            document_summary=summary,
            status=DefenseSessionStatus.IN_PROGRESS,
            room_id=10,
        )
        session.complete()
        assert session.status == DefenseSessionStatus.COMPLETED

    def test_create_session_with_multiple_personas(self):
        summary = DocumentSummary(title="test", sections=[], key_data=[], raw_text="text")
        session = DefenseSession(
            id=None,
            persona_ids=["p1", "p2", "p3"],
            scenario_type=ScenarioType.GENERAL,
            document_summary=summary,
        )
        assert session.persona_ids == ["p1", "p2", "p3"]
        assert session.status == DefenseSessionStatus.PREPARING

    def test_empty_persona_ids_raises(self):
        from domain.common.exceptions import DomainValidationException

        summary = DocumentSummary(title="test", sections=[], key_data=[], raw_text="text")
        with pytest.raises(DomainValidationException):
            DefenseSession(
                id=None,
                persona_ids=[],
                scenario_type=ScenarioType.GENERAL,
                document_summary=summary,
            )

    def test_too_many_persona_ids_raises(self):
        from domain.common.exceptions import DomainValidationException

        summary = DocumentSummary(title="test", sections=[], key_data=[], raw_text="text")
        with pytest.raises(DomainValidationException):
            DefenseSession(
                id=None,
                persona_ids=["a", "b", "c", "d", "e", "f"],
                scenario_type=ScenarioType.GENERAL,
                document_summary=summary,
            )


class TestScenarioConfig:
    def test_performance_review_has_dimensions(self):
        config = SCENARIO_CONFIGS[ScenarioType.PERFORMANCE_REVIEW]
        assert "dimensions" in config
        assert len(config["dimensions"]) >= 5

    def test_all_types_have_config(self):
        for st in ScenarioType:
            assert st in SCENARIO_CONFIGS, f"Missing config for {st}"
