# input: Optional[RedisClient]（可为 None 时退化为 no-op）
# output: PersonaBuildCache (build_cache_key / get / set)；Story 2.4 AC7 幂等缓存（TTL=15min）
# owner: wanhua.gu
# pos: 应用层 - persona 构建幂等缓存（Redis thin wrapper, 无 Redis 时 no-op）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Redis-backed idempotency cache for persona build runs (Story 2.4 AC7).

Key design points:
- Key = SHA256 of (user_id || NUL || sorted(materials))  — order-insensitive
  so duplicate requests with shuffled materials hit the same cache
- Value = persona_id string
- TTL = 900s (15 min)
- Redis failures are swallowed (logged at WARNING) so the main build path is
  never blocked by cache availability
- When ``redis`` is None (no config), all operations are no-ops
"""

from __future__ import annotations

import hashlib
from typing import Optional

from core.logging_config import get_logger

logger = get_logger(__name__)

_CACHE_PREFIX = "persona_build"
_DEFAULT_TTL_S = 900  # 15 minutes


def build_cache_key(user_id: str, materials: list[str]) -> str:
    """Compute a deterministic, order-insensitive cache key for (user_id, materials).

    Sorting materials means two requests with the same set of texts (regardless
    of order) hit the same cache entry — desirable for UX (users tend to
    re-submit the same pasted content in different orderings while tinkering).
    """
    h = hashlib.sha256()
    h.update(user_id.encode("utf-8"))
    for mat in sorted(materials):
        h.update(b"\x00")
        h.update(mat.encode("utf-8"))
    return f"{_CACHE_PREFIX}:{h.hexdigest()}"


class PersonaBuildCache:
    """Thin Redis wrapper providing get/set with TTL and graceful degradation."""

    def __init__(self, redis, *, ttl_s: int = _DEFAULT_TTL_S) -> None:
        """Accept any object exposing async ``get(key)`` / ``set(key, value, ttl=)``.

        Passing ``None`` disables caching (all operations become no-ops).
        """
        self._redis = redis
        self._ttl = ttl_s

    async def get(self, key: str) -> Optional[str]:
        if self._redis is None:
            return None
        try:
            return await self._redis.get(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("persona_build_cache_get_failed", key=key, error=str(exc))
            return None

    async def set(self, key: str, persona_id: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.set(key, persona_id, ttl=self._ttl)
        except Exception as exc:  # noqa: BLE001
            logger.warning("persona_build_cache_set_failed", key=key, error=str(exc))


__all__ = ["PersonaBuildCache", "build_cache_key"]
