# input: UoW factory → stakeholder_persona_repository
# output: PersonaV2Service.get_v2 / patch_v2 — 5-layer editor 服务 (Story 2.7)
# owner: wanhua.gu
# pos: 应用层服务 - 5-layer Persona v2 编辑器服务 (Story 2.7)；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""PersonaV2Service — backs GET/PATCH /personas/{id}/v2 (Story 2.7)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from domain.stakeholder.persona_entity import (
    DecisionPattern,
    ExpressionStyle,
    HardRule,
    IdentityProfile,
    InterpersonalStyle,
    Persona,
)

from .dto import (
    EvidenceDTO,
    PersonaPatchV2DTO,
    PersonaV2DTO,
)


class PersonaNotFoundError(Exception):
    """Raised when the target persona id does not exist in the v2 repo."""


class PersonaV2Service:
    """Application service for the 5-layer persona editor."""

    def __init__(self, uow_factory: Callable) -> None:
        self._uow_factory = uow_factory

    async def get_v2(self, persona_id: str) -> PersonaV2DTO:
        async with self._uow_factory() as uow:
            result = await uow.stakeholder_persona_repository.get_with_evidence(
                persona_id
            )
            if result is None:
                raise PersonaNotFoundError(persona_id)
            persona, evidence = result
            return _to_dto(persona, evidence)

    async def patch_v2(
        self, persona_id: str, patch: PersonaPatchV2DTO
    ) -> PersonaV2DTO:
        async with self._uow_factory() as uow:
            result = await uow.stakeholder_persona_repository.get_with_evidence(
                persona_id
            )
            if result is None:
                raise PersonaNotFoundError(persona_id)
            persona, evidence = result
            _apply_patch(persona, patch)
            saved = await uow.stakeholder_persona_repository.save_structured_persona(
                persona
            )
            await uow.commit()
            # evidence is unaffected by PATCH (read-only per design)
            return _to_dto(saved, evidence)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _apply_patch(persona: Persona, patch: PersonaPatchV2DTO) -> None:
    """Apply non-None fields of patch onto persona in place.

    List / object fields are **replaced** wholesale (not merged item-by-item).
    rejected_features is treated the same way — client always sends the full
    rejection map.
    """
    if patch.name is not None:
        persona.name = patch.name
    if patch.role is not None:
        persona.role = patch.role
    if patch.avatar_color is not None:
        persona.avatar_color = patch.avatar_color
    if patch.hard_rules is not None:
        persona.hard_rules = [HardRule(**r.model_dump()) for r in patch.hard_rules]
    if patch.identity is not None:
        persona.identity = IdentityProfile(**patch.identity.model_dump())
    if patch.expression is not None:
        persona.expression = ExpressionStyle(**patch.expression.model_dump())
    if patch.decision is not None:
        persona.decision = DecisionPattern(**patch.decision.model_dump())
    if patch.interpersonal is not None:
        persona.interpersonal = InterpersonalStyle(**patch.interpersonal.model_dump())
    if patch.rejected_features is not None:
        persona.rejected_features = {
            layer: list(indices) for layer, indices in patch.rejected_features.items()
        }


def _to_dto(persona: Persona, evidence: list) -> PersonaV2DTO:
    return PersonaV2DTO(
        id=persona.id,
        name=persona.name,
        role=persona.role,
        avatar_color=persona.avatar_color,
        hard_rules=[asdict(r) for r in persona.hard_rules],
        identity=asdict(persona.identity) if persona.identity else None,
        expression=asdict(persona.expression) if persona.expression else None,
        decision=asdict(persona.decision) if persona.decision else None,
        interpersonal=asdict(persona.interpersonal) if persona.interpersonal else None,
        evidence=[EvidenceDTO(**asdict(e)) for e in evidence],
        rejected_features=dict(persona.rejected_features),
        source_materials=list(persona.source_materials),
    )
