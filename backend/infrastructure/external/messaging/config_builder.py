from __future__ import annotations

"""Messaging config builder (composition root for messaging layer).

This module maps application settings (Kafka settings subset) to the
MessagingConfig dataclasses used by the messaging infrastructure.

Keeping this builder in the infrastructure layer avoids coupling core
configuration to specific providers and preserves layering (core -> infra).
"""

from typing import Protocol

from .config import (
    MessagingConfig,
    KafkaConfig,
    TLSConfig,
    SASLConfig,
    ProducerTuning,
    ConsumerTuning,
    RetryConfig,
    RetryLayer,
)


class KafkaSettingsLike(Protocol):
    # Provider/driver
    provider: str
    driver: str  # "confluent" | "aiokafka"

    # Core Kafka
    bootstrap_servers: str
    client_id: str
    transactional_id: str | None

    # TLS
    tls_enable: bool
    tls_ca_location: str | None
    tls_certificate: str | None
    tls_key: str | None
    tls_verify: bool

    # SASL
    sasl_mechanism: str | None
    sasl_username: str | None
    sasl_password: str | None

    # Producer tuning
    producer_acks: str
    producer_enable_idempotence: bool
    producer_compression_type: str
    producer_linger_ms: int
    producer_batch_size: int
    producer_max_in_flight: int

    # Consumer tuning
    consumer_enable_auto_commit: bool
    consumer_auto_offset_reset: str
    consumer_max_poll_interval_ms: int
    consumer_session_timeout_ms: int
    consumer_fetch_min_bytes: int
    consumer_fetch_max_bytes: int
    consumer_commit_every_n: int
    consumer_commit_interval_ms: int
    consumer_max_concurrency: int
    consumer_inflight_max: int

    # Retry policy
    retry_layers: str | None
    retry_dlq_suffix: str


def messaging_config_from_settings(ks: KafkaSettingsLike) -> MessagingConfig:
    """Build MessagingConfig from a KafkaSettings-like object.

    The function performs a simple field mapping. It assumes `ks` exposes
    attributes listed in KafkaSettingsLike and does not import from core.
    """

    tls = TLSConfig(
        enable=ks.tls_enable,
        ca_location=ks.tls_ca_location,
        certificate=ks.tls_certificate,
        key=ks.tls_key,
        verify=ks.tls_verify,
    )
    sasl = SASLConfig(
        mechanism=ks.sasl_mechanism,
        username=ks.sasl_username,
        password=ks.sasl_password,
    )
    producer = ProducerTuning(
        acks=ks.producer_acks,
        enable_idempotence=ks.producer_enable_idempotence,
        compression_type=ks.producer_compression_type,
        linger_ms=ks.producer_linger_ms,
        batch_size=ks.producer_batch_size,
        max_in_flight=ks.producer_max_in_flight,
        message_timeout_ms=getattr(ks, "producer_message_timeout_ms", 120_000),
        send_wait_s=getattr(ks, "producer_send_wait_s", 5.0),
        delivery_wait_s=getattr(ks, "producer_delivery_wait_s", 30.0),
    )
    consumer = ConsumerTuning(
        enable_auto_commit=ks.consumer_enable_auto_commit,
        auto_offset_reset=ks.consumer_auto_offset_reset,
        max_poll_interval_ms=ks.consumer_max_poll_interval_ms,
        session_timeout_ms=ks.consumer_session_timeout_ms,
        fetch_min_bytes=ks.consumer_fetch_min_bytes,
        fetch_max_bytes=ks.consumer_fetch_max_bytes,
        commit_every_n=ks.consumer_commit_every_n,
        commit_interval_ms=ks.consumer_commit_interval_ms,
        max_concurrency=ks.consumer_max_concurrency,
        inflight_max=ks.consumer_inflight_max,
    )

    # Retry layers parsing
    layers: list[RetryLayer] = []
    raw = ks.retry_layers or ""
    for item in [s.strip() for s in raw.split(",") if s.strip()]:
        try:
            suffix, delay = item.split(":", 1)
            layers.append(RetryLayer(suffix=suffix, delay_ms=int(delay)))
        except Exception:
            continue
    retry = RetryConfig(layers=layers or RetryConfig().layers, dlq_suffix=ks.retry_dlq_suffix)

    kafka = KafkaConfig(
        bootstrap_servers=ks.bootstrap_servers,
        client_id=ks.client_id,
        transactional_id=ks.transactional_id,
        tls=tls,
        sasl=sasl,
        producer=producer,
        consumer=consumer,
        driver="aiokafka" if ks.driver == "aiokafka" else "confluent",
    )
    return MessagingConfig(
        provider=ks.provider,
        kafka=kafka,
        retry=retry,
    )


__all__ = ["messaging_config_from_settings", "KafkaSettingsLike"]
