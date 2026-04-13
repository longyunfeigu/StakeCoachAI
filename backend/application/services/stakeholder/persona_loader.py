# input: Markdown 画像文件目录 (persona_dir) + 可选 StakeholderPersonaRepository (v2 DB 路径), TTL 缓存配置
# output: PersonaLoader 服务（含 TTL 缓存 + v1/v2 双路径）, Persona 数据结构 re-export 自 domain.stakeholder.persona_entity (向后兼容)
# owner: wanhua.gu
# pos: 应用层 - 利益相关者画像加载（v1 markdown 扫描 + v2 DB 合并，v2 优先）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""PersonaLoader: scan and parse stakeholder persona Markdown files (v1) + merge structured v2 from DB."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from core.logging_config import get_logger
from domain.stakeholder.persona_entity import Persona  # re-export for backward compatibility
from domain.stakeholder.repository import StakeholderPersonaRepository

logger = get_logger(__name__)

# Default cache TTL in seconds (persona files rarely change mid-request)
_DEFAULT_CACHE_TTL = 30.0


__all__ = ["Persona", "PersonaLoader"]


class PersonaLoader:
    """Load personas from markdown files (v1) and optionally DB (v2).

    Story 2.2 扩展:
    - 构造时不传 repository → 完全走 v1 markdown 路径 (向后兼容)
    - 调用 ``await loader.refresh_from_db(repository)`` 后，v2 persona 从 DB 合并进缓存
    - 同 id 冲突时 v2 优先
    """

    def __init__(self, persona_dir: str, *, cache_ttl: float = _DEFAULT_CACHE_TTL) -> None:
        self._persona_dir = Path(persona_dir)
        self._cache_ttl = cache_ttl
        self._cached_personas: list[Persona] | None = None
        self._cached_by_id: dict[str, Persona] | None = None
        self._cached_by_name: dict[str, str] | None = None  # name → id
        self._cache_time: float = 0.0
        self._v2_by_id: dict[str, Persona] = {}  # populated by refresh_from_db

    def reload(self) -> None:
        """Invalidate cache so next access re-reads from disk. Does not clear v2 cache."""
        self._cached_personas = None
        self._cached_by_id = None
        self._cached_by_name = None
        self._cache_time = 0.0

    async def refresh_from_db(self, repository: StakeholderPersonaRepository) -> None:
        """Pull personas from DB into cache.

        Story 2.2 AC5/AC7:
        - DB personas 在后续 ``get_persona``/``list_personas`` 中优先于 v1 markdown
        - 调用方（API dependency）可在每个请求前刷新
        """
        v2_list = await repository.list_all()
        self._v2_by_id = {p.id: p for p in v2_list}
        # Invalidate derived caches so next list/get sees merged view
        self._cached_personas = None
        self._cached_by_id = None
        self._cached_by_name = None

    def _is_cache_valid(self) -> bool:
        return (
            self._cached_personas is not None
            and (time.monotonic() - self._cache_time) < self._cache_ttl
        )

    def _refresh_cache(self) -> list[Persona]:
        if self._is_cache_valid():
            return self._cached_personas  # type: ignore[return-value]

        # First load v1 markdown (may be empty if dir missing)
        v1_personas: list[Persona] = []
        if self._persona_dir.exists():
            for md_file in sorted(self._persona_dir.glob("*.md")):
                persona = self._parse_file(md_file)
                if persona:
                    v1_personas.append(persona)
        else:
            logger.warning("persona_dir_not_found", path=str(self._persona_dir))

        # Merge v2 over v1: v2 wins on same id
        merged_by_id: dict[str, Persona] = {p.id: p for p in v1_personas}
        for pid, v2_persona in self._v2_by_id.items():
            merged_by_id[pid] = v2_persona

        personas = sorted(merged_by_id.values(), key=lambda p: p.id)
        by_id: dict[str, Persona] = dict(merged_by_id)
        by_name: dict[str, str] = {}
        for p in personas:
            by_name[p.name] = p.id
            by_name[p.id] = p.id

        self._cached_personas = personas
        self._cached_by_id = by_id
        self._cached_by_name = by_name
        self._cache_time = time.monotonic()
        return personas

    def list_personas(self) -> list[Persona]:
        """Return all personas (v1 markdown + v2 DB merged; v2 priority)."""
        return list(self._refresh_cache())

    def get_persona(self, persona_id: str) -> Optional[Persona]:
        """Get a single persona by ID. v2 takes precedence over v1 markdown."""
        # Fast path: v2 cache (AC7 — skip markdown scan if v2 matches)
        if persona_id in self._v2_by_id:
            return self._v2_by_id[persona_id]
        self._refresh_cache()
        if self._cached_by_id is not None:
            return self._cached_by_id.get(persona_id)
        return None

    def get_name_to_id_map(self) -> dict[str, str]:
        """Return a name/id → persona_id mapping (cached). Used by mention extraction."""
        self._refresh_cache()
        return dict(self._cached_by_name) if self._cached_by_name else {}

    def _parse_file(self, path: Path) -> Optional[Persona]:
        """Parse a single Markdown file into a v1 Persona."""
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.error("persona_file_read_error", path=str(path), error=str(exc))
            return None

        persona_id = path.stem
        frontmatter = self._extract_frontmatter(content)
        body = self._strip_frontmatter(content)

        name = frontmatter.get("name", "")
        role = frontmatter.get("role", "")
        avatar_color = frontmatter.get("avatar_color")
        parse_status = "ok"

        organization_id = self._parse_optional_int(frontmatter.get("organization_id"))
        team_id = self._parse_optional_int(frontmatter.get("team_id"))

        voice_id = frontmatter.get("voice_id")
        voice_speed = self._parse_optional_float(frontmatter.get("voice_speed")) or 1.0
        voice_style = frontmatter.get("voice_style")

        if not name or not role:
            parse_status = "partial"
            if not name:
                name = persona_id

        profile_summary = self._extract_summary(body)

        return Persona(
            id=persona_id,
            name=name,
            role=role,
            avatar_color=avatar_color,
            organization_id=organization_id,
            team_id=team_id,
            profile_summary=profile_summary,
            parse_status=parse_status,
            voice_id=voice_id,
            voice_speed=voice_speed,
            voice_style=voice_style,
        )

    def _extract_frontmatter(self, content: str) -> dict:
        """Extract YAML frontmatter from Markdown content."""
        if not content.startswith("---"):
            return {}

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}

        fm_text = parts[1].strip()
        result = {}
        for line in fm_text.split("\n"):
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    result[key] = value
        return result

    def _strip_frontmatter(self, content: str) -> str:
        """Remove YAML frontmatter from content."""
        if not content.startswith("---"):
            return content
        parts = content.split("---", 2)
        if len(parts) < 3:
            return content
        return parts[2].strip()

    @staticmethod
    def _parse_optional_int(value: str | None) -> int | None:
        """Parse a string value to int, returning None if invalid."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_optional_float(value: str | None) -> float | None:
        """Parse a string value to float, returning None if invalid."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _extract_summary(self, body: str) -> str:
        """Extract first ~200 chars as profile summary."""
        lines = [l.strip() for l in body.split("\n") if l.strip() and not l.startswith("#")]
        text = " ".join(lines)
        if len(text) > 200:
            return text[:200] + "..."
        return text
