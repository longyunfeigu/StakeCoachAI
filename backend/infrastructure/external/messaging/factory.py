from __future__ import annotations

from typing import List, Optional

from .base import ConsumeMiddleware, Consumer, Envelope, PublishMiddleware, Publisher, Serializer
from .config import MessagingConfig
from .providers.kafka.publisher import KafkaPublisher
from .providers.kafka.consumer import KafkaConsumer

try:
    from .providers.aiokafka.publisher import AiokafkaPublisher
    from .providers.aiokafka.consumer import AiokafkaConsumer
except Exception:
    AiokafkaPublisher = None  # type: ignore
    AiokafkaConsumer = None  # type: ignore


def create_publisher(
    cfg: MessagingConfig,
    serializer: Serializer,
    middlewares: Optional[List[PublishMiddleware]] = None,
) -> Publisher:
    if cfg.provider == "kafka":
        if cfg.kafka.driver == "confluent":
            return KafkaPublisher(cfg.kafka, serializer, middlewares)
        elif cfg.kafka.driver == "aiokafka":
            if AiokafkaPublisher is None:
                raise ImportError("aiokafka not installed. `pip install aiokafka`. ")
            return AiokafkaPublisher(cfg.kafka, serializer, middlewares)
    raise ValueError(f"Unsupported provider: {cfg.provider}")


def create_consumer(
    cfg: MessagingConfig,
    serializer: Serializer,
    middlewares: Optional[List[ConsumeMiddleware]] = None,
) -> Consumer:
    if cfg.provider == "kafka":
        if cfg.kafka.driver == "confluent":
            return KafkaConsumer(cfg.kafka, cfg.retry, serializer, middlewares)
        elif cfg.kafka.driver == "aiokafka":
            if AiokafkaConsumer is None:
                raise ImportError("aiokafka not installed. `pip install aiokafka`. ")
            return AiokafkaConsumer(cfg.kafka, cfg.retry, serializer, middlewares)
    raise ValueError(f"Unsupported provider: {cfg.provider}")
