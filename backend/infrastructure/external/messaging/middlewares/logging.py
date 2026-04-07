from __future__ import annotations

import logging
from typing import Optional

from ..base import ConsumeMiddleware, Envelope, HandleResult, PublishMiddleware, PublishResult


class LoggingMiddleware(PublishMiddleware, ConsumeMiddleware):
    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.log = logger or logging.getLogger("messaging")

    def before_publish(self, topic: str, env: Envelope) -> Envelope:  # type: ignore[override]
        self.log.debug(
            "publishing",
            extra={
                "topic": topic,
                "key": (env.key or b"").hex(),
                "headers": list(env.headers.keys()),
            },
        )
        return env

    def after_publish(self, topic: str, env: Envelope, result: PublishResult) -> None:  # type: ignore[override]
        self.log.info(
            "published",
            extra={
                "topic": topic,
                "partition": result.partition,
                "offset": result.offset,
                "key": (env.key or b"").hex(),
            },
        )

    def before_handle(self, topic: str, partition: int, offset: int, env: Envelope) -> Envelope:  # type: ignore[override]
        self.log.debug(
            "handling",
            extra={
                "topic": topic,
                "partition": partition,
                "offset": offset,
                "headers": list(env.headers.keys()),
            },
        )
        return env

    def after_handle(
        self,
        topic: str,
        partition: int,
        offset: int,
        env: Envelope,
        result: HandleResult,
        exc: Optional[BaseException] = None,
    ) -> None:  # type: ignore[override]
        level = logging.ERROR if exc else logging.INFO
        self.log.log(
            level,
            "handled",
            extra={
                "topic": topic,
                "partition": partition,
                "offset": offset,
                "result": result.value,
                "error": str(exc) if exc else None,
            },
        )
