from __future__ import annotations

from typing import List, Optional

from ...base import Envelope, PublishMiddleware, PublishResult, Publisher, Serializer
from ...config import KafkaConfig
from ._loop import LoopThread


def _to_headers(headers: dict[str, bytes]) -> List[tuple[str, bytes]]:
    return [(k, v) for k, v in headers.items()]


class AiokafkaPublisher(Publisher):
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
            from aiokafka import AIOKafkaProducer  # type: ignore
        except Exception as e:  # noqa: BLE001
            raise ImportError(
                "aiokafka is required for AiokafkaPublisher. Install via `pip install aiokafka`."
            ) from e
        self._AIOKafkaProducer = AIOKafkaProducer
        self._loop = LoopThread()
        self._loop.start()
        self._producer = self._loop.run_coro(self._create_producer())

    async def _create_producer(self):
        from aiokafka import AIOKafkaProducer
        import ssl

        use_tls = self.cfg.tls.enable
        use_sasl = bool(self.cfg.sasl.mechanism)
        if use_tls:
            security_protocol = "SASL_SSL" if use_sasl else "SSL"
        else:
            security_protocol = "SASL_PLAINTEXT" if use_sasl else "PLAINTEXT"

        ssl_context = None
        if use_tls:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            if self.cfg.tls.verify:
                ctx.verify_mode = ssl.CERT_REQUIRED
                try:
                    if self.cfg.tls.ca_location:
                        ctx.load_verify_locations(cafile=self.cfg.tls.ca_location)
                    else:
                        ctx.load_default_certs()
                except Exception:
                    ctx.load_default_certs()
            else:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            if self.cfg.tls.certificate and self.cfg.tls.key:
                ctx.load_cert_chain(certfile=self.cfg.tls.certificate, keyfile=self.cfg.tls.key)
            ssl_context = ctx

        producer = AIOKafkaProducer(
            bootstrap_servers=self.cfg.bootstrap_servers,
            client_id=self.cfg.client_id,
            compression_type=self.cfg.producer.compression_type,
            linger_ms=self.cfg.producer.linger_ms,
            batch_size=self.cfg.producer.batch_size,
            acks=self.cfg.producer.acks,
            max_in_flight_requests_per_connection=self.cfg.producer.max_in_flight,
            security_protocol=security_protocol,
            ssl_context=ssl_context,
            sasl_mechanism=self.cfg.sasl.mechanism,
            sasl_plain_username=self.cfg.sasl.username,
            sasl_plain_password=self.cfg.sasl.password,
        )
        await producer.start()
        return producer

    def publish(self, topic: str, env: Envelope) -> PublishResult:
        for m in self.middlewares:
            env = m.before_publish(topic, env)
        value_bytes = (
            env.payload
            if isinstance(env.payload, (bytes, bytearray))
            else self.serializer.dumps(env.payload)
        )
        key = env.key

        async def _send():
            md = await self._producer.send_and_wait(
                topic, value=value_bytes, key=key, headers=_to_headers(env.headers)
            )
            return md

        md = self._loop.run_coro(_send())
        result = PublishResult(
            topic=topic, partition=md.partition, offset=md.offset, timestamp=None
        )
        for m in self.middlewares:
            m.after_publish(topic, env, result)
        return result

    def close(self) -> None:
        async def _stop():
            await self._producer.stop()

        try:
            self._loop.run_coro(_stop())
        finally:
            self._loop.stop()
