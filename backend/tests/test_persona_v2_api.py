# input: FastAPI minimal app + PersonaV2Service override
# output: Story 2.7 GET/PATCH /personas/{id}/v2 API 测试
# owner: wanhua.gu
# pos: 测试层 - Story 2.7 PersonaV2 API 路由测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""API tests for Story 2.7: persona v2 editor endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.dependencies import get_persona_v2_service
from api.routes.stakeholder import router
from application.services.stakeholder.dto import (
    EvidenceDTO,
    ExpressionDTO,
    HardRuleDTO,
    IdentityDTO,
    PersonaPatchV2DTO,
    PersonaV2DTO,
)
from application.services.stakeholder.persona_v2_service import (
    PersonaNotFoundError,
    PersonaNotV2Error,
)
from core.exceptions import register_exception_handlers


class _StubV2Service:
    def __init__(self) -> None:
        self._store: dict[str, PersonaV2DTO] = {
            "cfo": PersonaV2DTO(
                id="cfo",
                name="CFO",
                role="首席财务官",
                avatar_color="#123",
                schema_version=2,
                hard_rules=[HardRuleDTO(statement="预算超支必报", severity="critical")],
                identity=IdentityDTO(background="会计师", core_values=["成本"]),
                expression=ExpressionDTO(tone="严谨", catchphrases=["数字会说话"]),
                decision=None,
                interpersonal=None,
                evidence=[
                    EvidenceDTO(
                        claim="严谨",
                        citations=["「请按会计准则」"],
                        confidence=0.9,
                        source_material_id="m1",
                        layer="expression",
                    )
                ],
                rejected_features={},
                source_materials=["m1"],
            ),
        }
        self._v1_ids = {"legacy"}

    async def get_v2(self, persona_id: str) -> PersonaV2DTO:
        if persona_id not in self._store:
            raise PersonaNotFoundError(persona_id)
        return self._store[persona_id]

    async def patch_v2(self, persona_id: str, patch: PersonaPatchV2DTO) -> PersonaV2DTO:
        if persona_id in self._v1_ids:
            raise PersonaNotV2Error(persona_id)
        if persona_id not in self._store:
            raise PersonaNotFoundError(persona_id)
        existing = self._store[persona_id]
        updated = existing.model_copy(
            update={
                k: v for k, v in patch.model_dump(exclude_none=True).items()
                if k in PersonaV2DTO.model_fields
            }
        )
        # hard_rules etc. come out as dicts, convert back
        if patch.hard_rules is not None:
            updated.hard_rules = patch.hard_rules
        if patch.expression is not None:
            updated.expression = patch.expression
        if patch.identity is not None:
            updated.identity = patch.identity
        if patch.rejected_features is not None:
            updated.rejected_features = patch.rejected_features
        self._store[persona_id] = updated
        return updated


@pytest.fixture
def client():
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    stub = _StubV2Service()
    app.dependency_overrides[get_persona_v2_service] = lambda: stub

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test"), stub


@pytest.mark.asyncio
async def test_get_v2_happy(client) -> None:
    ac, _ = client
    async with ac as c:
        resp = await c.get("/api/v1/stakeholder/personas/cfo/v2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == "cfo"
        assert body["data"]["schema_version"] == 2
        assert len(body["data"]["hard_rules"]) == 1
        assert len(body["data"]["evidence"]) == 1


@pytest.mark.asyncio
async def test_get_v2_not_found(client) -> None:
    ac, _ = client
    async with ac as c:
        resp = await c.get("/api/v1/stakeholder/personas/missing/v2")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_v2_partial(client) -> None:
    ac, stub = client
    async with ac as c:
        resp = await c.patch(
            "/api/v1/stakeholder/personas/cfo/v2",
            json={
                "name": "CFO 2.0",
                "rejected_features": {"hard_rules": [0]},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["name"] == "CFO 2.0"
        assert body["data"]["rejected_features"] == {"hard_rules": [0]}
        # role untouched
        assert body["data"]["role"] == "首席财务官"


@pytest.mark.asyncio
async def test_patch_v2_rejects_v1(client) -> None:
    ac, _ = client
    async with ac as c:
        resp = await c.patch(
            "/api/v1/stakeholder/personas/legacy/v2",
            json={"name": "x"},
        )
        # Project's exception handler reshapes detail, but status code is
        # what clients act on. 409 is the v1-reject contract.
        assert resp.status_code == 409
