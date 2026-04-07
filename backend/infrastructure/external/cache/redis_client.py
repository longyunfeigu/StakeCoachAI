"""
统一的Redis客户端实现 - 支持完整数据结构和高级功能
"""

from __future__ import annotations

import asyncio
import json
from core.logging_config import get_logger
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
import random
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncGenerator

from redis import asyncio as aioredis
from redis.exceptions import RedisError

from core.config import settings
import socket

logger = get_logger(__name__)


# ============= 枚举和数据类 =============


class CacheStatus(Enum):
    """缓存状态枚举"""

    HIT = "hit"
    MISS = "miss"
    ERROR = "error"


class RedisDataType(Enum):
    """Redis数据类型枚举"""

    STRING = "string"
    HASH = "hash"
    LIST = "list"
    SET = "set"
    ZSET = "zset"
    STREAM = "stream"
    BITMAP = "bitmap"
    HYPERLOGLOG = "hyperloglog"
    GEO = "geo"


class CacheMetrics:
    """缓存指标统计"""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.total_get = 0
        self.total_set = 0
        self.total_delete = 0
        self.operation_times = []

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def avg_operation_time(self) -> float:
        if not self.operation_times:
            return 0.0
        return sum(self.operation_times) / len(self.operation_times)

    def record_get(self, status: CacheStatus):
        self.total_get += 1
        if status == CacheStatus.HIT:
            self.hits += 1
        elif status == CacheStatus.MISS:
            self.misses += 1
        else:
            self.errors += 1

    def record_operation_time(self, duration: float):
        self.operation_times.append(duration)
        # 只保留最近1000次操作的时间
        if len(self.operation_times) > 1000:
            self.operation_times.pop(0)


# ============= 缓存接口 =============


class CacheInterface(ABC):
    """缓存抽象接口"""

    @abstractmethod
    async def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        pass

    @abstractmethod
    async def delete(self, *keys: str) -> int:
        """删除一个或多个键，返回删除的数量"""
        pass

    @abstractmethod
    async def exists(self, *keys: str) -> int:
        """判断一个或多个键是否存在，返回存在的数量"""
        pass

    @abstractmethod
    async def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间"""
        pass


# ============= 主Redis客户端类 =============


class RedisClient(CacheInterface):
    """
    统一的Redis客户端 - 完整功能实现

    特性:
    - 支持所有Redis数据结构
    - 自动序列化/反序列化
    - 命名空间隔离
    - 性能监控和指标统计
    - 分布式锁支持
    - 事务和管道支持
    - 完善的错误处理
    """

    def __init__(
        self,
        client: aioredis.Redis,
        namespace: str = "",
        enable_metrics: bool = True,
        enable_logging: bool = True,
        serializer: Optional[Callable] = None,
        deserializer: Optional[Callable] = None,
    ):
        self._client = client
        self._namespace = namespace.strip(":")
        self._enable_metrics = enable_metrics
        self._enable_logging = enable_logging
        self._metrics = CacheMetrics() if enable_metrics else None

        # 自定义序列化器
        self._serializer = serializer or self._default_serializer
        self._deserializer = deserializer or self._default_deserializer

    # ============= 工具方法 =============

    def _format_key(self, key: str) -> str:
        """格式化键名，添加命名空间前缀"""
        if not self._namespace:
            return key
        return f"{self._namespace}:{key}"

    def _default_serializer(self, value: Any) -> str:
        """默认序列化方法"""
        if isinstance(value, (str, int, float)):
            return str(value)
        try:
            return json.dumps(value, default=str, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.error(f"序列化失败: {e}")
            raise

    def _default_deserializer(self, value: Optional[str], as_json: bool = True) -> Any:
        """默认反序列化方法"""
        if value is None:
            return None
        if not as_json:
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value

    async def _execute_with_metrics(self, operation: Callable, *args, **kwargs) -> Any:
        """带指标统计的操作执行"""
        if not self._enable_metrics:
            return await operation(*args, **kwargs)

        start_time = time.time()
        try:
            result = await operation(*args, **kwargs)
            duration = time.time() - start_time
            self._metrics.record_operation_time(duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            self._metrics.record_operation_time(duration)
            raise

    # ============= String 操作 =============

    async def get(self, key: str, default: Any = None) -> Any:
        """获取字符串值"""
        formatted_key = self._format_key(key)
        try:
            value = await self._execute_with_metrics(self._client.get, formatted_key)

            if self._enable_metrics:
                status = CacheStatus.HIT if value is not None else CacheStatus.MISS
                self._metrics.record_get(status)

            if self._enable_logging and value is None:
                logger.debug(f"缓存未命中: {formatted_key}")

            return self._deserializer(value) if value is not None else default

        except RedisError as e:
            if self._enable_metrics:
                self._metrics.record_get(CacheStatus.ERROR)
            logger.error(f"获取缓存失败 [{formatted_key}]: {e}")
            return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        nx: bool = False,  # 仅当key不存在时设置
        xx: bool = False,  # 仅当key存在时设置
        keepttl: bool = False,  # 保持原有TTL
        get: bool = False,  # 返回旧值
    ) -> Union[bool, Any]:
        """设置字符串值，支持多种选项"""
        formatted_key = self._format_key(key)
        try:
            payload = self._serializer(value)
            expire = ttl if ttl is not None else settings.redis.default_ttl

            result = await self._execute_with_metrics(
                self._client.set,
                formatted_key,
                payload,
                ex=expire if expire and expire > 0 else None,
                nx=nx,
                xx=xx,
                keepttl=keepttl,
                get=get,
            )

            if self._enable_metrics:
                self._metrics.total_set += 1

            if self._enable_logging:
                logger.debug(f"缓存设置成功: {formatted_key}, TTL: {expire}")

            if get:
                return self._deserializer(result) if result else None
            return bool(result)

        except RedisError as e:
            logger.error(f"设置缓存失败 [{formatted_key}]: {e}")
            return False if not get else None

    async def getset(self, key: str, value: Any) -> Any:
        """设置新值并返回旧值"""
        formatted_key = self._format_key(key)
        try:
            old_value = await self._execute_with_metrics(
                self._client.getset, formatted_key, self._serializer(value)
            )
            return self._deserializer(old_value) if old_value else None
        except RedisError as e:
            logger.error(f"getset操作失败: {e}")
            return None

    async def mget(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取"""
        if not keys:
            return {}

        formatted_keys = [self._format_key(k) for k in keys]
        try:
            values = await self._execute_with_metrics(self._client.mget, formatted_keys)
            return {
                key: self._deserializer(value)
                for key, value in zip(keys, values)
                if value is not None
            }
        except RedisError as e:
            logger.error(f"批量获取失败: {e}")
            return {}

    async def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """批量设置"""
        if not mapping:
            return True

        try:
            # 序列化所有值
            formatted_mapping = {
                self._format_key(k): self._serializer(v) for k, v in mapping.items()
            }

            # 使用pipeline提高性能
            async with self._client.pipeline() as pipe:
                expire = ttl if ttl is not None else settings.redis.default_ttl

                for key, value in formatted_mapping.items():
                    if expire and expire > 0:
                        pipe.set(key, value, ex=expire)
                    else:
                        pipe.set(key, value)

                results = await pipe.execute()

                if self._enable_metrics:
                    self._metrics.total_set += len(mapping)

                return all(results)

        except RedisError as e:
            logger.error(f"批量设置失败: {e}")
            return False

    async def incr(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> Optional[int]:
        """自增计数器"""
        formatted_key = self._format_key(key)
        try:
            value = await self._execute_with_metrics(self._client.incrby, formatted_key, amount)

            expire = ttl if ttl is not None else settings.redis.default_ttl
            if expire and expire > 0:
                await self._client.expire(formatted_key, expire)

            return value

        except RedisError as e:
            logger.error(f"自增计数器失败 [{formatted_key}]: {e}")
            return None

    async def decr(self, key: str, amount: int = 1) -> Optional[int]:
        """自减计数器"""
        formatted_key = self._format_key(key)
        try:
            return await self._execute_with_metrics(self._client.decrby, formatted_key, amount)
        except RedisError as e:
            logger.error(f"自减计数器失败 [{formatted_key}]: {e}")
            return None

    # ============= Hash 操作 =============

    async def hget(self, key: str, field: str) -> Any:
        """获取Hash字段值"""
        try:
            value = await self._execute_with_metrics(
                self._client.hget, self._format_key(key), field
            )
            return self._deserializer(value) if value else None
        except RedisError as e:
            logger.error(f"获取Hash字段失败: {e}")
            return None

    async def hset(
        self,
        key: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        mapping: Optional[Dict[str, Any]] = None,
    ) -> int:
        """设置Hash字段值，支持单个或批量设置"""
        formatted_key = self._format_key(key)
        try:
            if mapping:
                # 批量设置
                serialized_mapping = {k: self._serializer(v) for k, v in mapping.items()}
                return await self._execute_with_metrics(
                    self._client.hset, formatted_key, mapping=serialized_mapping
                )
            elif field is not None and value is not None:
                # 单个设置
                return await self._execute_with_metrics(
                    self._client.hset, formatted_key, field, self._serializer(value)
                )
            else:
                raise ValueError("必须提供field和value，或者mapping参数")
        except RedisError as e:
            logger.error(f"设置Hash字段失败: {e}")
            return 0

    async def hmset(self, key: str, mapping: Dict[str, Any]) -> bool:
        """批量设置Hash字段（兼容旧API）"""
        return await self.hset(key, mapping=mapping) > 0

    async def hgetall(self, key: str) -> Dict[str, Any]:
        """获取Hash所有字段"""
        try:
            data = await self._execute_with_metrics(self._client.hgetall, self._format_key(key))
            return {field: self._deserializer(value) for field, value in data.items()}
        except RedisError as e:
            logger.error(f"获取Hash所有字段失败: {e}")
            return {}

    async def hdel(self, key: str, *fields: str) -> int:
        """删除Hash字段"""
        try:
            return await self._execute_with_metrics(
                self._client.hdel, self._format_key(key), *fields
            )
        except RedisError as e:
            logger.error(f"删除Hash字段失败: {e}")
            return 0

    async def hexists(self, key: str, field: str) -> bool:
        """检查Hash字段是否存在"""
        try:
            return await self._execute_with_metrics(
                self._client.hexists, self._format_key(key), field
            )
        except RedisError as e:
            logger.error(f"检查Hash字段失败: {e}")
            return False

    async def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        """Hash字段自增"""
        try:
            return await self._execute_with_metrics(
                self._client.hincrby, self._format_key(key), field, amount
            )
        except RedisError as e:
            logger.error(f"Hash字段自增失败: {e}")
            return 0

    # ============= List 操作 =============

    async def lpush(self, key: str, *values: Any) -> int:
        """从左侧推入列表"""
        formatted_key = self._format_key(key)
        try:
            serialized_values = [self._serializer(v) for v in values]
            return await self._execute_with_metrics(
                self._client.lpush, formatted_key, *serialized_values
            )
        except RedisError as e:
            logger.error(f"列表左侧推入失败: {e}")
            return 0

    async def rpush(self, key: str, *values: Any) -> int:
        """从右侧推入列表"""
        formatted_key = self._format_key(key)
        try:
            serialized_values = [self._serializer(v) for v in values]
            return await self._execute_with_metrics(
                self._client.rpush, formatted_key, *serialized_values
            )
        except RedisError as e:
            logger.error(f"列表右侧推入失败: {e}")
            return 0

    async def lpop(self, key: str, count: Optional[int] = None) -> Any:
        """从左侧弹出元素"""
        try:
            result = await self._execute_with_metrics(
                self._client.lpop, self._format_key(key), count
            )
            if count:
                return [self._deserializer(v) for v in result] if result else []
            else:
                return self._deserializer(result) if result else None
        except RedisError as e:
            logger.error(f"列表左侧弹出失败: {e}")
            return [] if count else None

    async def rpop(self, key: str, count: Optional[int] = None) -> Any:
        """从右侧弹出元素"""
        try:
            result = await self._execute_with_metrics(
                self._client.rpop, self._format_key(key), count
            )
            if count:
                return [self._deserializer(v) for v in result] if result else []
            else:
                return self._deserializer(result) if result else None
        except RedisError as e:
            logger.error(f"列表右侧弹出失败: {e}")
            return [] if count else None

    async def lrange(self, key: str, start: int = 0, stop: int = -1) -> List[Any]:
        """获取列表范围元素"""
        try:
            values = await self._execute_with_metrics(
                self._client.lrange, self._format_key(key), start, stop
            )
            return [self._deserializer(v) for v in values]
        except RedisError as e:
            logger.error(f"获取列表范围失败: {e}")
            return []

    async def llen(self, key: str) -> int:
        """获取列表长度"""
        try:
            return await self._execute_with_metrics(self._client.llen, self._format_key(key))
        except RedisError as e:
            logger.error(f"获取列表长度失败: {e}")
            return 0

    async def ltrim(self, key: str, start: int, stop: int) -> bool:
        """修剪列表，保留指定范围"""
        try:
            await self._execute_with_metrics(self._client.ltrim, self._format_key(key), start, stop)
            return True
        except RedisError as e:
            logger.error(f"修剪列表失败: {e}")
            return False

    async def blpop(
        self, keys: Union[str, List[str]], timeout: int = 0
    ) -> Optional[Tuple[str, Any]]:
        """阻塞式左侧弹出"""
        if isinstance(keys, str):
            keys = [keys]
        formatted_keys = [self._format_key(k) for k in keys]
        try:
            result = await self._execute_with_metrics(self._client.blpop, formatted_keys, timeout)
            if result:
                # 移除命名空间前缀
                key = result[0]
                if self._namespace and key.startswith(f"{self._namespace}:"):
                    key = key[len(self._namespace) + 1 :]
                return (key, self._deserializer(result[1]))
            return None
        except RedisError as e:
            logger.error(f"阻塞式弹出失败: {e}")
            return None

    # ============= Set 操作 =============

    async def sadd(self, key: str, *members: Any) -> int:
        """添加集合成员"""
        formatted_key = self._format_key(key)
        try:
            serialized_members = [self._serializer(m) for m in members]
            return await self._execute_with_metrics(
                self._client.sadd, formatted_key, *serialized_members
            )
        except RedisError as e:
            logger.error(f"添加集合成员失败: {e}")
            return 0

    async def srem(self, key: str, *members: Any) -> int:
        """移除集合成员"""
        formatted_key = self._format_key(key)
        try:
            serialized_members = [self._serializer(m) for m in members]
            return await self._execute_with_metrics(
                self._client.srem, formatted_key, *serialized_members
            )
        except RedisError as e:
            logger.error(f"移除集合成员失败: {e}")
            return 0

    async def smembers(self, key: str) -> Set[Any]:
        """获取集合所有成员"""
        try:
            members = await self._execute_with_metrics(self._client.smembers, self._format_key(key))
            return {self._deserializer(m) for m in members}
        except RedisError as e:
            logger.error(f"获取集合成员失败: {e}")
            return set()

    async def sismember(self, key: str, member: Any) -> bool:
        """检查是否为集合成员"""
        try:
            return await self._execute_with_metrics(
                self._client.sismember, self._format_key(key), self._serializer(member)
            )
        except RedisError as e:
            logger.error(f"检查集合成员失败: {e}")
            return False

    async def scard(self, key: str) -> int:
        """获取集合大小"""
        try:
            return await self._execute_with_metrics(self._client.scard, self._format_key(key))
        except RedisError as e:
            logger.error(f"获取集合大小失败: {e}")
            return 0

    async def sunion(self, *keys: str) -> Set[Any]:
        """集合并集"""
        formatted_keys = [self._format_key(k) for k in keys]
        try:
            members = await self._execute_with_metrics(self._client.sunion, *formatted_keys)
            return {self._deserializer(m) for m in members}
        except RedisError as e:
            logger.error(f"集合并集操作失败: {e}")
            return set()

    async def sinter(self, *keys: str) -> Set[Any]:
        """集合交集"""
        formatted_keys = [self._format_key(k) for k in keys]
        try:
            members = await self._execute_with_metrics(self._client.sinter, *formatted_keys)
            return {self._deserializer(m) for m in members}
        except RedisError as e:
            logger.error(f"集合交集操作失败: {e}")
            return set()

    async def sdiff(self, *keys: str) -> Set[Any]:
        """集合差集"""
        formatted_keys = [self._format_key(k) for k in keys]
        try:
            members = await self._execute_with_metrics(self._client.sdiff, *formatted_keys)
            return {self._deserializer(m) for m in members}
        except RedisError as e:
            logger.error(f"集合差集操作失败: {e}")
            return set()

    # ============= Sorted Set 操作 =============

    async def zadd(
        self,
        key: str,
        mapping: Dict[Any, float],
        nx: bool = False,
        xx: bool = False,
        ch: bool = False,
        incr: bool = False,
    ) -> Union[int, float, None]:
        """添加有序集合成员"""
        formatted_key = self._format_key(key)
        try:
            serialized_mapping = {
                self._serializer(member): score for member, score in mapping.items()
            }
            return await self._execute_with_metrics(
                self._client.zadd, formatted_key, serialized_mapping, nx=nx, xx=xx, ch=ch, incr=incr
            )
        except RedisError as e:
            logger.error(f"添加有序集合成员失败: {e}")
            return None

    async def zrange(
        self, key: str, start: int = 0, stop: int = -1, withscores: bool = False, desc: bool = False
    ) -> Union[List[Any], List[Tuple[Any, float]]]:
        """获取有序集合范围成员"""
        try:
            if desc:
                result = await self._execute_with_metrics(
                    self._client.zrevrange,
                    self._format_key(key),
                    start,
                    stop,
                    withscores=withscores,
                )
            else:
                result = await self._execute_with_metrics(
                    self._client.zrange, self._format_key(key), start, stop, withscores=withscores
                )

            if withscores:
                return [(self._deserializer(m), score) for m, score in result]
            else:
                return [self._deserializer(m) for m in result]
        except RedisError as e:
            logger.error(f"获取有序集合范围失败: {e}")
            return []

    async def zrank(self, key: str, member: Any) -> Optional[int]:
        """获取成员排名（从0开始）"""
        try:
            return await self._execute_with_metrics(
                self._client.zrank, self._format_key(key), self._serializer(member)
            )
        except RedisError as e:
            logger.error(f"获取成员排名失败: {e}")
            return None

    async def zscore(self, key: str, member: Any) -> Optional[float]:
        """获取成员分数"""
        try:
            return await self._execute_with_metrics(
                self._client.zscore, self._format_key(key), self._serializer(member)
            )
        except RedisError as e:
            logger.error(f"获取成员分数失败: {e}")
            return None

    async def zincrby(self, key: str, amount: float, member: Any) -> float:
        """增加成员分数"""
        try:
            return await self._execute_with_metrics(
                self._client.zincrby, self._format_key(key), amount, self._serializer(member)
            )
        except RedisError as e:
            logger.error(f"增加成员分数失败: {e}")
            return 0.0

    # ============= 通用操作 =============

    async def delete(self, *keys: str) -> int:
        """删除键"""
        formatted_keys = [self._format_key(k) for k in keys]
        try:
            result = await self._execute_with_metrics(self._client.delete, *formatted_keys)
            if self._enable_metrics:
                self._metrics.total_delete += result
            return result
        except RedisError as e:
            logger.error(f"删除键失败: {e}")
            return 0

    async def exists(self, *keys: str) -> int:
        """检查键是否存在"""
        formatted_keys = [self._format_key(k) for k in keys]
        try:
            return await self._execute_with_metrics(self._client.exists, *formatted_keys)
        except RedisError as e:
            logger.error(f"检查键存在性失败: {e}")
            return 0

    async def expire(self, key: str, seconds: int) -> bool:
        """设置过期时间"""
        try:
            return await self._execute_with_metrics(
                self._client.expire, self._format_key(key), seconds
            )
        except RedisError as e:
            logger.error(f"设置过期时间失败: {e}")
            return False

    async def ttl(self, key: str) -> int:
        """获取剩余生存时间（秒）"""
        try:
            return await self._execute_with_metrics(self._client.ttl, self._format_key(key))
        except RedisError as e:
            logger.error(f"获取TTL失败: {e}")
            return -2

    async def type(self, key: str) -> str:
        """获取键类型"""
        try:
            return await self._execute_with_metrics(self._client.type, self._format_key(key))
        except RedisError as e:
            logger.error(f"获取键类型失败: {e}")
            return "none"

    async def keys(self, pattern: str = "*") -> List[str]:
        """查找匹配的键（使用 SCAN 迭代，避免 KEYS 阻塞）"""
        try:
            if self._namespace:
                formatted_pattern = self._format_key(pattern if pattern != "*" else "*")
            else:
                formatted_pattern = pattern

            collected: List[str] = []
            async for k in self._client.scan_iter(match=formatted_pattern):
                if self._namespace:
                    prefix = f"{self._namespace}:"
                    if k.startswith(prefix):
                        collected.append(k[len(prefix) :])
                    else:
                        collected.append(k)
                else:
                    collected.append(k)
            return collected
        except RedisError as e:
            logger.error(f"查找键失败: {e}")
            return []

    async def clear_namespace(self) -> int:
        """清理当前命名空间下的所有键"""
        pattern = f"{self._namespace}:*" if self._namespace else "*"
        deleted_count = 0

        try:
            # 使用pipeline批量删除
            cursor = 0
            while True:
                cursor, keys = await self._client.scan(cursor, match=pattern, count=100)

                if keys:
                    async with self._client.pipeline() as pipe:
                        for key in keys:
                            # Async pipeline commands are enqueued synchronously; only execute() is awaited
                            pipe.delete(key)
                        results = await pipe.execute()
                        deleted_count += sum(results)

                if cursor == 0:
                    break

            logger.info(f"清理命名空间 [{self._namespace}], 删除 {deleted_count} 个键")
            return deleted_count

        except RedisError as e:
            logger.error(f"清理命名空间失败: {e}")
            return deleted_count

    # ============= 高级功能 =============

    @asynccontextmanager
    async def lock(
        self,
        key: str,
        timeout: int = 10,
        blocking_timeout: int = 5,
        thread_local: bool = True,
        *,
        auto_renew: Optional[bool] = None,
        renew_interval: Optional[float] = None,
        jitter: Optional[float] = None,
    ):
        """
        分布式锁上下文管理器，支持可选自动续租。

        Args:
            key: 锁的键名
            timeout: 锁的超时时间（秒）
            blocking_timeout: 获取锁的等待时间（秒）
            thread_local: 是否使用线程本地存储
            auto_renew: 是否自动续租；None 则使用配置默认
            renew_interval: 续租间隔（秒）；None 则按比例计算（默认 60% * timeout）
            jitter: 抖动比例（0~1）；None 使用配置默认（默认 0.1）
        """
        lock_key = f"lock:{self._format_key(key)}"
        lock = self._client.lock(
            lock_key,
            timeout=timeout,
            blocking_timeout=blocking_timeout,
            thread_local=thread_local,
        )

        enable_auto_renew = (
            settings.REDIS_LOCK_AUTO_RENEW_DEFAULT if auto_renew is None else auto_renew
        )
        ratio = getattr(settings, "REDIS_LOCK_AUTO_RENEW_INTERVAL_RATIO", 0.6)
        jitter_ratio = (
            getattr(settings, "REDIS_LOCK_AUTO_RENEW_JITTER_RATIO", 0.1)
            if jitter is None
            else jitter
        )

        cancel = asyncio.Event()

        async def _auto_extend_task():
            # 无 timeout 或非正值时不进行续租
            if not timeout or timeout <= 0:
                return
            base_interval = (
                renew_interval if renew_interval is not None else max(1.0, timeout * float(ratio))
            )
            try:
                while not cancel.is_set():
                    # 计算带抖动的间隔，避免续租尖峰
                    j = (
                        1.0 + random.uniform(-float(jitter_ratio), float(jitter_ratio))
                        if jitter_ratio
                        else 1.0
                    )
                    interval = max(0.5, base_interval * j)
                    try:
                        await asyncio.wait_for(cancel.wait(), timeout=interval)
                        break  # cancel set
                    except asyncio.TimeoutError:
                        pass
                    try:
                        await lock.extend(timeout)
                    except Exception as e:
                        logger.warning(f"锁续租失败 [{lock_key}]: {e}")
            except asyncio.CancelledError:
                pass

        task: Optional[asyncio.Task] = None

        try:
            acquired = await lock.acquire()
            if not acquired:
                raise TimeoutError(f"获取锁失败: {lock_key}")
            if enable_auto_renew:
                task = asyncio.create_task(_auto_extend_task())
            yield lock
        finally:
            cancel.set()
            if task is not None:
                task.cancel()
                try:
                    await task
                except Exception:
                    pass
            try:
                await lock.release()
            except Exception as e:
                logger.error(f"释放锁失败 [{lock_key}]: {e}")

    @asynccontextmanager
    async def pipeline(self, transaction: bool = True):
        """
        管道/事务上下文管理器

        Args:
            transaction: 是否使用事务（MULTI/EXEC）
        """
        pipe = self._client.pipeline(transaction=transaction)
        try:
            yield pipe
            await pipe.execute()
        except Exception as e:
            logger.error(f"管道/事务执行失败: {e}")
            raise

    async def publish(self, channel: str, message: Any) -> int:
        """
        发布消息到频道

        Args:
            channel: 频道名称
            message: 消息内容

        Returns:
            接收消息的订阅者数量
        """
        formatted_channel = self._format_key(channel)
        try:
            return await self._execute_with_metrics(
                self._client.publish, formatted_channel, self._serializer(message)
            )
        except RedisError as e:
            logger.error(f"发布消息失败: {e}")
            return 0

    async def subscribe(self, *channels: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        订阅频道，返回消息生成器

        Args:
            channels: 要订阅的频道列表

        Yields:
            接收到的消息字典
        """
        formatted_channels = [self._format_key(c) for c in channels]
        pubsub = self._client.pubsub()

        try:
            await pubsub.subscribe(*formatted_channels)

            async for message in pubsub.listen():
                if message["type"] in ("message", "pmessage"):
                    # 处理消息
                    channel = message["channel"]
                    if self._namespace and channel.startswith(f"{self._namespace}:"):
                        channel = channel[len(self._namespace) + 1 :]

                    processed_message = {
                        "channel": channel,
                        "data": self._deserializer(message["data"]),
                        "pattern": message.get("pattern"),
                    }
                    yield processed_message
        finally:
            await pubsub.unsubscribe(*formatted_channels)
            await pubsub.close()

    async def psubscribe(self, pattern: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        模式订阅（psubscribe），返回消息生成器。

        Args:
            pattern: 频道匹配模式（支持通配符）

        Yields:
            接收到的消息字典
        """
        # 为 pattern 增加命名空间前缀
        formatted_pattern = self._format_key(pattern)
        pubsub = self._client.pubsub()

        try:
            await pubsub.psubscribe(formatted_pattern)

            async for message in pubsub.listen():
                if message["type"] in ("pmessage", "message"):
                    channel = message.get("channel")
                    data = message.get("data")
                    # 还原去掉命名空间前缀的频道名
                    if (
                        isinstance(channel, str)
                        and self._namespace
                        and channel.startswith(f"{self._namespace}:")
                    ):
                        channel = channel[len(self._namespace) + 1 :]

                    processed_message = {
                        "channel": channel,
                        "data": self._deserializer(data),
                        "pattern": message.get("pattern"),
                    }
                    yield processed_message
        finally:
            try:
                await pubsub.punsubscribe(formatted_pattern)
            finally:
                await pubsub.close()

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            return await self._client.ping()
        except Exception as e:
            logger.error(f"Redis健康检查失败: {e}")
            return False

    @property
    def metrics(self) -> Optional[CacheMetrics]:
        """获取指标统计"""
        return self._metrics

    @property
    def client(self) -> aioredis.Redis:
        """获取原始Redis客户端（谨慎使用）"""
        return self._client


# ============= 缓存模式实现 =============


class CachePatterns:
    """常用缓存模式实现"""

    def __init__(self, cache: RedisClient):
        self.cache = cache

    async def cache_aside(self, key: str, fetch_func: Callable, ttl: Optional[int] = None) -> Any:
        """
        Cache-Aside模式（最常用）
        1. 先从缓存读取
        2. 缓存未命中时从数据源获取
        3. 将结果写入缓存
        """
        # 尝试从缓存获取
        value = await self.cache.get(key)
        if value is not None:
            return value

        # 缓存未命中，从数据源获取
        value = await fetch_func()

        # 写入缓存
        if value is not None:
            await self.cache.set(key, value, ttl=ttl)

        return value

    async def write_through(
        self, key: str, value: Any, write_func: Callable, ttl: Optional[int] = None
    ) -> bool:
        """
        Write-Through模式
        1. 同时写入缓存和数据源
        2. 保证数据一致性
        """
        # 写入数据源
        success = await write_func(value)

        if success:
            # 写入缓存
            await self.cache.set(key, value, ttl=ttl)

        return success

    async def write_behind(
        self, key: str, value: Any, queue_key: str = "write_queue", ttl: Optional[int] = None
    ) -> bool:
        """
        Write-Behind模式（异步写入）
        1. 先写入缓存
        2. 异步写入数据源（通过队列）
        """
        # 立即写入缓存
        cache_success = await self.cache.set(key, value, ttl=ttl)

        if cache_success:
            # 加入写入队列（后台任务处理）
            await self.cache.rpush(
                queue_key, {"key": key, "value": value, "timestamp": datetime.now().isoformat()}
            )

        return cache_success

    async def refresh_ahead(
        self, key: str, fetch_func: Callable, ttl: int, refresh_ratio: float = 0.8
    ) -> Any:
        """
        Refresh-Ahead模式
        在TTL即将过期时主动刷新缓存
        """
        value = await self.cache.get(key)
        remaining_ttl = await self.cache.ttl(key)

        # 如果剩余时间少于阈值，主动刷新
        if remaining_ttl > 0 and remaining_ttl < ttl * (1 - refresh_ratio):
            # 异步刷新（可以放入任务队列）
            new_value = await fetch_func()
            await self.cache.set(key, new_value, ttl=ttl)
            return new_value

        # 缓存未命中或不需要刷新
        if value is None:
            value = await fetch_func()
            await self.cache.set(key, value, ttl=ttl)

        return value


# ============= 单例模式管理 =============

_redis_client: Optional[aioredis.Redis] = None
_cache_instance: Optional[RedisClient] = None
_lock = asyncio.Lock()


async def init_redis_client(
    namespace: Optional[str] = None,
    enable_metrics: bool = True,
    enable_logging: bool = True,
    **kwargs,
) -> RedisClient:
    """
    初始化Redis客户端

    Args:
        namespace: 命名空间
        enable_metrics: 是否启用指标统计
        enable_logging: 是否启用日志
        **kwargs: 其他Redis连接参数

    Returns:
        RedisClient实例
    """
    global _redis_client, _cache_instance

    if _cache_instance is not None:
        return _cache_instance

    async with _lock:
        if _cache_instance is not None:
            return _cache_instance

        if not settings.redis.url:
            raise RuntimeError("REDIS__URL 未配置，无法初始化Redis客户端")

        try:
            # 创建Redis连接
            # 构建跨平台 keepalive 选项（若可用）
            keepalive_opts = {}
            if (
                hasattr(socket, "TCP_KEEPIDLE")
                and hasattr(socket, "TCP_KEEPINTVL")
                and hasattr(socket, "TCP_KEEPCNT")
            ):
                keepalive_opts = {
                    socket.TCP_KEEPIDLE: 1,
                    socket.TCP_KEEPINTVL: 1,
                    socket.TCP_KEEPCNT: 3,
                }

            client = aioredis.from_url(
                settings.redis.url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=settings.redis.max_connections,
                socket_keepalive=True,
                socket_keepalive_options=keepalive_opts,
                **kwargs,
            )

            # 测试连接
            await client.ping()

            _redis_client = client
            _cache_instance = RedisClient(
                client=client,
                namespace=namespace or settings.redis.namespace,
                enable_metrics=enable_metrics,
                enable_logging=enable_logging,
            )

            logger.info(f"Redis客户端初始化成功: {settings.redis.url}")
            return _cache_instance

        except Exception as e:
            logger.error(f"Redis客户端初始化失败: {e}")
            raise


async def get_redis_client() -> RedisClient:
    """获取全局Redis客户端实例"""
    if _cache_instance is None:
        return await init_redis_client()
    return _cache_instance


async def shutdown_redis_client() -> None:
    """关闭Redis连接"""
    global _redis_client, _cache_instance

    if _redis_client is not None:
        try:
            await _redis_client.close()
            logger.info("Redis连接已关闭")
        except Exception as e:
            logger.error(f"关闭Redis连接失败: {e}")
        finally:
            _redis_client = None
            _cache_instance = None


# ============= 便捷函数 =============


async def create_redis_client(namespace: str, **kwargs) -> RedisClient:
    """
    创建独立的Redis客户端实例（非单例）

    Args:
        namespace: 命名空间
        **kwargs: Redis连接参数

    Returns:
        新的RedisClient实例
    """
    if not settings.redis.url:
        raise RuntimeError("REDIS__URL 未配置")

    client = aioredis.from_url(
        settings.redis.url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=settings.redis.max_connections,
        **kwargs,
    )

    await client.ping()

    return RedisClient(client=client, namespace=namespace, enable_metrics=True, enable_logging=True)
