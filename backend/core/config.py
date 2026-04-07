"""
配置文件 - 项目配置管理
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GrpcTlsSettings(BaseModel):
    enabled: bool = False
    cert: Optional[str] = None
    key: Optional[str] = None
    ca: Optional[str] = None


class GrpcSettings(BaseModel):
    enabled: bool = False
    host: str = "0.0.0.0"  # nosec B104
    port: int = 50051
    # This maps to GRPC option grpc.max_concurrent_streams
    max_concurrent_streams: int = 100
    tls: GrpcTlsSettings = Field(default_factory=GrpcTlsSettings)


class KafkaSettings(BaseModel):
    # Provider/driver
    provider: str = Field(default="kafka")
    driver: str = Field(default="confluent")  # confluent or aiokafka

    # Core Kafka
    bootstrap_servers: str = Field(default="localhost:9092")
    client_id: str = Field(default="app-messaging")
    transactional_id: Optional[str] = None

    # TLS
    tls_enable: bool = False
    tls_ca_location: Optional[str] = None
    tls_certificate: Optional[str] = None
    tls_key: Optional[str] = None
    tls_verify: bool = True

    # SASL
    sasl_mechanism: Optional[str] = None
    sasl_username: Optional[str] = None
    sasl_password: Optional[str] = None

    # Producer tuning
    producer_acks: str = "all"
    producer_enable_idempotence: bool = True
    producer_compression_type: str = "zstd"
    producer_linger_ms: int = 5
    producer_batch_size: int = 64 * 1024
    producer_max_in_flight: int = 5
    producer_message_timeout_ms: int = 120_000
    producer_send_wait_s: float = 5.0
    producer_delivery_wait_s: float = 30.0

    # Consumer tuning
    consumer_enable_auto_commit: bool = False
    consumer_auto_offset_reset: str = "latest"
    consumer_max_poll_interval_ms: int = 300000
    consumer_session_timeout_ms: int = 45000
    consumer_fetch_min_bytes: int = 1
    consumer_fetch_max_bytes: int = 50 * 1024 * 1024
    consumer_commit_every_n: int = 100
    consumer_commit_interval_ms: int = 2000
    consumer_max_concurrency: int = 1
    consumer_inflight_max: int = 1000

    # Retry policy
    retry_layers: Optional[str] = "retry.5s:5000,retry.1m:60000,retry.10m:600000"
    retry_dlq_suffix: str = "dlq"


class RedisSettings(BaseModel):
    url: Optional[str] = None
    max_connections: int = 10
    default_ttl: int = 300
    namespace: str = "fastapi-forge"


class IdempotencySettings(BaseModel):
    lock_ttl_seconds: int = 30
    result_ttl_seconds: int = 24 * 60 * 60


class DatabaseSettings(BaseModel):
    url: str = "postgresql+asyncpg://stakecoach:password@localhost/stakecoachdb"


class LLMSettings(BaseModel):
    provider: str = "openai"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    max_retries: int = 2


class StorageSettings(BaseModel):
    type: str = "local"  # local, s3, oss
    bucket: Optional[str] = None
    region: Optional[str] = None
    endpoint: Optional[str] = None
    public_base_url: Optional[str] = None
    # S3 specific
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    s3_sse: Optional[str] = None
    s3_acl: str = "private"
    # OSS specific
    oss_access_key_id: Optional[str] = None
    oss_access_key_secret: Optional[str] = None
    # Local storage specific
    local_base_path: str = "/tmp/storage"  # nosec B108
    # Advanced settings
    max_retry_attempts: int = 3
    timeout: int = 30
    enable_ssl: bool = True
    presign_max_size: int = 100 * 1024 * 1024  # 100MB
    presign_content_types: Optional[list[str]] = None
    validation_enabled: bool = False
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_types: Optional[list[str]] = None


class MetricsSettings(BaseModel):
    enabled: bool = False
    access_token: Optional[str] = None


class TracingSettings(BaseModel):
    enabled: bool = False
    exporter: str = "console"
    otlp_endpoint: Optional[str] = None
    sample_rate: float = 1.0
    expose_trace_id: bool = False


class HealthSettings(BaseModel):
    db_timeout_seconds: float = 5.0
    redis_timeout_seconds: float = 3.0
    storage_timeout_seconds: float = 5.0
    include_details: bool = False
    access_token: Optional[str] = None


class StakeholderSettings(BaseModel):
    anthropic_api_key: Optional[str] = None
    anthropic_base_url: Optional[str] = None
    model: str = "claude-opus-4-0-20250514"
    persona_dir: str = "data/personas"
    max_group_rounds: int = 20


class Settings(BaseSettings):
    """项目配置"""

    # 基础配置
    PROJECT_NAME: str = Field(
        default="FastAPI DDD Framework",
        validation_alias=AliasChoices("PROJECT_NAME", "APP_NAME"),
    )
    VERSION: str = Field(default="1.0.0", validation_alias=AliasChoices("VERSION", "APP_VERSION"))
    DEBUG: bool = Field(default=True, validation_alias=AliasChoices("DEBUG"))
    ENVIRONMENT: str = Field(default="development", validation_alias=AliasChoices("ENVIRONMENT"))
    AUTO_RUN_MIGRATIONS: bool = Field(
        default=False, validation_alias=AliasChoices("AUTO_RUN_MIGRATIONS")
    )

    # Server（用于 uvicorn / 部署脚本）
    HOST: str = Field(default="0.0.0.0", validation_alias=AliasChoices("HOST"))  # nosec B104
    PORT: int = Field(default=8000, validation_alias=AliasChoices("PORT"))
    RELOAD: bool = Field(default=False, validation_alias=AliasChoices("RELOAD"))
    WORKERS: int = Field(default=1, validation_alias=AliasChoices("WORKERS"))

    # 分组配置（方案A）：Kafka/Redis/Database/Storage 采用嵌套模型（外部类）
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    idempotency: IdempotencySettings = Field(default_factory=IdempotencySettings)

    # 安全配置
    SECRET_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SECRET_KEY"),
        description="应用密钥，生产环境必须设置",
    )

    # CORS配置
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        validation_alias=AliasChoices("CORS_ORIGINS"),
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(
        default=True, validation_alias=AliasChoices("CORS_ALLOW_CREDENTIALS")
    )
    CORS_ALLOW_METHODS: list[str] = Field(
        default=["*"], validation_alias=AliasChoices("CORS_ALLOW_METHODS")
    )
    CORS_ALLOW_HEADERS: list[str] = Field(
        default=["*"], validation_alias=AliasChoices("CORS_ALLOW_HEADERS")
    )

    llm: LLMSettings = Field(default_factory=LLMSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    metrics: MetricsSettings = Field(default_factory=MetricsSettings)
    tracing: TracingSettings = Field(default_factory=TracingSettings)
    health: HealthSettings = Field(default_factory=HealthSettings)

    # Stakeholder Chat settings
    stakeholder: StakeholderSettings = Field(default_factory=StakeholderSettings)

    # gRPC settings
    grpc: GrpcSettings = Field(default_factory=GrpcSettings)

    # Realtime / WebSocket（预留：仅配置层，具体实现可在业务服务中按需启用）
    REALTIME_WS_SEND_QUEUE_MAX: int = Field(
        default=100, validation_alias=AliasChoices("REALTIME_WS_SEND_QUEUE_MAX")
    )
    REALTIME_WS_SEND_OVERFLOW_POLICY: str = Field(
        default="drop_oldest",
        validation_alias=AliasChoices("REALTIME_WS_SEND_OVERFLOW_POLICY"),
    )

    # 分页配置（支持环境变量覆盖）
    DEFAULT_PAGE_SIZE: int = Field(default=20, validation_alias=AliasChoices("DEFAULT_PAGE_SIZE"))
    MAX_PAGE_SIZE: int = Field(default=100, validation_alias=AliasChoices("MAX_PAGE_SIZE"))

    # Upload（通用上限；具体接口可再做细分）
    MAX_UPLOAD_SIZE: int = Field(
        default=10 * 1024 * 1024, validation_alias=AliasChoices("MAX_UPLOAD_SIZE")
    )
    UPLOAD_DIR: str = Field(default="./uploads", validation_alias=AliasChoices("UPLOAD_DIR"))

    # 日志/请求体记录配置
    LOG_REQUEST_BODY_ENABLE_BY_DEFAULT: bool = Field(
        default=True, validation_alias=AliasChoices("LOG_REQUEST_BODY_ENABLE_BY_DEFAULT")
    )
    LOG_REQUEST_BODY_MAX_BYTES: int = Field(
        default=2048, validation_alias=AliasChoices("LOG_REQUEST_BODY_MAX_BYTES")
    )
    LOG_REQUEST_BODY_ALLOW_MULTIPART: bool = Field(
        default=False, validation_alias=AliasChoices("LOG_REQUEST_BODY_ALLOW_MULTIPART")
    )

    # 文件日志配置
    LOG_FILE: Optional[str] = Field(default=None, validation_alias=AliasChoices("LOG_FILE"))
    LOG_LEVEL: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL"))
    LOG_MAX_BYTES: int = Field(
        default=100 * 1024 * 1024, validation_alias=AliasChoices("LOG_MAX_BYTES")
    )  # 100MB
    LOG_BACKUP_COUNT: int = Field(default=5, validation_alias=AliasChoices("LOG_BACKUP_COUNT"))

    # Email / 外部集成（可选）
    SMTP_HOST: Optional[str] = Field(default=None, validation_alias=AliasChoices("SMTP_HOST"))
    SMTP_PORT: int = Field(default=587, validation_alias=AliasChoices("SMTP_PORT"))
    SMTP_USER: Optional[str] = Field(default=None, validation_alias=AliasChoices("SMTP_USER"))
    SMTP_PASSWORD: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("SMTP_PASSWORD")
    )
    EMAIL_FROM: Optional[str] = Field(default=None, validation_alias=AliasChoices("EMAIL_FROM"))

    STRIPE_API_KEY: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("STRIPE_API_KEY")
    )

    # Error Tracking (Sentry)
    SENTRY_DSN: Optional[str] = Field(default=None, validation_alias=AliasChoices("SENTRY_DSN"))

    # Rate limiting（预留：具体实现可选 Redis/本地）
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=60, validation_alias=AliasChoices("RATE_LIMIT_PER_MINUTE")
    )

    # Redis 锁自动续租配置（全局默认值）
    REDIS_LOCK_AUTO_RENEW_DEFAULT: bool = Field(
        default=False, validation_alias=AliasChoices("REDIS_LOCK_AUTO_RENEW_DEFAULT")
    )
    REDIS_LOCK_AUTO_RENEW_INTERVAL_RATIO: float = Field(
        default=0.6, validation_alias=AliasChoices("REDIS_LOCK_AUTO_RENEW_INTERVAL_RATIO")
    )
    REDIS_LOCK_AUTO_RENEW_JITTER_RATIO: float = Field(
        default=0.1, validation_alias=AliasChoices("REDIS_LOCK_AUTO_RENEW_JITTER_RATIO")
    )

    # Kafka grouped settings (builder below)

    # pydantic-settings v2 configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        # Fail fast for unknown keys in `.env` to avoid "configured but not used" footguns.
        extra="forbid",
        env_nested_delimiter="__",
    )

    @model_validator(mode="after")
    def _validate_secret_key(self):
        # 所有环境均要求显式配置 SECRET_KEY
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY 未配置。请在环境变量或 .env 中设置 SECRET_KEY")
        return self

    @field_validator("CORS_ORIGINS", "CORS_ALLOW_METHODS", "CORS_ALLOW_HEADERS", mode="before")
    @classmethod
    def _parse_str_list(cls, v: Any):
        """允许 JSON 字符串或逗号分隔字符串两种格式。"""
        if isinstance(v, list):
            return [str(item) for item in v]
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("[") and s.endswith("]"):
                import json

                arr = None
                try:
                    arr = json.loads(s)
                except ValueError:
                    arr = None
                if isinstance(arr, list):
                    return [str(item) for item in arr]
            if "," in s:
                return [item.strip() for item in s.split(",") if item.strip()]
            return [s]
        return v


settings = Settings()
