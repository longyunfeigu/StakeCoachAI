# input: PersonaV2Service + mock UoW
# output: Story 2.7 get_v2 / patch_v2 行为测试
# owner: wanhua.gu
# pos: 测试层 - Story 2.7 PersonaV2Service 单元测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for PersonaV2Service (Story 2.7)."""

from __future__ import annotations

import pytest

from application.services.stakeholder.dto import (
    ExpressionDTO,
    HardRuleDTO,
    PersonaPatchV2DTO,
)
from application.services.stakeholder.persona_v2_service import (
    PersonaNotFoundError,
    PersonaV2Service,
)
from domain.stakeholder.persona_entity import (
    DecisionPattern,
    Evidence,
    ExpressionStyle,
    HardRule,
    IdentityProfile,
    InterpersonalStyle,
    Persona,
)


def _make_v2_persona() -> Persona:
    return Persona(
        id="cfo",
        name="CFO",
        role="首席财务官",
        avatar_color="#123456",
        hard_rules=[HardRule(statement="预算超支必报", severity="critical")],
        identity=IdentityProfile(background="会计师", core_values=["成本"]),
        expression=ExpressionStyle(tone="严谨", catchphrases=["数字会说话"]),
        decision=DecisionPattern(style="保守", risk_tolerance="low"),
        interpersonal=InterpersonalStyle(authority_mode="正式"),
        evidence_citations=[
            Evidence(
                claim="严谨",
                citations=["「请按会计准则」"],
                confidence=0.9,
                source_material_id="mat-1",
                layer="expression",
            )
        ],
        source_materials=["mat-1"],
    )


class _FakeRepo:
    def __init__(self, persona: Persona | None) -> None:
        self._persona = persona
        self.saved: list[Persona] = []

    async def get_with_evidence(self, persona_id: str):
        if self._persona is None or self._persona.id != persona_id:
            return None
        return self._persona, list(self._persona.evidence_citations)

    async def save_structured_persona(self, persona: Persona) -> Persona:
        self.saved.append(persona)
        return persona


class _FakeUoW:
    def __init__(self, repo: _FakeRepo) -> None:
        self.stakeholder_persona_repository = repo
        self.committed = False

    async def __aenter__(self) -> "_FakeUoW":
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def _uow_factory_for(persona: Persona | None):
    repo = _FakeRepo(persona)

    def factory() -> _FakeUoW:
        return _FakeUoW(repo)

    return factory, repo


@pytest.mark.asyncio
async def test_get_v2_returns_full_dto() -> None:
    persona = _make_v2_persona()
    factory, _ = _uow_factory_for(persona)
    svc = PersonaV2Service(factory)

    dto = await svc.get_v2("cfo")

    assert dto.id == "cfo"
    assert dto.identity is not None and dto.identity.background == "会计师"
    assert len(dto.hard_rules) == 1
    assert dto.hard_rules[0].statement == "预算超支必报"
    assert len(dto.evidence) == 1
    assert dto.evidence[0].confidence == 0.9
    assert dto.source_materials == ["mat-1"]


@pytest.mark.asyncio
async def test_get_v2_not_found() -> None:
    factory, _ = _uow_factory_for(None)
    svc = PersonaV2Service(factory)
    with pytest.raises(PersonaNotFoundError):
        await svc.get_v2("missing")


@pytest.mark.asyncio
async def test_patch_v2_partial_update() -> None:
    persona = _make_v2_persona()
    factory, repo = _uow_factory_for(persona)
    svc = PersonaV2Service(factory)

    patch = PersonaPatchV2DTO(
        name="CFO Updated",
        hard_rules=[HardRuleDTO(statement="新规则", severity="high")],
        rejected_features={"expression": [0]},
    )
    dto = await svc.patch_v2("cfo", patch)

    assert dto.name == "CFO Updated"
    assert dto.role == "首席财务官"  # untouched
    assert len(dto.hard_rules) == 1 and dto.hard_rules[0].statement == "新规则"
    assert dto.rejected_features == {"expression": [0]}
    # Evidence is read-only and preserved
    assert len(dto.evidence) == 1
    # Save was called
    assert len(repo.saved) == 1


@pytest.mark.asyncio
async def test_patch_v2_expression_replaced_wholesale() -> None:
    persona = _make_v2_persona()
    factory, _ = _uow_factory_for(persona)
    svc = PersonaV2Service(factory)

    patch = PersonaPatchV2DTO(
        expression=ExpressionDTO(
            tone="活泼",
            catchphrases=["大家加油"],
            interruption_tendency="high",
        )
    )
    dto = await svc.patch_v2("cfo", patch)

    assert dto.expression is not None
    assert dto.expression.tone == "活泼"
    assert dto.expression.catchphrases == ["大家加油"]
    assert dto.expression.interruption_tendency == "high"
