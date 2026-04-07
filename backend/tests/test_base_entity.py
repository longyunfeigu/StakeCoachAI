from __future__ import annotations

from datetime import datetime, timezone

from domain.common.entity import BaseEntity, _ensure_utc


def test_ensure_utc_normalizes_naive_datetime() -> None:
    naive = datetime(2024, 1, 1, 12, 0, 0)
    aware = _ensure_utc(naive)
    assert aware is not None
    assert aware.tzinfo == timezone.utc


def test_base_entity_touch_and_soft_delete() -> None:
    entity = BaseEntity[int](id=1)
    assert entity.created_at is None
    entity._touch()
    assert entity.created_at is not None
    assert entity.updated_at is not None

    entity.mark_deleted()
    assert entity.deleted_at is not None
    assert entity.is_deleted() is True

    entity.restore()
    assert entity.deleted_at is None
    assert entity.is_deleted() is False
