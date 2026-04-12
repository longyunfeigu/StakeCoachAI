# application/services/stakeholder

利益相关者聊天应用服务 — 用例编排层。

## 文件索引

| 文件 | 职责 |
|------|------|
| `persona_loader.py` | PersonaLoader — 从 Markdown 文件加载角色画像 |
| `chatroom_service.py` | ChatRoomApplicationService — 聊天室 CRUD（创建/列表/详情） |
| `dto.py` | 聊天室/分析报告 DTO（CreateChatRoomDTO, ChatRoomDTO, MessageDTO, AnalysisReportDTO, AnalysisContentDTO 等） |
| `stakeholder_chat_service.py` | StakeholderChatService — 私聊消息发送与 AI 回复编排（含 SSE 推送） |
| `prompt_builder.py` | build_llm_messages() — 构建 LLM 对话 prompt |
| `sse.py` | RoomEventBus — SSE 事件总线 + format_sse 格式化 |
| `dispatcher.py` | Dispatcher — 群聊调度器，decide_responders() + check_followup()；首轮调度为空时兜底选择首位角色避免冷场 |
| `analysis_service.py` | AnalysisService — LLM 智能对话分析报告生成（阻力排名 + 有效论点 + 沟通建议） |
| `compression_service.py` | CompressionService — 后台对话历史语义压缩（异步增量摘要，不阻塞聊天） |

## 依赖关系

- `chatroom_service.py` 依赖 `ChatRoomDomainService`（领域规则）、`PersonaLoader`（角色存在性验证）、`UnitOfWork`（事务）
- `stakeholder_chat_service.py` 依赖 `UnitOfWork`、`PersonaLoader`、`LLMPort`、`prompt_builder`、`RoomEventBus`、`CompressionService`
- `compression_service.py` 依赖 `UnitOfWork`、`LLMPort`（压缩摘要生成）、`PersonaLoader`（发言者名称解析）
- `dispatcher.py` 依赖 `LLMPort`（调度决策 LLM 调用）、`PersonaLoader`（角色画像摘要）；LLM 返回空/解析失败时首轮调度兜底到房间首位角色
- `persona_loader.py` 依赖文件系统（读取 `data/personas/*.md`）
- `analysis_service.py` 依赖 `UnitOfWork`、`LLMPort`（分析生成）、`PersonaLoader`（角色信息）
