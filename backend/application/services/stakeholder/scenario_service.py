# input: AbstractUnitOfWork, Scenario DTOs
# output: ScenarioApplicationService 场景 CRUD 用例编排
# owner: wanhua.gu
# pos: 应用层服务 - 场景模板创建/查询/更新/删除用例编排；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Application service for scenario template CRUD."""

from __future__ import annotations

from typing import Callable

from application.services.stakeholder.dto import (
    CreateScenarioDTO,
    ScenarioDTO,
    UpdateScenarioDTO,
)
from domain.common.exceptions import BusinessException
from domain.common.unit_of_work import AbstractUnitOfWork
from domain.stakeholder.scenario_entity import Scenario
from shared.codes import BusinessCode


class ScenarioApplicationService:
    """Orchestrates scenario template CRUD operations."""

    def __init__(self, uow_factory: Callable[..., AbstractUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def create_scenario(self, dto: CreateScenarioDTO) -> ScenarioDTO:
        scenario = Scenario(
            id=None,
            name=dto.name,
            description=dto.description,
            context_prompt=dto.context_prompt,
            suggested_persona_ids=dto.suggested_persona_ids,
        )
        async with self._uow_factory() as uow:
            created = await uow.scenario_repository.create(scenario)
            return ScenarioDTO.model_validate(created)

    async def list_scenarios(self, *, skip: int = 0, limit: int = 50) -> list[ScenarioDTO]:
        async with self._uow_factory(readonly=True) as uow:
            scenarios = await uow.scenario_repository.list_all(skip=skip, limit=limit)
            return [ScenarioDTO.model_validate(s) for s in scenarios]

    async def get_scenario(self, scenario_id: int) -> ScenarioDTO:
        async with self._uow_factory(readonly=True) as uow:
            scenario = await uow.scenario_repository.get_by_id(scenario_id)
            if scenario is None:
                raise BusinessException(
                    code=BusinessCode.SCENARIO_NOT_FOUND,
                    message=f"Scenario {scenario_id} not found",
                    error_type="ScenarioNotFound",
                    details={"scenario_id": scenario_id},
                )
            return ScenarioDTO.model_validate(scenario)

    async def update_scenario(self, scenario_id: int, dto: UpdateScenarioDTO) -> ScenarioDTO:
        async with self._uow_factory() as uow:
            existing = await uow.scenario_repository.get_by_id(scenario_id)
            if existing is None:
                raise BusinessException(
                    code=BusinessCode.SCENARIO_NOT_FOUND,
                    message=f"Scenario {scenario_id} not found",
                    error_type="ScenarioNotFound",
                    details={"scenario_id": scenario_id},
                )
            if dto.name is not None:
                existing.name = dto.name
            if dto.description is not None:
                existing.description = dto.description
            if dto.context_prompt is not None:
                existing.context_prompt = dto.context_prompt
            if dto.suggested_persona_ids is not None:
                existing.suggested_persona_ids = dto.suggested_persona_ids
            updated = await uow.scenario_repository.update(existing)
            return ScenarioDTO.model_validate(updated)

    async def delete_scenario(self, scenario_id: int) -> bool:
        async with self._uow_factory() as uow:
            return await uow.scenario_repository.delete(scenario_id)
