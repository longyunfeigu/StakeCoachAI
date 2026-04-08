# input: AbstractUnitOfWork
# output: OrganizationService CRUD 服务
# owner: wanhua.gu
# pos: 应用层服务 - 组织/团队/角色关系 CRUD；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Application service for organization, team, and persona relationship management."""

from __future__ import annotations

from typing import Callable

from application.services.stakeholder.dto import (
    CreateOrganizationDTO,
    CreateRelationshipDTO,
    CreateTeamDTO,
    OrganizationDTO,
    OrganizationDetailDTO,
    RelationshipDTO,
    TeamDTO,
    UpdateOrganizationDTO,
    UpdateRelationshipDTO,
    UpdateTeamDTO,
)
from domain.common.exceptions import BusinessException
from domain.common.unit_of_work import AbstractUnitOfWork
from domain.stakeholder.organization_entity import Organization, PersonaRelationship, Team
from shared.codes import BusinessCode


class OrganizationService:
    """CRUD operations for organizations, teams, and persona relationships."""

    def __init__(self, uow_factory: Callable[..., AbstractUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    # ---- Organization CRUD ----

    async def create_organization(self, dto: CreateOrganizationDTO) -> OrganizationDTO:
        async with self._uow_factory() as uow:
            org = Organization(
                id=None,
                name=dto.name,
                industry=dto.industry,
                description=dto.description,
                context_prompt=dto.context_prompt,
            )
            created = await uow.organization_repository.create(org)
            return OrganizationDTO.model_validate(created)

    async def get_organization(self, org_id: int) -> OrganizationDetailDTO:
        async with self._uow_factory(readonly=True) as uow:
            org = await uow.organization_repository.get_by_id(org_id)
            if not org:
                raise BusinessException(BusinessCode.NOT_FOUND, "Organization not found")
            teams = await uow.team_repository.list_by_organization(org_id)
            return OrganizationDetailDTO(
                organization=OrganizationDTO.model_validate(org),
                teams=[TeamDTO.model_validate(t) for t in teams],
            )

    async def list_organizations(self) -> list[OrganizationDTO]:
        async with self._uow_factory(readonly=True) as uow:
            orgs = await uow.organization_repository.list_all()
            return [OrganizationDTO.model_validate(o) for o in orgs]

    async def update_organization(self, org_id: int, dto: UpdateOrganizationDTO) -> OrganizationDTO:
        async with self._uow_factory() as uow:
            org = await uow.organization_repository.get_by_id(org_id)
            if not org:
                raise BusinessException(BusinessCode.NOT_FOUND, "Organization not found")
            if dto.name is not None:
                org.name = dto.name
            if dto.industry is not None:
                org.industry = dto.industry
            if dto.description is not None:
                org.description = dto.description
            if dto.context_prompt is not None:
                org.context_prompt = dto.context_prompt
            updated = await uow.organization_repository.update(org)
            return OrganizationDTO.model_validate(updated)

    async def delete_organization(self, org_id: int) -> None:
        async with self._uow_factory() as uow:
            deleted = await uow.organization_repository.delete(org_id)
            if not deleted:
                raise BusinessException(BusinessCode.NOT_FOUND, "Organization not found")

    # ---- Team CRUD ----

    async def create_team(self, org_id: int, dto: CreateTeamDTO) -> TeamDTO:
        async with self._uow_factory() as uow:
            org = await uow.organization_repository.get_by_id(org_id)
            if not org:
                raise BusinessException(BusinessCode.NOT_FOUND, "Organization not found")
            team = Team(
                id=None,
                organization_id=org_id,
                name=dto.name,
                description=dto.description,
            )
            created = await uow.team_repository.create(team)
            return TeamDTO.model_validate(created)

    async def list_teams(self, org_id: int) -> list[TeamDTO]:
        async with self._uow_factory(readonly=True) as uow:
            teams = await uow.team_repository.list_by_organization(org_id)
            return [TeamDTO.model_validate(t) for t in teams]

    async def update_team(self, org_id: int, team_id: int, dto: UpdateTeamDTO) -> TeamDTO:
        async with self._uow_factory() as uow:
            team = await uow.team_repository.get_by_id(team_id)
            if not team or team.organization_id != org_id:
                raise BusinessException(BusinessCode.NOT_FOUND, "Team not found")
            if dto.name is not None:
                team.name = dto.name
            if dto.description is not None:
                team.description = dto.description
            updated = await uow.team_repository.update(team)
            return TeamDTO.model_validate(updated)

    async def delete_team(self, org_id: int, team_id: int) -> None:
        async with self._uow_factory() as uow:
            team = await uow.team_repository.get_by_id(team_id)
            if not team or team.organization_id != org_id:
                raise BusinessException(BusinessCode.NOT_FOUND, "Team not found")
            await uow.team_repository.delete(team_id)

    # ---- Persona Relationship CRUD ----

    async def create_relationship(self, org_id: int, dto: CreateRelationshipDTO) -> RelationshipDTO:
        async with self._uow_factory() as uow:
            org = await uow.organization_repository.get_by_id(org_id)
            if not org:
                raise BusinessException(BusinessCode.NOT_FOUND, "Organization not found")
            rel = PersonaRelationship(
                id=None,
                organization_id=org_id,
                from_persona_id=dto.from_persona_id,
                to_persona_id=dto.to_persona_id,
                relationship_type=dto.relationship_type,
                description=dto.description,
            )
            created = await uow.persona_relationship_repository.create(rel)
            return RelationshipDTO.model_validate(created)

    async def list_relationships(self, org_id: int) -> list[RelationshipDTO]:
        async with self._uow_factory(readonly=True) as uow:
            rels = await uow.persona_relationship_repository.list_by_organization(org_id)
            return [RelationshipDTO.model_validate(r) for r in rels]

    async def update_relationship(
        self, org_id: int, rel_id: int, dto: UpdateRelationshipDTO
    ) -> RelationshipDTO:
        async with self._uow_factory() as uow:
            rel = await uow.persona_relationship_repository.get_by_id(rel_id)
            if not rel or rel.organization_id != org_id:
                raise BusinessException(BusinessCode.NOT_FOUND, "Relationship not found")
            if dto.relationship_type is not None:
                rel.relationship_type = dto.relationship_type
            if dto.description is not None:
                rel.description = dto.description
            updated = await uow.persona_relationship_repository.update(rel)
            return RelationshipDTO.model_validate(updated)

    async def delete_relationship(self, org_id: int, rel_id: int) -> None:
        async with self._uow_factory() as uow:
            rel = await uow.persona_relationship_repository.get_by_id(rel_id)
            if not rel or rel.organization_id != org_id:
                raise BusinessException(BusinessCode.NOT_FOUND, "Relationship not found")
            await uow.persona_relationship_repository.delete(rel_id)
