# input: Markdown 画像文件目录 (persona_dir), TTL 缓存配置
# output: PersonaLoader 服务（含 TTL 缓存）, Persona 数据结构, get_name_to_id_map() 快速查找
# owner: wanhua.gu
# pos: 应用层 - 利益相关者画像加载与解析服务（带 30s TTL 内存缓存避免重复磁盘扫描）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""PersonaLoader: scan and parse stakeholder persona Markdown files."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.logging_config import get_logger

logger = get_logger(__name__)

# Default cache TTL in seconds (persona files rarely change mid-request)
_DEFAULT_CACHE_TTL = 30.0


@dataclass
class Persona:
    """Parsed stakeholder persona."""

    id: str
    name: str
    role: str
    avatar_color: Optional[str] = None
    profile_summary: str = ""
    full_content: str = ""
    parse_status: str = "ok"  # ok | partial


class PersonaLoader:
    """Load and parse persona Markdown files from a directory.

    Includes a TTL-based in-memory cache to avoid repeated disk scans
    within a short time window (e.g. during a single group chat round).
    """

    def __init__(self, persona_dir: str, *, cache_ttl: float = _DEFAULT_CACHE_TTL) -> None:
        self._persona_dir = Path(persona_dir)
        self._cache_ttl = cache_ttl
        self._cached_personas: list[Persona] | None = None
        self._cached_by_id: dict[str, Persona] | None = None
        self._cached_by_name: dict[str, str] | None = None  # name → id
        self._cache_time: float = 0.0

    def reload(self) -> None:
        """Invalidate cache so next access re-reads from disk."""
        self._cached_personas = None
        self._cached_by_id = None
        self._cached_by_name = None
        self._cache_time = 0.0

    def _is_cache_valid(self) -> bool:
        return (
            self._cached_personas is not None
            and (time.monotonic() - self._cache_time) < self._cache_ttl
        )

    def _refresh_cache(self) -> list[Persona]:
        if self._is_cache_valid():
            return self._cached_personas  # type: ignore[return-value]

        if not self._persona_dir.exists():
            logger.warning("persona_dir_not_found", path=str(self._persona_dir))
            self._cached_personas = []
            self._cached_by_id = {}
            self._cached_by_name = {}
            self._cache_time = time.monotonic()
            return []

        personas: list[Persona] = []
        by_id: dict[str, Persona] = {}
        by_name: dict[str, str] = {}
        for md_file in sorted(self._persona_dir.glob("*.md")):
            persona = self._parse_file(md_file)
            if persona:
                personas.append(persona)
                by_id[persona.id] = persona
                by_name[persona.name] = persona.id
                by_name[persona.id] = persona.id

        self._cached_personas = personas
        self._cached_by_id = by_id
        self._cached_by_name = by_name
        self._cache_time = time.monotonic()
        return personas

    def list_personas(self) -> list[Persona]:
        """Return all parsed personas (cached with TTL)."""
        return list(self._refresh_cache())

    def get_persona(self, persona_id: str) -> Optional[Persona]:
        """Get a single persona by ID (O(1) lookup via cache)."""
        self._refresh_cache()
        if self._cached_by_id is not None:
            return self._cached_by_id.get(persona_id)
        return None

    def get_name_to_id_map(self) -> dict[str, str]:
        """Return a name/id → persona_id mapping (cached). Used by mention extraction."""
        self._refresh_cache()
        return dict(self._cached_by_name) if self._cached_by_name else {}

    def _parse_file(self, path: Path) -> Optional[Persona]:
        """Parse a single Markdown file into a Persona."""
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
            profile_summary=profile_summary,
            full_content=content,
            parse_status=parse_status,
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

    def _extract_summary(self, body: str) -> str:
        """Extract first ~200 chars as profile summary."""
        lines = [l.strip() for l in body.split("\n") if l.strip() and not l.startswith("#")]
        text = " ".join(lines)
        if len(text) > 200:
            return text[:200] + "..."
        return text
