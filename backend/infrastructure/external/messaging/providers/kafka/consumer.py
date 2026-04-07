from __future__ import annotations

import heapq
import logging
import time
from dataclasses import dataclass
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


def _from_confluent_headers(raw: Optional[List[Tuple[str, bytes]]]) -> Dict[str, bytes]:
    headers: Dict[str, bytes] = {}
    if not raw:
        return headers
    for k, v in raw:
        if isinstance(k, bytes):
            k = k.decode("utf-8")
        headers[k] = v
    return headers


def _to_confluent_headers(headers: dict[str, bytes]) -> List[tuple[str, bytes]]:
    return [(k, v) for k, v in headers.items()]


@dataclass
class _PausedPartition:
    topic: str
    partition: int
    resume_at_ms: int
    offset: int


class KafkaConsumer(Consumer):
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
        self.log = logger or logging.getLogger("messaging.consumer")
        self._group_id: Optional[str] = None
        self._topics: Optional[List[str]] = None
        self._stopped = False
        self._paused_heap: List[Tuple[int, _PausedPartition]] = []  # min-heap by resume_at
        self._assignments: Dict[Tuple[str, int], int] = {}  # tp -> last committed offset (reserved)

        try:
            from confluent_kafka import (
                Consumer as CKConsumer,
                KafkaException,
                TopicPartition,
                Producer,
            )
        except Exception as e:  # noqa: BLE001
            raise ImportError(
                "confluent_kafka is required for KafkaConsumer. Install via `pip install confluent-kafka`."
            ) from e
        self._CKConsumer = CKConsumer
        self._KafkaException = KafkaException
        self._TopicPartition = TopicPartition
        # own producer for requeue (retry/DLQ)
        self._Producer = Producer
        self._consumer = None
        self._producer = None
        self._retry_policy = RetryPolicy(retry)
        self._transactional: bool = bool(self.cfg.transactional_id)

    def _build_consumer(self) -> None:
        conf = {
            "bootstrap.servers": self.cfg.bootstrap_servers,
            "client.id": self.cfg.client_id,
            "group.id": self._group_id or f"{self.cfg.client_id}-group",
            "enable.auto.commit": False,
            "auto.offset.reset": self.cfg.consumer.auto_offset_reset,
            "max.poll.interval.ms": self.cfg.consumer.max_poll_interval_ms,
            "session.timeout.ms": self.cfg.consumer.session_timeout_ms,
            "fetch.min.bytes": self.cfg.consumer.fetch_min_bytes,
            "fetch.max.bytes": self.cfg.consumer.fetch_max_bytes,
        }
        # Set security.protocol consistently for all TLS/SASL combinations
        use_tls = self.cfg.tls.enable
        use_sasl = bool(self.cfg.sasl.mechanism)
        if use_tls:
            security_protocol = "SASL_SSL" if use_sasl else "SSL"
        else:
            security_protocol = "SASL_PLAINTEXT" if use_sasl else "PLAINTEXT"
        conf["security.protocol"] = security_protocol

        if self.cfg.tls.enable:
            conf.update(
                {
                    "ssl.ca.location": self.cfg.tls.ca_location,
                    "ssl.certificate.location": self.cfg.tls.certificate,
                    "ssl.key.location": self.cfg.tls.key,
                    "enable.ssl.certificate.verification": self.cfg.tls.verify,
                }
            )
        if self.cfg.sasl.mechanism:
            conf.update(
                {
                    "sasl.mechanism": self.cfg.sasl.mechanism,
                    "sasl.username": self.cfg.sasl.username,
                    "sasl.password": self.cfg.sasl.password,
                }
            )
        # Enable read_committed only if needed; default stays read_uncommitted
        self._consumer = self._CKConsumer(conf)
        prod_conf = {
            "bootstrap.servers": self.cfg.bootstrap_servers,
            "client.id": self.cfg.client_id + ".consumer-producer",
            "enable.idempotence": True,
            "compression.type": self.cfg.producer.compression_type,
            "linger.ms": self.cfg.producer.linger_ms,
            "acks": self.cfg.producer.acks,
            "max.in.flight.requests.per.connection": self.cfg.producer.max_in_flight,
        }
        # timeout tuning aligned with publisher
        prod_conf["message.timeout.ms"] = self.cfg.producer.message_timeout_ms
        # Use same security.protocol for the producer used by the consumer
        prod_conf["security.protocol"] = security_protocol
        if self.cfg.tls.enable:
            prod_conf.update(
                {
                    "ssl.ca.location": self.cfg.tls.ca_location,
                    "ssl.certificate.location": self.cfg.tls.certificate,
                    "ssl.key.location": self.cfg.tls.key,
                    "enable.ssl.certificate.verification": self.cfg.tls.verify,
                }
            )
        if self.cfg.sasl.mechanism:
            prod_conf.update(
                {
                    "sasl.mechanism": self.cfg.sasl.mechanism,
                    "sasl.username": self.cfg.sasl.username,
                    "sasl.password": self.cfg.sasl.password,
                }
            )
        if self._transactional and self.cfg.transactional_id:
            prod_conf["transactional.id"] = self.cfg.transactional_id
        self._producer = self._Producer(prod_conf)
        # backpressure / delivery wait (seconds)
        self._send_wait_s = self.cfg.producer.send_wait_s
        self._delivery_wait_s = self.cfg.producer.delivery_wait_s
        # Initialize transactions if enabled
        if self._transactional:
            try:
                self._producer.init_transactions()
                self.log.info(
                    "initialized transactional producer",
                    extra={"transactional_id": self.cfg.transactional_id},
                )
            except Exception as e:  # noqa: BLE001
                self.log.error("init_transactions failed", extra={"error": str(e)})
                raise

    def subscribe(self, topics: List[str], group_id: str) -> None:
        self._topics = topics
        self._group_id = group_id

    def _resume_due_partitions(self) -> None:
        if not self._paused_heap or not self._consumer:
            return
        now = now_ms()
        to_resume: List[Tuple[int, _PausedPartition]] = []
        while self._paused_heap and self._paused_heap[0][0] <= now:
            _, p = heapq.heappop(self._paused_heap)
            to_resume.append((0, p))
        if not to_resume:
            return
        tps = [self._TopicPartition(p.topic, p.partition, p.offset) for _, p in to_resume]
        try:
            self._consumer.resume(tps)
            self.log.debug("resumed partitions", extra={"count": len(tps)})
        except Exception:
            pass

    def _pause_partition_until(
        self, topic: str, partition: int, offset: int, resume_at_ms: int
    ) -> None:
        if not self._consumer:
            return
        tp = self._TopicPartition(topic, partition, offset)
        try:
            self._consumer.pause([tp])
            # ensure we will start from the current message when resumed
            self._consumer.seek(tp)
            heapq.heappush(
                self._paused_heap,
                (resume_at_ms, _PausedPartition(topic, partition, resume_at_ms, offset)),
            )
            self.log.debug(
                "paused partition",
                extra={
                    "topic": topic,
                    "partition": partition,
                    "offset": offset,
                    "resume_at": resume_at_ms,
                },
            )
        except Exception as e:  # noqa: BLE001
            self.log.error("pause/seek failed", extra={"error": str(e)})

    def start(self, handler: Consumer.Handler) -> None:
        if not self._topics or not self._group_id:
            raise RuntimeError("Call subscribe(topics, group_id) before start().")
        self._build_consumer()
        assert self._consumer is not None and self._producer is not None
        # Register rebalance callbacks for safer commits on reassignments
        self._consumer.subscribe(self._topics, on_assign=self._on_assign, on_revoke=self._on_revoke)
        commit_n = self.cfg.consumer.commit_every_n
        commit_interval = self.cfg.consumer.commit_interval_ms / 1000.0
        last_commit_time = time.monotonic()
        processed_since_commit = 0

        try:
            while not self._stopped:
                # Resume due partitions
                self._resume_due_partitions()

                msg = self._consumer.poll(timeout=0.5)
                if msg is None:
                    # periodic commit by time
                    now_t = time.monotonic()
                    if processed_since_commit and (now_t - last_commit_time) >= commit_interval:
                        try:
                            self._consumer.commit(asynchronous=False)
                            processed_since_commit = 0
                            last_commit_time = now_t
                        except Exception:
                            pass
                    continue
                if msg.error():
                    # log and continue
                    self.log.error("consumer error", extra={"error": str(msg.error())})
                    continue

                topic = msg.topic()
                partition = msg.partition()
                offset = msg.offset()
                headers = _from_confluent_headers(msg.headers())
                value = msg.value()
                key = msg.key()

                # delay check before handler
                not_before = headers.get(H_RETRY_NOT_BEFORE)
                if not_before is not None:
                    try:
                        ts = int(not_before.decode("ascii"))
                    except Exception:
                        ts = None  # type: ignore
                    if ts is not None and ts > now_ms():
                        self._pause_partition_until(topic, partition, offset, ts)
                        continue

                # deserialize
                try:
                    payload = (
                        value if value is None or isinstance(value, (bytes, bytearray)) else value
                    )
                    if value is not None:
                        payload = self.serializer.loads(value)
                except Exception as e:  # noqa: BLE001
                    # deserialization error -> DLQ
                    decision_topic = f"{topic}.{self.retry_cfg.dlq_suffix}"
                    headers[H_ERROR_CLASS] = b"SerializationError"
                    headers[H_ERROR_MSG] = str(e).encode("utf-8")[:2048]
                    if self._transactional:
                        try:
                            self._producer.begin_transaction()
                            self._producer.produce(
                                topic=decision_topic,
                                key=key,
                                value=value,
                                headers=_to_confluent_headers(headers),
                            )
                            offsets = [self._TopicPartition(topic, partition, offset + 1)]
                            self._producer.send_offsets_to_transaction(offsets, self._consumer)
                            self._producer.commit_transaction()
                        except Exception:
                            try:
                                self._producer.abort_transaction()
                            except Exception:
                                pass
                        continue
                    else:
                        self._requeue(decision_topic, key, value, headers)
                        self._consumer.commit(asynchronous=False)
                        continue

                env = Envelope(payload=payload, key=key, headers=headers)
                # middlewares before
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
                    # default retry on unexpected errors
                    result = HandleResult.RETRY
                    err = e

                try:
                    if result == HandleResult.ACK:
                        processed_since_commit += 1
                        # track last processed offset; used for commit on revoke
                        self._assignments[(topic, partition)] = offset + 1
                    elif result == HandleResult.RETRY:
                        if self._transactional:
                            self._handle_retry_txn(
                                topic, partition, offset, key, value, headers, err
                            )
                        else:
                            self._handle_retry(topic, key, value, headers, err)
                            # commit this partition's offset immediately to avoid duplicate requeue
                            try:
                                tp = [self._TopicPartition(topic, partition, offset + 1)]
                                self._consumer.commit(offsets=tp, asynchronous=False)
                            except Exception:
                                pass
                            self._assignments[(topic, partition)] = offset + 1
                    elif result == HandleResult.DROP:
                        if self._transactional:
                            self._handle_drop_txn(
                                topic, partition, offset, key, value, headers, err
                            )
                        else:
                            self._handle_drop(topic, key, value, headers, err)
                            try:
                                tp = [self._TopicPartition(topic, partition, offset + 1)]
                                self._consumer.commit(offsets=tp, asynchronous=False)
                            except Exception:
                                pass
                            self._assignments[(topic, partition)] = offset + 1
                finally:
                    for m in self.middlewares:
                        m.after_handle(topic, partition, offset, env, result, err)

                # commit by count
                if processed_since_commit >= commit_n:
                    try:
                        self._consumer.commit(asynchronous=False)
                        processed_since_commit = 0
                        last_commit_time = time.monotonic()
                    except Exception:
                        pass

        finally:
            try:
                self._consumer.commit(asynchronous=False)
            except Exception:
                pass
            self.stop()

    # Rebalance callbacks
    def _on_assign(self, consumer, partitions):  # type: ignore[no-redef]
        # Clear paused heap and reset assignment tracking for these partitions
        self._paused_heap.clear()
        for tp in partitions:
            self._assignments.pop((tp.topic, tp.partition), None)
        try:
            consumer.assign(partitions)
            self.log.info("assigned", extra={"count": len(partitions)})
        except Exception as e:  # noqa: BLE001
            self.log.error("on_assign failed", extra={"error": str(e)})

    def _on_revoke(self, consumer, partitions):  # type: ignore[no-redef]
        # On revoke, synchronously commit last processed offsets (non-transactional)
        if not self._transactional:
            to_commit = []
            for tp in partitions:
                nxt = self._assignments.get((tp.topic, tp.partition))
                if nxt is not None:
                    to_commit.append(self._TopicPartition(tp.topic, tp.partition, nxt))
            if to_commit:
                try:
                    consumer.commit(offsets=to_commit, asynchronous=False)
                except Exception as e:  # noqa: BLE001
                    self.log.error(
                        "commit on revoke failed", extra={"error": str(e), "count": len(to_commit)}
                    )
        try:
            consumer.unassign()
        except Exception:
            pass

    def _requeue(
        self, topic: str, key: Optional[bytes], value: Optional[bytes], headers: Dict[str, bytes]
    ) -> None:
        assert self._producer is not None
        done: Dict[str, Optional[str]] = {"ok": None, "err": None}

        def _on_delivery(err, msg):  # type: ignore
            if err is not None:
                done["ok"], done["err"] = "0", str(err)
            else:
                done["ok"], done["err"] = "1", None

        # backpressure-aware produce with deadline
        import time as _t

        send_deadline = _t.monotonic() + self._send_wait_s
        while True:
            try:
                self._producer.produce(
                    topic=topic,
                    key=key,
                    value=value,
                    headers=_to_confluent_headers(headers),
                    on_delivery=_on_delivery,
                )
                break
            except BufferError:
                self._producer.poll(0.1)
                if _t.monotonic() >= send_deadline:
                    raise

        # wait only for this record's delivery
        deadline = _t.monotonic() + self._delivery_wait_s
        while done["ok"] is None and _t.monotonic() < deadline:
            self._producer.poll(0.05)
        if done["ok"] != "1":
            raise RuntimeError(f"Requeue delivery failed: {done['err']}")

    def _handle_retry(
        self,
        current_topic: str,
        key: Optional[bytes],
        value: Optional[bytes],
        headers: Dict[str, bytes],
        err: Optional[BaseException],
    ) -> None:
        decision = self._retry_policy.next_for_retry(current_topic)
        ensure_original_topic(headers, current_topic)
        bump_attempts(headers)
        if not decision.is_dlq:
            set_not_before_ms(headers, now_ms() + decision.delay_ms)
        if err is not None:
            headers[H_ERROR_CLASS] = type(err).__name__.encode("utf-8")
            headers[H_ERROR_MSG] = str(err).encode("utf-8")[:2048]
        self._requeue(decision.next_topic, key, value, headers)

    def _handle_retry_txn(
        self,
        current_topic: str,
        partition: int,
        offset: int,
        key: Optional[bytes],
        value: Optional[bytes],
        headers: Dict[str, bytes],
        err: Optional[BaseException],
    ) -> None:
        assert self._producer is not None and self._consumer is not None
        decision = self._retry_policy.next_for_retry(current_topic)
        ensure_original_topic(headers, current_topic)
        bump_attempts(headers)
        if not decision.is_dlq:
            set_not_before_ms(headers, now_ms() + decision.delay_ms)
        if err is not None:
            headers[H_ERROR_CLASS] = type(err).__name__.encode("utf-8")
            headers[H_ERROR_MSG] = str(err).encode("utf-8")[:2048]
        try:
            self._producer.begin_transaction()
            self._producer.produce(
                topic=decision.next_topic,
                key=key,
                value=value,
                headers=_to_confluent_headers(headers),
            )
            # Commit the source offset as part of the transaction (offset+1)
            offsets = [self._TopicPartition(current_topic, partition, offset + 1)]
            self._producer.send_offsets_to_transaction(offsets, self._consumer)
            self._producer.commit_transaction()
        except Exception as e:  # noqa: BLE001
            try:
                self._producer.abort_transaction()
            except Exception:
                pass
            # Let the message be reprocessed (offset not committed)
            self.log.error("transactional retry failed", extra={"error": str(e)})

    def _handle_drop(
        self,
        current_topic: str,
        key: Optional[bytes],
        value: Optional[bytes],
        headers: Dict[str, bytes],
        err: Optional[BaseException],
    ) -> None:
        dlq_topic = f"{current_topic}.{self.retry_cfg.dlq_suffix}"
        if err is not None:
            headers[H_ERROR_CLASS] = type(err).__name__.encode("utf-8")
            headers[H_ERROR_MSG] = str(err).encode("utf-8")[:2048]
        self._requeue(dlq_topic, key, value, headers)

    def _handle_drop_txn(
        self,
        current_topic: str,
        partition: int,
        offset: int,
        key: Optional[bytes],
        value: Optional[bytes],
        headers: Dict[str, bytes],
        err: Optional[BaseException],
    ) -> None:
        assert self._producer is not None and self._consumer is not None
        dlq_topic = f"{current_topic}.{self.retry_cfg.dlq_suffix}"
        if err is not None:
            headers[H_ERROR_CLASS] = type(err).__name__.encode("utf-8")
            headers[H_ERROR_MSG] = str(err).encode("utf-8")[:2048]
        try:
            self._producer.begin_transaction()
            self._producer.produce(
                topic=dlq_topic,
                key=key,
                value=value,
                headers=_to_confluent_headers(headers),
            )
            offsets = [self._TopicPartition(current_topic, partition, offset + 1)]
            self._producer.send_offsets_to_transaction(offsets, self._consumer)
            self._producer.commit_transaction()
        except Exception as e:  # noqa: BLE001
            try:
                self._producer.abort_transaction()
            except Exception:
                pass
            self.log.error("transactional drop failed", extra={"error": str(e)})

    def stop(self) -> None:
        self._stopped = True
        try:
            if self._consumer is not None:
                self._consumer.close()
        except Exception:
            pass
        try:
            if self._producer is not None:
                self._producer.flush(5)
        except Exception:
            pass
