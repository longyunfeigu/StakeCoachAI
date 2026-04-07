"""缓存层对外暴露的接口"""

from .redis_client import (
    # 主类
    RedisClient,
    CachePatterns,
    CacheInterface,
    # 枚举和数据类
    CacheStatus,
    RedisDataType,
    CacheMetrics,
    # 初始化和管理函数
    init_redis_client,
    get_redis_client,
    shutdown_redis_client,
    create_redis_client,
)


__all__ = [
    # 新接口（推荐使用）
    "RedisClient",
    "CachePatterns",
    "CacheInterface",
    "CacheStatus",
    "RedisDataType",
    "CacheMetrics",
    "init_redis_client",
    "get_redis_client",
    "shutdown_redis_client",
    "create_redis_client",
]
