from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional


@dataclass(slots=True)
class TLSConfig:
    enable: bool = False
    ca_location: Optional[str] = None
    certificate: Optional[str] = None
    key: Optional[str] = None
    verify: bool = True


@dataclass(slots=True)
class SASLConfig:
    mechanism: Optional[str] = None  # e.g. "PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512"
    username: Optional[str] = None
    password: Optional[str] = None


@dataclass(slots=True)
class ProducerTuning:
    acks: str = "all"
    enable_idempotence: bool = True
    compression_type: str = "zstd"
    linger_ms: int = 5
    batch_size: int = 64 * 1024
    max_in_flight: int = 5
    # Delivery/timeout tuning
    message_timeout_ms: int = 120_000
    send_wait_s: float = 5.0
    delivery_wait_s: float = 30.0


@dataclass(slots=True)
class ConsumerTuning:
    enable_auto_commit: bool = False
    auto_offset_reset: str = "latest"
    max_poll_interval_ms: int = 300000
    session_timeout_ms: int = 45000
    fetch_min_bytes: int = 1
    fetch_max_bytes: int = 50 * 1024 * 1024
    commit_every_n: int = 100
    commit_interval_ms: int = 2000
    max_concurrency: int = 1
    inflight_max: int = 1000


@dataclass(slots=True)
class RetryLayer:
    suffix: str
    delay_ms: int


@dataclass(slots=True)
class RetryConfig:
    layers: List[RetryLayer] = field(
        default_factory=lambda: [
            RetryLayer(suffix="retry.5s", delay_ms=5_000),
            RetryLayer(suffix="retry.1m", delay_ms=60_000),
            RetryLayer(suffix="retry.10m", delay_ms=600_000),
        ]
    )
    dlq_suffix: str = "dlq"


@dataclass(slots=True)
class KafkaConfig:
    bootstrap_servers: str = "localhost:9092"
    client_id: str = "app-messaging"
    transactional_id: Optional[str] = None
    tls: TLSConfig = field(default_factory=TLSConfig)
    sasl: SASLConfig = field(default_factory=SASLConfig)
    producer: ProducerTuning = field(default_factory=ProducerTuning)
    consumer: ConsumerTuning = field(default_factory=ConsumerTuning)
    driver: Literal["confluent", "aiokafka"] = "confluent"


@dataclass(slots=True)
class MessagingConfig:
    provider: Literal["kafka"] = "kafka"
    kafka: KafkaConfig = field(default_factory=KafkaConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
