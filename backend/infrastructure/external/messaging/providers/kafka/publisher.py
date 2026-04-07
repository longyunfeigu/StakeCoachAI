from __future__ import annotations

from typing import Iterable, List, Optional
import time

from ...base import Envelope, PublishMiddleware, PublishResult, Publisher, Serializer
from ...config import KafkaConfig
from ...exceptions import PublishError


def _to_confluent_headers(headers: dict[str, bytes]) -> List[tuple[str, bytes]]:
    return [(k, v) for k, v in headers.items()]


class KafkaPublisher(Publisher):
    def __init__(
        self,
        cfg: KafkaConfig,
        serializer: Serializer,
        middlewares: Optional[List[PublishMiddleware]] = None,
    ) -> None:
        self.cfg = cfg
        self.serializer = serializer
        self.middlewares = middlewares or []
        try:
            from confluent_kafka import Producer  # type: ignore
        except Exception as e:  # noqa: BLE001
            raise ImportError(
                "confluent_kafka is required for KafkaPublisher. Install via `pip install confluent-kafka`."
            ) from e

        conf: dict = {
            "bootstrap.servers": cfg.bootstrap_servers,
            "client.id": cfg.client_id,
            "enable.idempotence": cfg.producer.enable_idempotence,
            "compression.type": cfg.producer.compression_type,
            "linger.ms": cfg.producer.linger_ms,
            "acks": cfg.producer.acks,
            "message.send.max.retries": 10,
            "max.in.flight.requests.per.connection": cfg.producer.max_in_flight,
        }
        # batching/timeout tuning (safe defaults)
        # Prefer message.timeout.ms over deprecated delivery.timeout.ms
        conf["message.timeout.ms"] = cfg.producer.message_timeout_ms
        # Set security.protocol consistently for all combos of TLS/SASL
        use_tls = cfg.tls.enable
        use_sasl = bool(cfg.sasl.mechanism)
        if use_tls:
            security_protocol = "SASL_SSL" if use_sasl else "SSL"
        else:
            security_protocol = "SASL_PLAINTEXT" if use_sasl else "PLAINTEXT"
        conf["security.protocol"] = security_protocol

        if cfg.tls.enable:
            conf.update(
                {
                    "ssl.ca.location": cfg.tls.ca_location,
                    "ssl.certificate.location": cfg.tls.certificate,
                    "ssl.key.location": cfg.tls.key,
                    "enable.ssl.certificate.verification": cfg.tls.verify,
                }
            )
        if cfg.sasl.mechanism:
            conf.update(
                {
                    "sasl.mechanism": cfg.sasl.mechanism,
                    "sasl.username": cfg.sasl.username,
                    "sasl.password": cfg.sasl.password,
                }
            )
        self._Producer = Producer
        self._producer = Producer(conf)
        # local timeouts for backpressure and delivery waiting (seconds)
        self._send_wait_s = cfg.producer.send_wait_s
        self._delivery_wait_s = cfg.producer.delivery_wait_s

    def publish(self, topic: str, env: Envelope) -> PublishResult:
        # middlewares before
        for m in self.middlewares:
            env = m.before_publish(topic, env)

        value_bytes = (
            env.payload
            if isinstance(env.payload, (bytes, bytearray))
            else self.serializer.dumps(env.payload)
        )
        key = env.key

        meta_holder: dict = {}

        def _delivery(err, msg):  # type: ignore[no-redef]
            if err is not None:
                meta_holder["error"] = err
            else:
                meta_holder["result"] = PublishResult(
                    topic=msg.topic(),
                    partition=msg.partition(),
                    offset=msg.offset(),
                    timestamp=msg.timestamp()[1],
                )

        # Backpressure handling: retry on BufferError after polling, with deadline
        send_deadline = time.monotonic() + self._send_wait_s
        while True:
            try:
                self._producer.produce(
                    topic=topic,
                    key=key,
                    value=bytes(value_bytes),
                    headers=_to_confluent_headers(env.headers),
                    on_delivery=_delivery,
                )
                break
            except BufferError:
                # allow delivery callbacks to run and free queue space
                self._producer.poll(0.1)
                if time.monotonic() >= send_deadline:
                    raise PublishError("Producer queue full: timed out while retrying produce()")

        # Wait only for this message's delivery callback (do not flush all)
        delivery_deadline = time.monotonic() + self._delivery_wait_s
        while "error" not in meta_holder and "result" not in meta_holder:
            self._producer.poll(0.05)
            if time.monotonic() >= delivery_deadline:
                raise PublishError("Delivery wait timeout for produced message")

        if "error" in meta_holder:
            raise PublishError(str(meta_holder["error"]))
        result = meta_holder.get("result")
        if not result:
            raise PublishError("No delivery report")

        for m in self.middlewares:
            m.after_publish(topic, env, result)
        return result

    def publish_many(self, topic: str, envs: Iterable[Envelope]) -> List[PublishResult]:  # type: ignore[override]
        # Pre-size results for stable ordering
        env_list = list(envs)
        results: List[Optional[PublishResult]] = [None] * len(env_list)
        errors: list[str] = []

        def make_cb(i: int):
            def _delivery(err, msg):  # type: ignore
                if err is not None:
                    errors.append(str(err))
                else:
                    results[i] = PublishResult(
                        topic=msg.topic(),
                        partition=msg.partition(),
                        offset=msg.offset(),
                        timestamp=msg.timestamp()[1],
                    )

            return _delivery

        # before middlewares per message
        processed_envs: List[Envelope] = []
        for env in env_list:
            e = env
            for m in self.middlewares:
                e = m.before_publish(topic, e)
            processed_envs.append(e)

        for i, env in enumerate(processed_envs):
            value_bytes = (
                env.payload
                if isinstance(env.payload, (bytes, bytearray))
                else self.serializer.dumps(env.payload)
            )
            key = env.key

            while True:
                try:
                    self._producer.produce(
                        topic=topic,
                        key=key,
                        value=bytes(value_bytes),
                        headers=_to_confluent_headers(env.headers),
                        on_delivery=make_cb(i),
                    )
                    break
                except BufferError:
                    self._producer.poll(0.1)

        # Flush once at the end
        self._producer.flush()

        if errors:
            raise PublishError("; ".join(errors[:3]) + (" ..." if len(errors) > 3 else ""))

        # after middlewares
        for i, env in enumerate(processed_envs):
            assert results[i] is not None
            for m in self.middlewares:
                m.after_publish(topic, env, results[i])  # type: ignore[arg-type]
        return [r for r in results if r is not None]

    def close(self) -> None:
        try:
            self._producer.flush(5)
        except Exception:
            pass
