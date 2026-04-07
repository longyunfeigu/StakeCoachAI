# input: asyncio.Queue
# output: RoomEventBus SSE 事件总线
# owner: wanhua.gu
# pos: 应用层 - 聊天室 SSE 事件发布/订阅总线；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""SSE event bus for stakeholder chat rooms.

Each room has a set of subscriber queues. When an event is published,
it's pushed to all active subscribers for that room.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any


class RoomEventBus:
    """In-memory pub/sub for SSE events, keyed by room_id."""

    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, room_id: int) -> asyncio.Queue:
        """Create a new subscriber queue for a room."""
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[room_id].add(queue)
        return queue

    def unsubscribe(self, room_id: int, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        self._subscribers[room_id].discard(queue)
        if not self._subscribers[room_id]:
            del self._subscribers[room_id]

    async def publish(self, room_id: int, event: str, data: Any) -> None:
        """Push an event to all subscribers of a room."""
        for queue in list(self._subscribers.get(room_id, [])):
            await queue.put((event, data))


def format_sse(event: str, data: Any) -> str:
    """Format a Server-Sent Event string."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# Singleton event bus
room_event_bus = RoomEventBus()
