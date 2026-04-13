# input: SQLAlchemyStakeholderPersonaRepository + in-memory SQLite
# output: Story 2.2 AC4/AC6 stakeholder persona 仓储集成测试
# owner: wanhua.gu
# pos: 测试层 - Story 2.2 stakeholder persona 仓储集成测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Story 2.2: SQLAlchemyStakeholderPersonaRepository (AC4, AC6)."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from domain.stakeholder.persona_entity import (
    DecisionPattern,
    Evidence,
    ExpressionStyle,
    HardRule,
    IdentityProfile,
    InterpersonalStyle,
    Persona,
)
from infrastructure.models.base import Base
from infrastructure.repositories.stakeholder_persona_repository import (
    SQLAlchemyStakeholderPersonaRepository,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _make_v2_persona(persona_id: str = "cfo") -> Persona:
    return Persona(
        id=persona_id,
        name="CFO",
        role="首席财务官",
        avatar_color="#123456",
        profile_summary="数字至上",
        full_content="",
        hard_rules=[HardRule(statement="预算超支必报", severity="critical")],
        identity=IdentityProfile(
            background="会计师", core_values=["成本"], hidden_agenda="裁员"
        ),
        expression=ExpressionStyle(
            tone="严谨", catchphrases=["数字会说话"], interruption_tendency="low"
        ),
        decision=DecisionPattern(
            style="保守", risk_tolerance="low", typical_questions=["ROI?"]
        ),
        interpersonal=InterpersonalStyle(
            authority_mode="正式", triggers=["数据造假"], emotion_states=["严肃"]
        ),
        evidence_citations=[
            Evidence(
                claim="严谨",
                citations=["「请按会计准则」"],
                confidence=0.9,
                source_material_id="mat-1",
                layer="expression",
            ),
            Evidence(
                claim="保守",
                citations=["「这个风险太大」"],
                confidence=0.85,
                source_material_id="mat-1",
                layer="decision",
            ),
        ],
        schema_version=2,
        legacy_content="# 旧 markdown",
        source_materials=["mat-1"],
    )


# ---------------------------------------------------------------------------
# AC4: schema 列存在
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schema_columns_exist(engine) -> None:
    """AC4: 所有要求的列存在。"""
    def _inspect(sync_conn):
        insp = inspect(sync_conn)
        cols = {c["name"] for c in insp.get_columns("stakeholder_personas")}
        return cols

    async with engine.connect() as conn:
        cols = await conn.run_sync(_inspect)

    for required in [
        "id",
        "name",
        "role",
        "structured_profile",
        "evidence_citations",
        "schema_version",
        "source_materials",
        "legacy_content",
        "full_content",
    ]:
        assert required in cols, f"missing column: {required}"


# ---------------------------------------------------------------------------
# AC6: save_structured_persona + get_with_evidence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_then_get_with_evidence(session_factory) -> None:
    """AC6: save 后 get_with_evidence 证据链数量一致。"""
    async with session_factory() as session:
        repo = SQLAlchemyStakeholderPersonaRepository(session)
        persona = _make_v2_persona()
        saved = await repo.save_structured_persona(persona)
        await session.commit()

        assert saved.id == "cfo"
        assert saved.schema_version == 2
        assert len(saved.evidence_citations) == 2

    # Re-query in a fresh session
    async with session_factory() as session:
        repo = SQLAlchemyStakeholderPersonaRepository(session)
        result = await repo.get_with_evidence("cfo")
        assert result is not None
        loaded, evidences = result
        assert loaded.id == "cfo"
        assert loaded.schema_version == 2
        assert loaded.identity is not None
        assert loaded.identity.background == "会计师"
        assert len(evidences) == 2
        assert {e.layer for e in evidences} == {"expression", "decision"}


@pytest.mark.asyncio
async def test_get_with_evidence_not_found(session_factory) -> None:
    async with session_factory() as session:
        repo = SQLAlchemyStakeholderPersonaRepository(session)
        result = await repo.get_with_evidence("nonexistent")
        assert result is None


@pytest.mark.asyncio
async def test_save_is_upsert(session_factory) -> None:
    """save_structured_persona 对已存在 id 执行 UPDATE 而非冲突。"""
    async with session_factory() as session:
        repo = SQLAlchemyStakeholderPersonaRepository(session)
        await repo.save_structured_persona(_make_v2_persona("boss"))
        await session.commit()

        updated = _make_v2_persona("boss")
        updated.name = "Updated Name"
        await repo.save_structured_persona(updated)
        await session.commit()

    async with session_factory() as session:
        repo = SQLAlchemyStakeholderPersonaRepository(session)
        loaded = await repo.get_by_id("boss")
        assert loaded is not None
        assert loaded.name == "Updated Name"


@pytest.mark.asyncio
async def test_list_all_filter_by_schema_version(session_factory) -> None:
    async with session_factory() as session:
        repo = SQLAlchemyStakeholderPersonaRepository(session)
        await repo.save_structured_persona(_make_v2_persona("a"))
        # Insert v1-only persona via direct model
        v1 = Persona(id="old", name="Legacy", role="x", full_content="# md", schema_version=1)
        await repo.save_structured_persona(v1)
        await session.commit()

        all_v2 = await repo.list_all(schema_version=2)
        assert {p.id for p in all_v2} == {"a"}

        all_any = await repo.list_all()
        assert {p.id for p in all_any} == {"a", "old"}
