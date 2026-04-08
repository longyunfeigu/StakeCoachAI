# input: SQLAlchemy AsyncSession, OrganizationModel/TeamModel/PersonaRelationshipModel ORM
# output: SQLAlchemyOrganizationRepository, SQLAlchemyTeamRepository, SQLAlchemyPersonaRelationshipRepository 仓储实现
# owner: wanhua.gu
# pos: 基础设施层 - 组织上下文仓储 SQLAlchemy 实现；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""SQLAlchemy-backed repositories for organization context aggregate."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domain.stakeholder.organization_entity import Organization, PersonaRelationship, Team
from domain.stakeholder.repository import (
    OrganizationRepository,
    PersonaRelationshipRepository,
    TeamRepository,
)
from infrastructure.models.organization import (
    OrganizationModel,
    PersonaRelationshipModel,
    TeamModel,
)


class SQLAlchemyOrganizationRepository(OrganizationRepository):
    """Persist organizations using SQLAlchemy ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: OrganizationModel) -> Organization:
        return Organization(
            id=model.id,
            name=model.name,
            industry=model.industry or "",
            description=model.description or "",
            context_prompt=model.context_prompt or "",
            created_at=model.created_at,
        )

    async def create(self, org: Organization) -> Organization:
        model = OrganizationModel(
            name=org.name,
            industry=org.industry,
            description=org.description,
            context_prompt=org.context_prompt,
            created_at=org.created_at,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, org_id: int) -> Optional[Organization]:
        result = await self.session.execute(
            select(OrganizationModel).where(OrganizationModel.id == org_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_all(self, *, skip: int = 0, limit: int = 50) -> list[Organization]:
        query = (
            select(OrganizationModel)
            .order_by(OrganizationModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, org: Organization) -> Organization:
        stmt = (
            update(OrganizationModel)
            .where(OrganizationModel.id == org.id)
            .values(
                name=org.name,
                industry=org.industry,
                description=org.description,
                context_prompt=org.context_prompt,
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_by_id(org.id)  # type: ignore[return-value]

    async def delete(self, org_id: int) -> bool:
        result = await self.session.execute(
            delete(OrganizationModel).where(OrganizationModel.id == org_id)
        )
        await self.session.flush()
        return result.rowcount > 0


class SQLAlchemyTeamRepository(TeamRepository):
    """Persist teams using SQLAlchemy ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: TeamModel) -> Team:
        return Team(
            id=model.id,
            organization_id=model.organization_id,
            name=model.name,
            description=model.description or "",
            created_at=model.created_at,
        )

    async def create(self, team: Team) -> Team:
        model = TeamModel(
            organization_id=team.organization_id,
            name=team.name,
            description=team.description,
            created_at=team.created_at,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, team_id: int) -> Optional[Team]:
        result = await self.session.execute(select(TeamModel).where(TeamModel.id == team_id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_organization(self, org_id: int) -> list[Team]:
        query = (
            select(TeamModel)
            .where(TeamModel.organization_id == org_id)
            .order_by(TeamModel.created_at.asc())
        )
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, team: Team) -> Team:
        stmt = (
            update(TeamModel)
            .where(TeamModel.id == team.id)
            .values(name=team.name, description=team.description)
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_by_id(team.id)  # type: ignore[return-value]

    async def delete(self, team_id: int) -> bool:
        result = await self.session.execute(delete(TeamModel).where(TeamModel.id == team_id))
        await self.session.flush()
        return result.rowcount > 0


class SQLAlchemyPersonaRelationshipRepository(PersonaRelationshipRepository):
    """Persist persona relationships using SQLAlchemy ORM."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: PersonaRelationshipModel) -> PersonaRelationship:
        return PersonaRelationship(
            id=model.id,
            organization_id=model.organization_id,
            from_persona_id=model.from_persona_id,
            to_persona_id=model.to_persona_id,
            relationship_type=model.relationship_type,
            description=model.description or "",
            created_at=model.created_at,
        )

    async def create(self, rel: PersonaRelationship) -> PersonaRelationship:
        model = PersonaRelationshipModel(
            organization_id=rel.organization_id,
            from_persona_id=rel.from_persona_id,
            to_persona_id=rel.to_persona_id,
            relationship_type=rel.relationship_type,
            description=rel.description,
            created_at=rel.created_at,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, rel_id: int) -> Optional[PersonaRelationship]:
        result = await self.session.execute(
            select(PersonaRelationshipModel).where(PersonaRelationshipModel.id == rel_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_organization(self, org_id: int) -> list[PersonaRelationship]:
        query = (
            select(PersonaRelationshipModel)
            .where(PersonaRelationshipModel.organization_id == org_id)
            .order_by(PersonaRelationshipModel.created_at.asc())
        )
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_by_persona(self, org_id: int, persona_id: str) -> list[PersonaRelationship]:
        query = (
            select(PersonaRelationshipModel)
            .where(
                PersonaRelationshipModel.organization_id == org_id,
                (PersonaRelationshipModel.from_persona_id == persona_id)
                | (PersonaRelationshipModel.to_persona_id == persona_id),
            )
            .order_by(PersonaRelationshipModel.created_at.asc())
        )
        result = await self.session.execute(query)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, rel: PersonaRelationship) -> PersonaRelationship:
        stmt = (
            update(PersonaRelationshipModel)
            .where(PersonaRelationshipModel.id == rel.id)
            .values(
                relationship_type=rel.relationship_type,
                description=rel.description,
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_by_id(rel.id)  # type: ignore[return-value]

    async def delete(self, rel_id: int) -> bool:
        result = await self.session.execute(
            delete(PersonaRelationshipModel).where(PersonaRelationshipModel.id == rel_id)
        )
        await self.session.flush()
        return result.rowcount > 0
