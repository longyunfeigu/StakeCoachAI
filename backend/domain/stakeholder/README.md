# domain/stakeholder

利益相关者聊天聚合 — 领域层（纯业务逻辑，无外部依赖）。

## 文件索引

| 文件 | 职责 |
|------|------|
| `entity.py` | ChatRoom / Message 领域实体，含类型验证和 UTC 时间处理 |
| `repository.py` | ChatRoomRepository / MessageRepository 抽象仓储接口 |
| `service.py` | ChatRoomDomainService — 聊天室创建业务规则（私聊1人/群聊>=2人） |

## 领域规则

- `ChatRoom.type` 只允许 `private` / `group`
- `Message.sender_type` 只允许 `user` / `persona` / `system`
- 私聊聊天室 `persona_ids` 必须恰好 1 个
- 群聊聊天室 `persona_ids` 至少 2 个
