"""Idempotency helpers for API boundaries."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional


def validate_idempotency_key(key: str) -> str:
    """Validate Idempotency-Key header value.

    Keeps the rules intentionally simple for a kit:
    - 8..128 chars
    - visible ASCII only
    """
    k = (key or "").strip()
    if not k:
        raise ValueError("Idempotency-Key is empty")
    if len(k) < 8 or len(k) > 128:
        raise ValueError("Idempotency-Key length must be between 8 and 128")
    for ch in k:
        o = ord(ch)
        if o < 33 or o > 126:
            raise ValueError("Idempotency-Key must be visible ASCII characters")
    return k


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def build_request_hash(
    *,
    scope: str,
    subject: str,
    body: Any,
) -> str:
    raw = canonical_json({"scope": scope, "subject": subject, "body": body})
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def pick_subject_from_request_headers(headers: dict[str, str]) -> str:
    """Pick a best-effort idempotency subject.

    Prefer authenticated identity when available; fall back to a stable anon bucket.
    """
    auth = (headers.get("authorization") or "").strip()
    if auth:
        return hashlib.sha256(auth.encode("utf-8")).hexdigest()
    return "anon"
