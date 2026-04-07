"""HTTP header helpers for content disposition and filenames."""

from __future__ import annotations

from typing import Optional


def sanitize_filename(filename: Optional[str], fallback: str) -> str:
    """Sanitize a filename for use in Content-Disposition.

    Removes CR/LF and quotes, trims spaces. Falls back to provided
    default when result is empty.
    """
    if not filename:
        return fallback
    cleaned = filename.replace("\r", " ").replace("\n", " ").strip()
    cleaned = cleaned.replace('"', "")
    return cleaned or fallback


def build_content_disposition(mode: str, filename: str) -> str:
    """Build a Content-Disposition header value.

    Args:
        mode: "inline" or "attachment"
        filename: suggested filename
    """
    safe = sanitize_filename(filename, filename or "file")
    return f'{mode}; filename="{safe}"'
