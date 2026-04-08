# input: PersonaLoader, persona_dir path
# output: PersonaEditorService — create/update/delete persona .md files
# owner: wanhua.gu
# pos: 应用层服务 - Persona Markdown 文件 CRUD 编辑器；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""PersonaEditorService: CRUD operations on persona Markdown files."""

from __future__ import annotations

from pathlib import Path

from core.logging_config import get_logger

from .dto import CreatePersonaDTO, UpdatePersonaDTO
from .persona_loader import PersonaLoader

logger = get_logger(__name__)


class PersonaEditorService:
    """Create, update, and delete persona Markdown files."""

    def __init__(self, persona_dir: str, persona_loader: PersonaLoader) -> None:
        self._persona_dir = Path(persona_dir)
        self._loader = persona_loader

    def _persona_path(self, persona_id: str) -> Path:
        path = (self._persona_dir / f"{persona_id}.md").resolve()
        if not path.is_relative_to(self._persona_dir.resolve()):
            raise ValueError(f"Invalid persona id: {persona_id}")
        return path

    @staticmethod
    def _build_markdown(
        name: str,
        role: str,
        avatar_color: str,
        content: str,
        *,
        organization_id: int | None = None,
        team_id: int | None = None,
        extra_frontmatter: dict | None = None,
    ) -> str:
        """Build a persona Markdown file with YAML frontmatter."""
        lines = [
            "---",
            f"name: {name}",
            f"role: {role}",
            f'avatar_color: "{avatar_color}"',
        ]
        if organization_id is not None:
            lines.append(f"organization_id: {organization_id}")
        if team_id is not None:
            lines.append(f"team_id: {team_id}")
        # Preserve any extra frontmatter keys (e.g. last_updated, confidence)
        if extra_frontmatter:
            for key, value in extra_frontmatter.items():
                if key not in ("name", "role", "avatar_color", "organization_id", "team_id"):
                    lines.append(f"{key}: {value}")
        lines.extend(["---", "", content])
        return "\n".join(lines)

    def create_persona(self, dto: CreatePersonaDTO) -> None:
        """Create a new persona Markdown file."""
        path = self._persona_path(dto.id)
        if path.exists():
            raise FileExistsError(f"Persona '{dto.id}' already exists")

        self._persona_dir.mkdir(parents=True, exist_ok=True)
        md = self._build_markdown(
            dto.name,
            dto.role,
            dto.avatar_color,
            dto.content,
            organization_id=dto.organization_id,
            team_id=dto.team_id,
        )
        path.write_text(md, encoding="utf-8")
        logger.info("persona_created", persona_id=dto.id)
        self._loader.reload()

    def update_persona(self, persona_id: str, dto: UpdatePersonaDTO) -> None:
        """Update an existing persona Markdown file (partial update)."""
        path = self._persona_path(persona_id)
        if not path.exists():
            raise FileNotFoundError(f"Persona '{persona_id}' not found")

        # Read and parse existing file
        existing_content = path.read_text(encoding="utf-8")
        frontmatter = self._loader._extract_frontmatter(existing_content)
        body = self._loader._strip_frontmatter(existing_content)

        # Merge changes
        name = dto.name if dto.name is not None else frontmatter.get("name", persona_id)
        role = dto.role if dto.role is not None else frontmatter.get("role", "")
        avatar_color = (
            dto.avatar_color
            if dto.avatar_color is not None
            else frontmatter.get("avatar_color", "#888888")
        )
        content = dto.content if dto.content is not None else body

        # Merge org/team: use DTO value if provided, else keep existing
        org_id = (
            dto.organization_id
            if dto.organization_id is not None
            else PersonaLoader._parse_optional_int(frontmatter.get("organization_id"))
        )
        t_id = (
            dto.team_id
            if dto.team_id is not None
            else PersonaLoader._parse_optional_int(frontmatter.get("team_id"))
        )

        # Collect extra frontmatter keys to preserve (e.g. last_updated, confidence)
        managed_keys = {"name", "role", "avatar_color", "organization_id", "team_id"}
        extra_fm = {k: v for k, v in frontmatter.items() if k not in managed_keys}

        md = self._build_markdown(
            name,
            role,
            avatar_color,
            content,
            organization_id=org_id,
            team_id=t_id,
            extra_frontmatter=extra_fm,
        )
        path.write_text(md, encoding="utf-8")
        logger.info("persona_updated", persona_id=persona_id)
        self._loader.reload()

    def delete_persona(self, persona_id: str) -> None:
        """Delete a persona Markdown file."""
        path = self._persona_path(persona_id)
        if not path.exists():
            raise FileNotFoundError(f"Persona '{persona_id}' not found")

        path.unlink()
        logger.info("persona_deleted", persona_id=persona_id)
        self._loader.reload()
