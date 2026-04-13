# input: application.services.stakeholder.persona_build_cache
# output: Story 2.4 AC7 幂等缓存 get/set/降级测试
# owner: wanhua.gu
# pos: 测试层 - Story 2.4 Redis 幂等缓存单元测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Story 2.4 PersonaBuildCache + build_cache_key (AC7)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from application.services.stakeholder.persona_build_cache import (
    PersonaBuildCache,
    build_cache_key,
)


def test_cache_key_is_deterministic():
    k1 = build_cache_key("user-1", ["hello", "world"])
    k2 = build_cache_key("user-1", ["hello", "world"])
    assert k1 == k2


def test_cache_key_is_order_insensitive():
    k1 = build_cache_key("user-1", ["hello", "world"])
    k2 = build_cache_key("user-1", ["world", "hello"])
    assert k1 == k2


def test_cache_key_differs_by_user():
    k1 = build_cache_key("user-1", ["hello"])
    k2 = build_cache_key("user-2", ["hello"])
    assert k1 != k2


def test_cache_key_differs_by_content():
    k1 = build_cache_key("user-1", ["hello"])
    k2 = build_cache_key("user-1", ["world"])
    assert k1 != k2


def test_cache_key_has_prefix():
    key = build_cache_key("u", ["x"])
    assert key.startswith("persona_build:")


@pytest.mark.asyncio
async def test_cache_noop_when_redis_is_none():
    cache = PersonaBuildCache(redis=None)
    assert await cache.get("any-key") is None
    # set() returns None and does not raise
    await cache.set("any-key", "persona-1")


@pytest.mark.asyncio
async def test_cache_roundtrip_with_fake_redis():
    store: dict[str, str] = {}

    class _FakeRedis:
        async def get(self, key):
            return store.get(key)

        async def set(self, key, value, ttl=None):
            store[key] = value

    cache = PersonaBuildCache(redis=_FakeRedis(), ttl_s=30)
    assert await cache.get("k1") is None
    await cache.set("k1", "persona-abc")
    assert await cache.get("k1") == "persona-abc"


@pytest.mark.asyncio
async def test_cache_get_swallows_redis_exception():
    redis = AsyncMock()
    redis.get.side_effect = RuntimeError("connection refused")

    cache = PersonaBuildCache(redis=redis)
    assert await cache.get("k") is None  # does not raise


@pytest.mark.asyncio
async def test_cache_set_swallows_redis_exception():
    redis = AsyncMock()
    redis.set.side_effect = RuntimeError("connection refused")

    cache = PersonaBuildCache(redis=redis)
    await cache.set("k", "persona-1")  # does not raise


@pytest.mark.asyncio
async def test_cache_set_passes_ttl_to_redis():
    redis = AsyncMock()

    cache = PersonaBuildCache(redis=redis, ttl_s=300)
    await cache.set("k", "persona-1")

    redis.set.assert_awaited_once_with("k", "persona-1", ttl=300)
