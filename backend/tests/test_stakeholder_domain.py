# input: domain/stakeholder entities, repositories; infrastructure models, repos
# output: Story 1.2 domain + infra layer tests
# owner: wanhua.gu
# pos: 测试层 - Story 1.2 聊天领域模型验收测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Story 1.2: ChatRoom/Message domain model + DB."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.models.base import Base


# ---------------------------------------------------------------------------
# AC1: Domain entity creation
# ---------------------------------------------------------------------------


def test_chatroom_entity_creation() -> None:
    from domain.stakeholder.entity import ChatRoom

    room = ChatRoom(
        id=None,
        name="Test Room",
        type="private",
        persona_ids=["jianfeng"],
    )
    assert room.name == "Test Room"
    assert room.type == "private"
    assert room.persona_ids == ["jianfeng"]
    assert room.created_at is not None
    assert room.last_message_at is None


def test_chatroom_entity_group() -> None:
    from domain.stakeholder.entity import ChatRoom

    room = ChatRoom(
        id=None,
        name="Group Chat",
        type="group",
        persona_ids=["jianfeng", "robin", "troy"],
    )
    assert room.type == "group"
    assert len(room.persona_ids) == 3


def test_chatroom_invalid_type() -> None:
    from domain.stakeholder.entity import ChatRoom
    from domain.common.exceptions import DomainValidationException

    with pytest.raises(DomainValidationException):
        ChatRoom(id=None, name="Bad", type="invalid", persona_ids=["a"])


def test_message_entity_creation() -> None:
    from domain.stakeholder.entity import Message

    msg = Message(
        id=None,
        room_id=1,
        sender_type="user",
        sender_id="user",
        content="Hello",
    )
    assert msg.sender_type == "user"
    assert msg.content == "Hello"
    assert msg.timestamp is not None


def test_message_invalid_sender_type() -> None:
    from domain.stakeholder.entity import Message
    from domain.common.exceptions import DomainValidationException

    with pytest.raises(DomainValidationException):
        Message(id=None, room_id=1, sender_type="invalid", sender_id="x", content="hi")


# ---------------------------------------------------------------------------
# AC2: Repository interfaces are abstract
# ---------------------------------------------------------------------------


def test_repository_interfaces_are_abstract() -> None:
    from domain.stakeholder.repository import ChatRoomRepository, MessageRepository
    import abc

    # Cannot instantiate directly
    with pytest.raises(TypeError):
        ChatRoomRepository()

    with pytest.raises(TypeError):
        MessageRepository()

    # All methods are abstract
    for method_name in ["create", "get_by_id", "list_rooms", "update_last_message_at"]:
        assert hasattr(ChatRoomRepository, method_name)

    for method_name in ["create", "list_by_room_id"]:
        assert hasattr(MessageRepository, method_name)


# ---------------------------------------------------------------------------
# AC3-6: ORM models + repository + index (integration with in-memory SQLite)
# ---------------------------------------------------------------------------


@pytest.fixture
async def async_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as session:
        async with session.begin():
            yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_orm_models_table_creation(async_session: AsyncSession) -> None:
    """AC3: ORM models create correct tables."""
    # Import to ensure models are registered
    from infrastructure.models.stakeholder import ChatRoomModel, StakeholderMessageModel

    result = await async_session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    tables = {row[0] for row in result.fetchall()}
    assert "stakeholder_chat_rooms" in tables
    assert "stakeholder_messages" in tables


@pytest.mark.asyncio
async def test_chatroom_repo_crud(async_session: AsyncSession) -> None:
    """AC4: Repository CRUD operations work."""
    from domain.stakeholder.entity import ChatRoom, Message
    from infrastructure.repositories.stakeholder_repository import (
        SQLAlchemyChatRoomRepository,
        SQLAlchemyStakeholderMessageRepository,
    )

    room_repo = SQLAlchemyChatRoomRepository(async_session)
    msg_repo = SQLAlchemyStakeholderMessageRepository(async_session)

    # Create room
    room = ChatRoom(id=None, name="Test", type="private", persona_ids=["jianfeng"])
    created = await room_repo.create(room)
    assert created.id is not None
    assert created.name == "Test"

    # Get by id
    fetched = await room_repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.name == "Test"
    assert fetched.persona_ids == ["jianfeng"]

    # List rooms
    rooms = await room_repo.list_rooms()
    assert len(rooms) == 1

    # Update last_message_at
    now = datetime.now(timezone.utc)
    await room_repo.update_last_message_at(created.id, now)
    updated = await room_repo.get_by_id(created.id)
    assert updated.last_message_at is not None

    # Create messages
    msg = Message(id=None, room_id=created.id, sender_type="user", sender_id="user", content="Hi")
    created_msg = await msg_repo.create(msg)
    assert created_msg.id is not None

    # List messages
    messages = await msg_repo.list_by_room_id(created.id)
    assert len(messages) == 1
    assert messages[0].content == "Hi"


@pytest.mark.asyncio
async def test_message_room_id_index(async_session: AsyncSession) -> None:
    """AC6: stakeholder_messages table has room_id index."""
    from infrastructure.models.stakeholder import StakeholderMessageModel

    result = await async_session.execute(
        text(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='stakeholder_messages'"
        )
    )
    indexes = {row[0] for row in result.fetchall()}
    assert any("room_id" in idx for idx in indexes)
