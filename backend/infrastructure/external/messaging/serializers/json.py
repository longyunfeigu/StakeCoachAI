from __future__ import annotations

import json
from typing import Any

from ..exceptions import SerializationError


class JsonSerializer:
    def dumps(self, obj: Any) -> bytes:
        try:
            return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        except Exception as e:  # noqa: BLE001
            raise SerializationError(str(e)) from e

    def loads(self, data: bytes) -> Any:
        try:
            return json.loads(data.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            raise SerializationError(str(e)) from e
