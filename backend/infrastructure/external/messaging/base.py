from __future__ import annotations

import abc
import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol


Headers = Dict[str, bytes]


@dataclass(slots=True)
class Envelope:
    payload: Any
    key: Optional[bytes] = None
    headers: Headers = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "v1"


@dataclass(slots=True)
class PublishResult:
    topic: str
    partition: int
    offset: int
    timestamp: Optional[int] = None


class HandleResult(enum.Enum):
    ACK = "ACK"
    RETRY = "RETRY"
    DROP = "DROP"


class Serializer(Protocol):
    def dumps(self, obj: Any) -> bytes: ...

    def loads(self, data: bytes) -> Any: ...


class PublishMiddleware(Protocol):
    def before_publish(self, topic: str, env: Envelope) -> Envelope: ...

    def after_publish(self, topic: str, env: Envelope, result: PublishResult) -> None: ...


class ConsumeMiddleware(Protocol):
    def before_handle(self, topic: str, partition: int, offset: int, env: Envelope) -> Envelope: ...

    def after_handle(
        self,
        topic: str,
        partition: int,
        offset: int,
        env: Envelope,
        result: HandleResult,
        exc: Optional[BaseException] = None,
    ) -> None: ...


class Publisher(abc.ABC):
    @abc.abstractmethod
    def publish(self, topic: str, env: Envelope) -> PublishResult: ...

    def publish_many(self, topic: str, envs: Iterable[Envelope]) -> List[PublishResult]:
        results: List[PublishResult] = []
        for env in envs:
            results.append(self.publish(topic, env))
        return results

    @abc.abstractmethod
    def close(self) -> None: ...


class Consumer(abc.ABC):
    Handler = Callable[[Envelope], HandleResult]

    @abc.abstractmethod
    def subscribe(self, topics: List[str], group_id: str) -> None: ...

    @abc.abstractmethod
    def start(self, handler: Handler) -> None: ...

    @abc.abstractmethod
    def stop(self) -> None: ...
