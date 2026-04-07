#!/usr/bin/env python3
"""Validate .po files syntax using polib.

Exit non-zero if any .po cannot be parsed.
"""
from __future__ import annotations

import sys
from pathlib import Path
import re

try:
    import polib  # type: ignore
except Exception as exc:  # pragma: no cover
    print("polib not installed; install it to validate .po files", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    po_files = list((root / "locales").glob("*/LC_MESSAGES/*.po"))
    if not po_files:
        return 0
    errors: list[str] = []

    # 1) Syntax validation
    for f in po_files:
        try:
            polib.pofile(str(f))
        except Exception as exc:  # pragma: no cover
            errors.append(f"{f}: {exc}")
    if errors:
        print("PO syntax errors detected:\n" + "\n".join(errors), file=sys.stderr)
        return 1

    # 2) Coverage check: collect used keys from codebase
    src_root = root
    used_keys: set[str] = set()
    key_re = re.compile(r"t\(\s*['\"]([a-zA-Z0-9_.]+)['\"]")
    msgkey_re = re.compile(r"message_key\s*=\s*['\"]([a-zA-Z0-9_.]+)['\"]")

    def scan_file(p: Path) -> None:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return
        for m in key_re.finditer(text):
            used_keys.add(m.group(1))
        for m in msgkey_re.finditer(text):
            used_keys.add(m.group(1))

    exclude_dirs = {".git", "venv", ".venv", "alembic", "locales", "grpc_app/generated"}
    for p in src_root.rglob("*.py"):
        if any(part in exclude_dirs for part in p.parts):
            continue
        scan_file(p)

    # 3) Validate each language file has all used keys translated (non-empty msgstr)
    missing_total = 0
    untranslated_total = 0
    for f in po_files:
        po = polib.pofile(str(f))
        keys_in_po = {e.msgid for e in po}
        # missing keys
        missing = sorted(used_keys - keys_in_po)
        # untranslated keys
        untranslated = sorted([e.msgid for e in po if not (e.msgstr or "").strip()])
        if missing:
            print(f"[i18n] Missing keys in {f}: {len(missing)}", file=sys.stderr)
            print(
                "  " + ", ".join(missing[:20]) + (" ..." if len(missing) > 20 else ""),
                file=sys.stderr,
            )
        if untranslated:
            print(f"[i18n] Untranslated keys in {f}: {len(untranslated)}", file=sys.stderr)
            print(
                "  " + ", ".join(untranslated[:20]) + (" ..." if len(untranslated) > 20 else ""),
                file=sys.stderr,
            )
        missing_total += len(missing)
        untranslated_total += len(untranslated)

        # info: extra keys (not used in code)
        extras = sorted(keys_in_po - used_keys)
        if extras:
            print(f"[i18n] Extra keys in {f}: {len(extras)} (info)")

    if missing_total or untranslated_total:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
