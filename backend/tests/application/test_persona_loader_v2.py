# input: PersonaLoader + StakeholderPersonaRepository
# output: Story 2.2 AC5/AC7 PersonaLoader v1/v2 双路径测试
# owner: wanhua.gu
# pos: 测试层 - Story 2.2 PersonaLoader v2 DB 路径验收测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Story 2.2: PersonaLoader v1/v2 dual-path (AC5, AC7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from application.services.stakeholder.persona_loader import PersonaLoader
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


async def _seed_v2_persona(session_factory, persona_id: str = "cfo") -> None:
    async with session_factory() as session:
        repo = SQLAlchemyStakeholderPersonaRepository(session)
        p = Persona(
            id=persona_id,
            name="CFO",
            role="首席财务官",
            hard_rules=[HardRule(statement="预算必审", severity="high")],
            identity=IdentityProfile(background="CPA", core_values=["成本"]),
            expression=ExpressionStyle(tone="严谨", catchphrases=["数字说话"]),
            decision=DecisionPattern(style="保守", risk_tolerance="low"),
            interpersonal=InterpersonalStyle(authority_mode="正式"),
            evidence_citations=[
                Evidence(
                    claim="严谨",
                    citations=["按会计准则"],
                    confidence=0.9,
                    source_material_id="m1",
                    layer="expression",
                )
            ],
            schema_version=2,
        )
        await repo.save_structured_persona(p)
        await session.commit()


@pytest.fixture
def v1_markdown_dir(tmp_path: Path) -> Path:
    """Create a v1 markdown persona on disk."""
    boss = tmp_path / "boss.md"
    boss.write_text(
        """---
name: 老板
role: CEO
avatar_color: "#FF0000"
---

# 老板

经典 v1 markdown persona。
""",
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# AC5: v1 persona.full_content 非空; v2 persona.structured_profile 非空
# ---------------------------------------------------------------------------


def test_v1_persona_returns_full_content(v1_markdown_dir: Path) -> None:
    """v1 persona 走 markdown parser，full_content 非空。"""
    loader = PersonaLoader(persona_dir=str(v1_markdown_dir))
    persona = loader.get_persona("boss")
    assert persona is not None
    assert persona.schema_version == 1
    assert persona.full_content != ""
    assert "老板" in persona.full_content


@pytest.mark.asyncio
async def test_v2_persona_returns_structured_profile(
    session_factory, tmp_path: Path
) -> None:
    """v2 persona 走 DB，5 层 structured 字段非空。"""
    await _seed_v2_persona(session_factory)

    # Use empty markdown dir
    loader = PersonaLoader(persona_dir=str(tmp_path))
    async with session_factory() as session:
        repo = SQLAlchemyStakeholderPersonaRepository(session)
        await loader.refresh_from_db(repo)

    persona = loader.get_persona("cfo")
    assert persona is not None
    assert persona.schema_version == 2
    assert persona.identity is not None
    assert persona.identity.background == "CPA"
    assert persona.expression is not None
    assert persona.expression.tone == "严谨"


# ---------------------------------------------------------------------------
# AC7: PersonaLoader 在 schema_version=2 时跳过 markdown 扫描走 DB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v2_only_skips_markdown_scan(
    session_factory, tmp_path: Path
) -> None:
    """空 markdown 目录下仍可返回 v2 persona。"""
    await _seed_v2_persona(session_factory, "boss")

    # Empty markdown dir
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    loader = PersonaLoader(persona_dir=str(empty_dir))
    async with session_factory() as session:
        repo = SQLAlchemyStakeholderPersonaRepository(session)
        await loader.refresh_from_db(repo)

    personas = loader.list_personas()
    assert len(personas) == 1
    assert personas[0].id == "boss"
    assert personas[0].schema_version == 2


@pytest.mark.asyncio
async def test_v1_v2_merge_v2_wins_on_conflict(
    session_factory, v1_markdown_dir: Path
) -> None:
    """v1 markdown + v2 DB 合并时，同 id 冲突 v2 优先。"""
    # v1 markdown 目录里有 boss.md
    # DB 里也有 id=boss 的 v2 persona
    await _seed_v2_persona(session_factory, "boss")

    loader = PersonaLoader(persona_dir=str(v1_markdown_dir))
    async with session_factory() as session:
        repo = SQLAlchemyStakeholderPersonaRepository(session)
        await loader.refresh_from_db(repo)

    persona = loader.get_persona("boss")
    assert persona is not None
    assert persona.schema_version == 2  # v2 wins
    assert persona.identity is not None  # v2 结构化字段存在


def test_v1_only_still_works_without_repo(v1_markdown_dir: Path) -> None:
    """不注入 repo 时 PersonaLoader 完全走 markdown-only 路径 (向后兼容)。"""
    loader = PersonaLoader(persona_dir=str(v1_markdown_dir))
    personas = loader.list_personas()
    assert len(personas) == 1
    assert personas[0].id == "boss"
    assert personas[0].schema_version == 1
