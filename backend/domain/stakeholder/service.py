# input: 无外部依赖，纯业务规则
# output: ChatRoomDomainService 聊天室领域服务
# owner: wanhua.gu
# pos: 领域层 - 利益相关者聊天室业务规则验证；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Domain service for stakeholder chat room business rules."""

from __future__ import annotations

from domain.common.exceptions import DomainValidationException


class ChatRoomDomainService:
    """Pure business rules for chat room creation and management."""

    def validate_room_creation(self, room_type: str, persona_ids: list[str]) -> None:
        """Validate persona_ids count based on room type.

        Raises DomainValidationException if the count is wrong.
        """
        if room_type == "private" and len(persona_ids) != 1:
            raise DomainValidationException(
                "Private room requires exactly 1 persona",
                field="persona_ids",
                details={"expected": 1, "got": len(persona_ids)},
            )
        if room_type == "group" and len(persona_ids) < 2:
            raise DomainValidationException(
                "Group room requires at least 2 personas",
                field="persona_ids",
                details={"minimum": 2, "got": len(persona_ids)},
            )
