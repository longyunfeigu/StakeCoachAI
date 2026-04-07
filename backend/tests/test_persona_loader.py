# input: PersonaLoader, FastAPI test client
# output: Story 1.4 画像加载与 API 验收测试
# owner: wanhua.gu
# pos: 测试层 - Story 1.4 画像加载与展示验收测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Story 1.4: Persona loading + API endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from application.services.stakeholder.persona_loader import PersonaLoader


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def persona_dir(tmp_path: Path) -> Path:
    """Create a temp persona directory with sample files."""
    # Well-formed persona
    jianfeng = tmp_path / "jianfeng.md"
    jianfeng.write_text(
        """---
name: 剑锋
role: VP of Engineering
avatar_color: "#4A90D9"
---

# 剑锋

强势的技术领导者，关注架构质量和团队效率。

## 沟通风格
直接、追问细节、不容忍模糊。
""",
        encoding="utf-8",
    )

    # Another persona
    robin = tmp_path / "robin.md"
    robin.write_text(
        """---
name: Robin
role: Product Manager
avatar_color: "#E67E22"
---

# Robin

注重用户体验和业务价值，善于平衡各方需求。
""",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def malformed_dir(tmp_path: Path) -> Path:
    """Create a temp dir with a malformed persona file."""
    bad = tmp_path / "unknown_person.md"
    bad.write_text("Just some text without frontmatter\nNo name or role here.", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# AC1: PersonaLoader scans and parses
# ---------------------------------------------------------------------------


def test_persona_loader_scan_and_parse(persona_dir: Path) -> None:
    loader = PersonaLoader(persona_dir=str(persona_dir))
    personas = loader.list_personas()

    assert len(personas) == 2
    ids = {p.id for p in personas}
    assert "jianfeng" in ids
    assert "robin" in ids

    jf = next(p for p in personas if p.id == "jianfeng")
    assert jf.name == "剑锋"
    assert jf.role == "VP of Engineering"
    assert jf.avatar_color == "#4A90D9"
    assert jf.parse_status == "ok"
    assert len(jf.profile_summary) > 0
    assert len(jf.full_content) > 0


# ---------------------------------------------------------------------------
# AC2: Frontmatter extraction
# ---------------------------------------------------------------------------


def test_parse_frontmatter_fields(persona_dir: Path) -> None:
    loader = PersonaLoader(persona_dir=str(persona_dir))
    robin = loader.get_persona("robin")

    assert robin is not None
    assert robin.name == "Robin"
    assert robin.role == "Product Manager"
    assert robin.avatar_color == "#E67E22"


# ---------------------------------------------------------------------------
# AC3: Malformed persona fallback
# ---------------------------------------------------------------------------


def test_malformed_persona_fallback(malformed_dir: Path) -> None:
    loader = PersonaLoader(persona_dir=str(malformed_dir))
    personas = loader.list_personas()

    assert len(personas) == 1
    p = personas[0]
    assert p.id == "unknown_person"
    assert p.name == "unknown_person"  # Fallback to filename
    assert p.parse_status == "partial"


# ---------------------------------------------------------------------------
# AC4: Reload after update
# ---------------------------------------------------------------------------


def test_persona_reload_after_update(persona_dir: Path) -> None:
    loader = PersonaLoader(persona_dir=str(persona_dir))

    # Initial load
    personas = loader.list_personas()
    assert len(personas) == 2

    # Add a new file
    troy = persona_dir / "troy.md"
    troy.write_text(
        """---
name: Troy
role: CTO
---

# Troy
""",
        encoding="utf-8",
    )

    # Reload invalidates cache, then list picks up new file
    loader.reload()
    personas = loader.list_personas()
    assert len(personas) == 3
    assert any(p.id == "troy" for p in personas)


# ---------------------------------------------------------------------------
# AC5-8: API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def app_with_personas(persona_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """Create a FastAPI test app with persona_dir configured."""
    monkeypatch.setenv("STAKEHOLDER__PERSONA_DIR", str(persona_dir))
    # Re-import to pick up env
    from api.dependencies import get_persona_loader
    from application.services.stakeholder.persona_loader import PersonaLoader as PL

    from main import app

    # Override dependency to use test persona_dir
    app.dependency_overrides[get_persona_loader] = lambda: PL(persona_dir=str(persona_dir))
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_personas_list(app_with_personas, persona_dir: Path) -> None:
    """AC5: GET /personas returns list."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_personas), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/stakeholder/personas")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 2
    assert all("id" in p and "name" in p and "role" in p for p in data)


@pytest.mark.asyncio
async def test_api_persona_detail(app_with_personas, persona_dir: Path) -> None:
    """AC6: GET /personas/{id} returns detail with profile_summary."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_personas), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/stakeholder/personas/jianfeng")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "jianfeng"
    assert data["name"] == "剑锋"
    assert data["profile_summary"] != ""


@pytest.mark.asyncio
async def test_api_persona_not_found(app_with_personas, persona_dir: Path) -> None:
    """AC7: GET /personas/nonexistent returns 404."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_personas), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/stakeholder/personas/nonexistent")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_personas_empty_dir(tmp_path: Path) -> None:
    """AC8: Empty persona dir returns empty list, not error."""
    from api.dependencies import get_persona_loader

    from main import app

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    app.dependency_overrides[get_persona_loader] = lambda: PersonaLoader(persona_dir=str(empty_dir))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/stakeholder/personas")

        assert resp.status_code == 200
        assert resp.json()["data"] == []
    finally:
        app.dependency_overrides.clear()
