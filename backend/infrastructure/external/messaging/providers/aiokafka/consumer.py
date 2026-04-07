from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from ...base import ConsumeMiddleware, Consumer, Envelope, HandleResult, Serializer
from ...config import KafkaConfig, RetryConfig
from ...exceptions import NonRetryableError, RetryableError
from ...middlewares.retry import RetryPolicy
from ...envelope import (
    H_ERROR_CLASS,
    H_ERROR_MSG,
    H_RETRY_NOT_BEFORE,
    bump_attempts,
    ensure_original_topic,
    now_ms,
    set_not_before_ms,
)
from ._loop import LoopThread


def _from_headers(raw: Optional[List[tuple[str, bytes]]]) -> Dict[str, bytes]:
    headers: Dict[str, bytes] = {}
    if not raw:
        return headers
    for k, v in raw:
        headers[k] = v
    return headers


def _to_headers(headers: Dict[str, bytes]) -> List[tuple[str, bytes]]:
    return [(k, v) for k, v in headers.items()]


class AiokafkaConsumer(Consumer):
    def __init__(
        self,
        cfg: KafkaConfig,
        retry: RetryConfig,
        serializer: Serializer,
        middlewares: Optional[List[ConsumeMiddleware]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.cfg = cfg
        self.retry_cfg = retry
        self.serializer = serializer
        self.middlewares = middlewares or []
        self.log = logger or logging.getLogger("messaging.aiokafka.consumer")
        self._group_id: Optional[str] = None
        self._topics: Optional[List[str]] = None
        self._stopped = False
        self._retry_policy = RetryPolicy(retry)
        self._assignments: Dict[Tuple[str, int], int] = {}
        self._delivery_wait_s: float = self.cfg.producer.delivery_wait_s
        try:
            from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # type: ignore
        except Exception as e:  # noqa: BLE001
            raise ImportError(
                "aiokafka is required for AiokafkaConsumer. Install via `pip install aiokafka`."
            ) from e
        self._AIOKafkaConsumer = AIOKafkaConsumer
        self._AIOKafkaProducer = AIOKafkaProducer
        self._loop = LoopThread()
        self._consumer = None
        self._producer = None

    def subscribe(self, topics: List[str], group_id: str) -> None:
        self._topics = topics
        self._group_id = group_id

    def start(self, handler: Consumer.Handler) -> None:
        if not self._topics or not self._group_id:
            raise RuntimeError("Call subscribe(topics, group_id) before start().")

        self._loop.start()

        async def _run():
            # Lazy imports to avoid hard dependency unless this path is used
            from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
            import ssl
            import asyncio

            # TLS/SASL configuration
            use_tls = self.cfg.tls.enable
            use_sasl = bool(self.cfg.sasl.mechanism)
            if use_tls:
                security_protocol = "SASL_SSL" if use_sasl else "SSL"
            else:
                security_protocol = "SASL_PLAINTEXT" if use_sasl else "PLAINTEXT"

            ssl_context = None
            if use_tls:
                # Build SSL context from provided files and verify flag
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                if self.cfg.tls.verify:
                    ctx.verify_mode = ssl.CERT_REQUIRED
                    try:
                        if self.cfg.tls.ca_location:
                            ctx.load_verify_locations(cafile=self.cfg.tls.ca_location)
                        else:
                            ctx.load_default_certs()
                    except Exception:
                        # Fall back to default certs if custom CA load fails
                        ctx.load_default_certs()
                else:
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                if self.cfg.tls.certificate and self.cfg.tls.key:
                    ctx.load_cert_chain(certfile=self.cfg.tls.certificate, keyfile=self.cfg.tls.key)
                ssl_context = ctx

            self._consumer = AIOKafkaConsumer(
                bootstrap_servers=self.cfg.bootstrap_servers,
                group_id=self._group_id,
                enable_auto_commit=False,
                auto_offset_reset=self.cfg.consumer.auto_offset_reset,
                security_protocol=security_protocol,
                ssl_context=ssl_context,
                sasl_mechanism=self.cfg.sasl.mechanism,
                sasl_plain_username=self.cfg.sasl.username,
                sasl_plain_password=self.cfg.sasl.password,
            )
            await self._consumer.start()
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.cfg.bootstrap_servers,
                client_id=self.cfg.client_id + ".consumer-producer",
                compression_type=self.cfg.producer.compression_type,
                security_protocol=security_protocol,
                ssl_context=ssl_context,
                sasl_mechanism=self.cfg.sasl.mechanism,
                sasl_plain_username=self.cfg.sasl.username,
                sasl_plain_password=self.cfg.sasl.password,
            )
            await self._producer.start()

            # Register rebalance listener and subscribe to topics
            class _Listener:
                def __init__(self, parent, tp_cls):
                    self.parent = parent
                    self.TopicPartition = tp_cls

                def on_partitions_assigned(self, assigned):
                    # Clear tracked offsets for assigned tps
                    for tp in assigned:
                        self.parent._assignments.pop((tp.topic, tp.partition), None)

                def on_partitions_revoked(self, revoked):
                    # Commit last processed offsets for revoked tps (best-effort)
                    mapping = {}
                    for tp in revoked:
                        nxt = self.parent._assignments.get((tp.topic, tp.partition))
                        if nxt is not None:
                            mapping[self.TopicPartition(tp.topic, tp.partition)] = nxt
                    if mapping:

                        async def _commit():
                            try:
                                await self.parent._consumer.commit(offsets=mapping)
                            except Exception:
                                pass

                        asyncio.create_task(_commit())

            listener = _Listener(self, TopicPartition)
            self._consumer.subscribe(self._topics, listener=listener)

            try:
                while not self._stopped:
                    msg = await self._consumer.getone()
                    topic = msg.topic
                    partition = msg.partition
                    offset = msg.offset
                    headers = _from_headers(msg.headers)
                    value = msg.value
                    key = msg.key

                    not_before = headers.get(H_RETRY_NOT_BEFORE)
                    if not_before is not None:
                        try:
                            ts = int(not_before.decode("ascii"))
                        except Exception:
                            ts = None  # type: ignore
                        if ts is not None and ts > now_ms():
                            # pause and seek this partition until ts
                            tp = TopicPartition(msg.topic, msg.partition)
                            # pause expects a list of TopicPartition
                            self._consumer.pause([tp])
                            # seek to current offset so message will be consumed later
                            self._consumer.seek(tp, msg.offset)
                            # naive sleep until due
                            delay = max(0, (ts - now_ms()) / 1000.0)
                            await asyncio.sleep(delay)
                            self._consumer.resume([tp])
                            continue

                    try:
                        payload = self.serializer.loads(value) if value is not None else None
                    except Exception as e:  # noqa: BLE001
                        dlq = f"{topic}.{self.retry_cfg.dlq_suffix}"
                        headers[H_ERROR_CLASS] = b"SerializationError"
                        headers[H_ERROR_MSG] = str(e).encode("utf-8")[:2048]
                        try:
                            await asyncio.wait_for(
                                self._producer.send_and_wait(
                                    dlq, value=value, key=key, headers=_to_headers(headers)
                                ),
                                timeout=self._delivery_wait_s,
                            )
                            await self._consumer.commit()
                            self._assignments[(topic, partition)] = offset + 1
                        except Exception:
                            pass
                        continue

                    env = Envelope(payload=payload, key=key, headers=headers)
                    for m in self.middlewares:
                        env = m.before_handle(topic, partition, offset, env)

                    result = HandleResult.ACK
                    err: Optional[BaseException] = None
                    try:
                        result = handler(env)
                    except RetryableError as e:
                        result = HandleResult.RETRY
                        err = e
                    except NonRetryableError as e:
                        result = HandleResult.DROP
                        err = e
                    except Exception as e:  # noqa: BLE001
                        result = HandleResult.RETRY
                        err = e

                    try:
                        if result == HandleResult.ACK:
                            await self._consumer.commit()
                            self._assignments[(topic, partition)] = offset + 1
                        elif result == HandleResult.RETRY:
                            decision = self._retry_policy.next_for_retry(topic)
                            ensure_original_topic(headers, topic)
                            bump_attempts(headers)
                            if not decision.is_dlq:
                                set_not_before_ms(headers, now_ms() + decision.delay_ms)
                            if err is not None:
                                headers[H_ERROR_CLASS] = type(err).__name__.encode("utf-8")
                                headers[H_ERROR_MSG] = str(err).encode("utf-8")[:2048]
                            try:
                                await asyncio.wait_for(
                                    self._producer.send_and_wait(
                                        decision.next_topic,
                                        value=value,
                                        key=key,
                                        headers=_to_headers(headers),
                                    ),
                                    timeout=self._delivery_wait_s,
                                )
                                await self._consumer.commit()
                                self._assignments[(topic, partition)] = offset + 1
                            except Exception:
                                pass
                        elif result == HandleResult.DROP:
                            dlq = f"{topic}.{self.retry_cfg.dlq_suffix}"
                            if err is not None:
                                headers[H_ERROR_CLASS] = type(err).__name__.encode("utf-8")
                                headers[H_ERROR_MSG] = str(err).encode("utf-8")[:2048]
                            try:
                                await asyncio.wait_for(
                                    self._producer.send_and_wait(
                                        dlq, value=value, key=key, headers=_to_headers(headers)
                                    ),
                                    timeout=self._delivery_wait_s,
                                )
                                await self._consumer.commit()
                                self._assignments[(topic, partition)] = offset + 1
                            except Exception:
                                pass
                    finally:
                        for m in self.middlewares:
                            m.after_handle(topic, partition, offset, env, result, err)

            finally:
                try:
                    await self._consumer.stop()
                except Exception:
                    pass
                try:
                    await self._producer.stop()
                except Exception:
                    pass

        # import asyncio here to avoid top-level dep if unused
        import asyncio

        self._loop.run_coro(_run())

    def stop(self) -> None:
        self._stopped = True
        self._loop.stop()
