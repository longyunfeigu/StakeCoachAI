from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ..config import RetryConfig


@dataclass(slots=True)
class RetryDecision:
    next_topic: str
    delay_ms: int
    is_dlq: bool


class RetryPolicy:
    def __init__(self, cfg: RetryConfig) -> None:
        self.cfg = cfg

    def analyze_topic(self, topic: str) -> Tuple[str, Optional[int]]:
        for idx, layer in enumerate(self.cfg.layers):
            suf = "." + layer.suffix
            if topic.endswith(suf):
                return topic[: -len(suf)], idx
        suf_dlq = "." + self.cfg.dlq_suffix
        if topic.endswith(suf_dlq):
            return topic[: -len(suf_dlq)], len(self.cfg.layers)
        return topic, None

    def next_for_retry(self, current_topic: str) -> RetryDecision:
        main, idx = self.analyze_topic(current_topic)
        if idx is None:
            layer = self.cfg.layers[0]
            return RetryDecision(
                next_topic=f"{main}.{layer.suffix}", delay_ms=layer.delay_ms, is_dlq=False
            )
        if idx < len(self.cfg.layers) - 1:
            layer = self.cfg.layers[idx + 1]
            return RetryDecision(
                next_topic=f"{main}.{layer.suffix}", delay_ms=layer.delay_ms, is_dlq=False
            )
        return RetryDecision(next_topic=f"{main}.{self.cfg.dlq_suffix}", delay_ms=0, is_dlq=True)
