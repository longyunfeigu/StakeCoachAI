from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional


H_ATTEMPTS = "x-attempts"
H_ORIGINAL_TOPIC = "x-original-topic"
H_RETRY_NOT_BEFORE = "x-retry-not-before"
H_CORR_ID = "x-corr-id"
H_TRACEPARENT = "traceparent"
H_BAGGAGE = "baggage"
H_VERSION = "x-version"
H_SCHEMA = "x-schema"
H_ERROR_CLASS = "x-error-class"
H_ERROR_MSG = "x-error-msg"


def _to_bytes_int(n: int) -> bytes:
    return str(n).encode("ascii")


def _to_int(b: Optional[bytes]) -> Optional[int]:
    if b is None:
        return None
    try:
        return int(b.decode("ascii"))
    except Exception:
        return None


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def get_header(headers: Dict[str, bytes], key: str) -> Optional[bytes]:
    return headers.get(key)


def set_header(headers: Dict[str, bytes], key: str, value: bytes) -> None:
    headers[key] = value


def get_attempts(headers: Dict[str, bytes]) -> int:
    v = headers.get(H_ATTEMPTS)
    return _to_int(v) or 0


def bump_attempts(headers: Dict[str, bytes]) -> int:
    n = get_attempts(headers) + 1
    headers[H_ATTEMPTS] = _to_bytes_int(n)
    return n


def get_not_before_ms(headers: Dict[str, bytes]) -> Optional[int]:
    return _to_int(headers.get(H_RETRY_NOT_BEFORE))


def set_not_before_ms(headers: Dict[str, bytes], ts_ms: int) -> None:
    headers[H_RETRY_NOT_BEFORE] = _to_bytes_int(ts_ms)


def ensure_original_topic(headers: Dict[str, bytes], topic: str) -> None:
    if H_ORIGINAL_TOPIC not in headers:
        headers[H_ORIGINAL_TOPIC] = topic.encode("utf-8")
