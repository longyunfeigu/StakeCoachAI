# input: domain/stakeholder service, PersonaLoader
# output: Story 2.1 domain + application layer tests
# owner: wanhua.gu
# pos: 测试层 - Story 2.1 聊天室 CRUD 领域与应用服务测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Story 2.1: ChatRoom domain service validation rules."""

from __future__ import annotations

import pytest

from domain.common.exceptions import DomainValidationException


# ---------------------------------------------------------------------------
# Domain service: validate_room_creation
# ---------------------------------------------------------------------------


def _make_loader_stub(known_ids: set[str]):
    """Create a minimal PersonaLoader stub that knows a fixed set of IDs."""

    class _Stub:
        def get_persona(self, persona_id: str):
            if persona_id in known_ids:
                return object()  # truthy
            return None

    return _Stub()


def test_private_room_requires_exactly_one_persona():
    from domain.stakeholder.service import ChatRoomDomainService

    svc = ChatRoomDomainService()
    with pytest.raises(DomainValidationException, match="exactly 1"):
        svc.validate_room_creation("private", ["a", "b"])


def test_private_room_empty_personas():
    from domain.stakeholder.service import ChatRoomDomainService

    svc = ChatRoomDomainService()
    with pytest.raises(DomainValidationException, match="exactly 1"):
        svc.validate_room_creation("private", [])


def test_group_room_requires_at_least_two_personas():
    from domain.stakeholder.service import ChatRoomDomainService

    svc = ChatRoomDomainService()
    with pytest.raises(DomainValidationException, match="at least 2"):
        svc.validate_room_creation("group", ["a"])


def test_private_room_valid():
    from domain.stakeholder.service import ChatRoomDomainService

    svc = ChatRoomDomainService()
    svc.validate_room_creation("private", ["jianfeng"])  # should not raise


def test_group_room_valid():
    from domain.stakeholder.service import ChatRoomDomainService

    svc = ChatRoomDomainService()
    svc.validate_room_creation("group", ["jianfeng", "robin"])  # should not raise
