# input: application.services.stakeholder.build_events
# output: Story 2.4 BuildEvent 契约测试（事件常量 + dataclass 字段）
# owner: wanhua.gu
# pos: 测试层 - Story 2.4 BuildEvent 契约单元测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Story 2.4 BuildEvent constants and dataclass contract."""

from __future__ import annotations

from application.services.stakeholder.build_events import (
    BUILD_ADVERSARIALIZE_DONE,
    BUILD_ADVERSARIALIZE_START,
    BUILD_AGENT_TOOL_USE,
    BUILD_ERROR,
    BUILD_EVENT_TYPES,
    BUILD_HEARTBEAT,
    BUILD_PARSE_DONE,
    BUILD_PERSIST_DONE,
    BUILD_WORKSPACE_READY,
    BuildEvent,
)


def test_six_canonical_event_constants_exist():
    six = [
        BUILD_WORKSPACE_READY,
        BUILD_AGENT_TOOL_USE,
        BUILD_PARSE_DONE,
        BUILD_ADVERSARIALIZE_START,
        BUILD_ADVERSARIALIZE_DONE,
        BUILD_PERSIST_DONE,
    ]
    assert len(set(six)) == 6  # all distinct strings


def test_auxiliary_event_types_exist():
    assert BUILD_ERROR == "error"
    assert BUILD_HEARTBEAT == "heartbeat"


def test_build_event_types_tuple_covers_all():
    assert BUILD_WORKSPACE_READY in BUILD_EVENT_TYPES
    assert BUILD_ERROR in BUILD_EVENT_TYPES
    assert len(BUILD_EVENT_TYPES) == 8


def test_build_event_dataclass_has_required_fields():
    ev = BuildEvent(seq=1, type=BUILD_WORKSPACE_READY, data={"workspace_path": "/tmp/x"})
    assert ev.seq == 1
    assert ev.type == "workspace_ready"
    assert ev.data["workspace_path"] == "/tmp/x"
    assert isinstance(ev.ts, float)


def test_build_event_ts_defaults_to_now():
    ev = BuildEvent(seq=0, type=BUILD_HEARTBEAT)
    assert ev.ts > 0
