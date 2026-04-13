# input: SQLAlchemy AsyncSession, StakeholderPersonaModel ORM
# output: SQLAlchemyStakeholderPersonaRepository - save_structured_persona / get_by_id / get_with_evidence / list_all / save_migration_error
# owner: wanhua.gu
# pos: 基础设施层 - 利益相关者画像仓储 SQLAlchemy 实现 (Story 2.2 + 2.3 失败回写 + 2.7 rejected_features 元数据)；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""SQLAlchemy implementation of StakeholderPersonaRepository (Story 2.2 + 2.3)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.stakeholder.persona_entity import (
    DecisionPattern,
    Evidence,
    ExpressionStyle,
    HardRule,
    IdentityProfile,
    InterpersonalStyle,
    Persona,
)
from domain.stakeholder.repository import StakeholderPersonaRepository
from infrastructure.models.stakeholder_persona import StakeholderPersonaModel


def _serialize_structured_profile(persona: Persona) -> Optional[dict]:
    """Serialize 5-layer fields to JSON dict. Returns None for v1 personas."""
    if persona.schema_version < 2:
        return None
    result: dict = {
        "hard_rules": [asdict(r) for r in persona.hard_rules],
        "identity": asdict(persona.identity) if persona.identity else None,
        "expression": asdict(persona.expression) if persona.expression else None,
        "decision": asdict(persona.decision) if persona.decision else None,
        "interpersonal": asdict(persona.interpersonal) if persona.interpersonal else None,
    }
    # Story 2.7: rejected_features lives in _metadata to avoid DB schema churn.
    if persona.rejected_features:
        result["_metadata"] = {"rejected_features": persona.rejected_features}
    return result


def _deserialize_structured_profile(data: Optional[dict]) -> dict:
    """Deserialize JSON structured_profile back to 5-layer dataclass instances."""
    if not data:
        return {
            "hard_rules": [],
            "identity": None,
            "expression": None,
            "decision": None,
            "interpersonal": None,
        }
    return {
        "hard_rules": [HardRule(**r) for r in (data.get("hard_rules") or [])],
        "identity": IdentityProfile(**data["identity"]) if data.get("identity") else None,
        "expression": ExpressionStyle(**data["expression"]) if data.get("expression") else None,
        "decision": DecisionPattern(**data["decision"]) if data.get("decision") else None,
        "interpersonal": (
            InterpersonalStyle(**data["interpersonal"]) if data.get("interpersonal") else None
        ),
    }


def _serialize_evidences(persona: Persona) -> Optional[list[dict]]:
    if not persona.evidence_citations:
        return None
    return [asdict(e) for e in persona.evidence_citations]


def _deserialize_evidences(data: Optional[list]) -> list[Evidence]:
    if not data:
        return []
    return [Evidence(**e) for e in data]


class SQLAlchemyStakeholderPersonaRepository(StakeholderPersonaRepository):
    """Persist structured stakeholder personas using SQLAlchemy ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: StakeholderPersonaModel) -> Persona:
        structured = _deserialize_structured_profile(model.structured_profile)
        # Story 2.7: recover rejected_features from _metadata if present.
        profile_dict = model.structured_profile or {}
        metadata = profile_dict.get("_metadata") if isinstance(profile_dict, dict) else None
        rejected = (metadata or {}).get("rejected_features") or {}
        return Persona(
            id=model.id,
            name=model.name,
            role=model.role,
            avatar_color=model.avatar_color,
            organization_id=model.organization_id,
            team_id=model.team_id,
            profile_summary=model.profile_summary or "",
            full_content=model.full_content or "",
            voice_id=model.voice_id,
            voice_speed=model.voice_speed if model.voice_speed is not None else 1.0,
            voice_style=model.voice_style,
            hard_rules=structured["hard_rules"],
            identity=structured["identity"],
            expression=structured["expression"],
            decision=structured["decision"],
            interpersonal=structured["interpersonal"],
            evidence_citations=_deserialize_evidences(model.evidence_citations),
            schema_version=model.schema_version,
            source_materials=list(model.source_materials or []),
            legacy_content=model.legacy_content,
            rejected_features=dict(rejected),
        )

    def _apply_to_model(self, model: StakeholderPersonaModel, persona: Persona) -> None:
        model.name = persona.name
        model.role = persona.role
        model.avatar_color = persona.avatar_color
        model.organization_id = persona.organization_id
        model.team_id = persona.team_id
        model.profile_summary = persona.profile_summary or ""
        model.full_content = persona.full_content or ""
        model.voice_id = persona.voice_id
        model.voice_speed = persona.voice_speed
        model.voice_style = persona.voice_style
        model.structured_profile = _serialize_structured_profile(persona)
        model.evidence_citations = _serialize_evidences(persona)
        model.schema_version = persona.schema_version
        model.source_materials = (
            list(persona.source_materials) if persona.source_materials else None
        )
        model.legacy_content = persona.legacy_content

    async def save_structured_persona(self, persona: Persona) -> Persona:
        existing = await self.session.get(StakeholderPersonaModel, persona.id)
        if existing is None:
            model = StakeholderPersonaModel(id=persona.id, name=persona.name, role=persona.role)
            self._apply_to_model(model, persona)
            self.session.add(model)
        else:
            self._apply_to_model(existing, persona)
            model = existing
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, persona_id: str) -> Optional[Persona]:
        model = await self.session.get(StakeholderPersonaModel, persona_id)
        return self._to_entity(model) if model else None

    async def get_with_evidence(self, persona_id: str) -> Optional[tuple[Persona, list[Evidence]]]:
        persona = await self.get_by_id(persona_id)
        if persona is None:
            return None
        return persona, list(persona.evidence_citations)

    async def list_all(self, *, schema_version: Optional[int] = None) -> list[Persona]:
        query = select(StakeholderPersonaModel)
        if schema_version is not None:
            query = query.where(StakeholderPersonaModel.schema_version == schema_version)
        query = query.order_by(StakeholderPersonaModel.id.asc())
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def save_migration_error(
        self,
        persona_id: str,
        error: str,
        *,
        legacy_markdown: Optional[str] = None,
        name: str = "",
        role: str = "",
    ) -> None:
        """Story 2.3 AC4: record a v1→v2 migration failure without touching schema_version.

        - 不存在 → 插入 schema_version=1 stub（full_content=legacy_markdown）
        - 已存在且 schema_version=2 → no-op（不会回退已迁移记录）
        - 已存在且 schema_version=1 → 仅更新 structured_profile._error，不动 full_content
        """
        existing = await self.session.get(StakeholderPersonaModel, persona_id)
        error_payload = {
            "_error": error,
            "_attempted_at": datetime.now(timezone.utc).isoformat(),
        }

        if existing is None:
            stub = StakeholderPersonaModel(
                id=persona_id,
                name=name or persona_id,
                role=role or "",
                full_content=legacy_markdown or "",
                legacy_content=legacy_markdown,
                schema_version=1,
                structured_profile=error_payload,
            )
            self.session.add(stub)
        else:
            if existing.schema_version >= 2:
                # already migrated successfully — do not regress
                return
            existing.structured_profile = error_payload
            if legacy_markdown is not None and not existing.legacy_content:
                existing.legacy_content = legacy_markdown

        await self.session.flush()
