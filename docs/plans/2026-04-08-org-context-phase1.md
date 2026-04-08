# 组织上下文 — 阶段一：数据模型 + 上下文感知对话

## Context

当前 StakeCoachAI 的角色（Persona）是孤岛——不知道公司做什么、其他角色是谁、和自己什么关系。这导致群聊中角色不会"配合"或"对立"，Coach 复盘也无法从组织政治角度给建议。

本阶段目标：引入 Organization / Team / PersonaRelationship 三个实体，让角色拥有组织归属和人际关系，并将这些信息注入 LLM prompt，使对话和复盘具备组织感知能力。

## §0 Triage

1. 只服务一个用户目标？**是**（组织上下文建模）
2. 只影响一个业务模块？**否**（stakeholder domain + prompt + coaching + 前端）
3. 不改 DB schema？**否**（新增 3 张表 + persona 加字段）
4. 不改公共 API 契约？**否**（新增组织/团队 CRUD API + persona API 扩展）
5. 不涉及 domain 规则变化？**否**（组织关系影响 prompt 构建逻辑）
6. 不涉及外部系统？**是**
7. 不涉及权限/安全？**是**
8. 少量文件？**否**（跨 4 层 + 前后端）

**→ Flow C（高风险变更），但降级为 Flow B** — 无 migration 复杂性（新表、不改旧表），无异步/事务问题。

## 第 1 层：目标与范围

### 目标
- 让 Persona 归属于 Organization + Team
- 建立角色间关系（上级/下级/同级/跨部门）
- prompt_builder 注入组织上下文 + 关系信息到 LLM 系统提示
- Coach 复盘注入组织上下文
- 前端：组织管理 UI + 角色关系编辑 + 关系图可视化

### 范围

| 在范围内 | 不在范围内 |
|----------|-----------|
| Organization CRUD（后端+前端） | 多租户/权限控制 |
| Team CRUD（后端+前端） | 证据驱动置信度系统 |
| PersonaRelationship CRUD | 周度聚合报告 |
| Persona 关联 org/team（frontmatter 扩展） | 个人成长追踪 |
| prompt_builder 注入组织上下文 | 战略目标关联 |
| coaching prompt 注入组织上下文 | |
| 前端关系图可视化 | |
| 创建场景时智能推荐角色 | |

### 影响范围

| 层 | 文件 | 变更类型 |
|----|------|---------|
| Domain | `domain/stakeholder/organization_entity.py` (新) | 新增 Organization, Team, PersonaRelationship 实体 |
| Infra/Models | `infrastructure/models/organization.py` (新) | 新增 3 张 ORM 表 |
| Infra/Repos | `infrastructure/repositories/organization_repository.py` (新) | 新增仓储实现 |
| Infra/UoW | `infrastructure/unit_of_work.py` | 注册新仓储 |
| Migration | `alembic/versions/xxx_add_organization.py` (新) | 新增迁移 |
| App/DTO | `application/services/stakeholder/dto.py` | 新增 Organization/Team/Relationship DTOs |
| App/Service | `application/services/stakeholder/organization_service.py` (新) | 组织 CRUD 服务 |
| App/Prompt | `application/services/stakeholder/prompt_builder.py` | 注入 org context + relationships |
| App/Coaching | `application/services/stakeholder/coaching_service.py` | 注入 org context |
| App/Persona | `application/services/stakeholder/persona_loader.py` | 解析新 frontmatter 字段 |
| App/Persona | `application/services/stakeholder/persona_editor_service.py` | 写入新 frontmatter |
| API | `api/routes/stakeholder.py` | 新增组织/团队/关系端点 |
| Frontend | `frontend/src/services/api.ts` | 新增 API 接口 |
| Frontend | `frontend/src/App.tsx` | 侧边栏增加组织管理入口 |
| Frontend | `frontend/src/components/OrganizationDialog.tsx` (新) | 组织管理对话框 |
| Frontend | `frontend/src/components/RelationshipEditor.tsx` (新) | 关系编辑组件 |
| Frontend | `frontend/src/components/OrgChart.tsx` (新) | 组织关系图可视化 |
| Frontend | `frontend/src/components/PersonaEditorDialog.tsx` | 增加 team 归属字段 |
| Frontend | `frontend/src/components/CreateRoomDialog.tsx` | 智能角色推荐 |

### 风险
- Persona 目前是文件存储，Organization/Team 是 DB 存储 → 混合存储模式需要衔接
- frontmatter 新增 `organization_id` / `team_id` 字段但 persona 不在 DB → 关系表用 `persona_id: str` 而非 FK

## 第 2 层：数据模型与方案

### 领域模型

```python
# Organization — 公司/组织
@dataclass
class Organization:
    id: Optional[int] = None
    name: str = ""              # 组织名称
    industry: str = ""          # 行业
    description: str = ""       # 组织描述（业务、产品、文化）
    context_prompt: str = ""    # 注入所有角色 system prompt 的组织背景
    created_at: Optional[datetime] = None

# Team — 部门/团队
@dataclass
class Team:
    id: Optional[int] = None
    organization_id: int = 0    # FK → Organization
    name: str = ""              # 团队名称
    description: str = ""       # 团队职责描述
    created_at: Optional[datetime] = None

# PersonaRelationship — 角色间关系
@dataclass
class PersonaRelationship:
    id: Optional[int] = None
    organization_id: int = 0             # FK → Organization
    from_persona_id: str = ""            # 角色A的 ID（字符串，对应 .md 文件名）
    to_persona_id: str = ""              # 角色B的 ID
    relationship_type: str = ""          # superior/subordinate/peer/cross_department
    description: str = ""                # 自由描述（例：直属汇报、产品方向协作）
    created_at: Optional[datetime] = None
```

### DB Schema

```sql
-- organizations
CREATE TABLE organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(255) DEFAULT '',
    description TEXT DEFAULT '',
    context_prompt TEXT DEFAULT '',
    created_at DATETIME(timezone=True) DEFAULT CURRENT_TIMESTAMP
);

-- teams
CREATE TABLE teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    created_at DATETIME(timezone=True) DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_teams_organization_id ON teams(organization_id);

-- persona_relationships
CREATE TABLE persona_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    from_persona_id VARCHAR(50) NOT NULL,
    to_persona_id VARCHAR(50) NOT NULL,
    relationship_type VARCHAR(30) NOT NULL,  -- superior/subordinate/peer/cross_department
    description TEXT DEFAULT '',
    created_at DATETIME(timezone=True) DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_persona_relationships_org ON persona_relationships(organization_id);
CREATE UNIQUE INDEX ux_persona_rel ON persona_relationships(organization_id, from_persona_id, to_persona_id);
```

### Persona frontmatter 扩展

```yaml
---
name: 首席财务官
role: CFO
avatar_color: "#FF5555"
organization_id: 1        # 新增：关联组织
team_id: 2                # 新增：关联团队
---
```

PersonaLoader 解析时提取这两个字段到 Persona dataclass。

### Prompt 注入策略

**prompt_builder.py 变更**：

1. 新增 `_build_org_context()` 函数：
   ```
   ## 组织背景
   {organization.context_prompt}
   
   ## 你在组织中的位置
   所属团队：{team.name} — {team.description}
   
   ## 你与其他角色的关系
   - {relationship.to_persona_name}：{relationship.relationship_type} — {relationship.description}
   ```

2. `build_llm_messages()` 和 `build_group_llm_messages()` 增加可选参数：
   ```python
   org_context: str | None = None  # 预构建好的组织上下文文本
   ```
   在 system prompt 中 persona_content 之后、role behavior instruction 之前注入。

3. **调用方**（`stakeholder_chat_service.py`）负责查询 org/team/relationships 并传入。

**coaching prompt 变更**：

`_build_coaching_system_prompt()` 增加 `org_context` 参数，注入到报告和对话摘要之间：
```
## 组织背景
{org_context}

## 你的任务
...额外增加：6. 从组织政治角度给出建议（例：「在向上级汇报前，建议先和 Robin 对齐」）
```

### API 设计

```
# Organization CRUD
POST   /api/v1/stakeholder/organizations           → 创建组织
GET    /api/v1/stakeholder/organizations           → 列出所有组织
GET    /api/v1/stakeholder/organizations/{id}      → 获取组织详情（含 teams）
PUT    /api/v1/stakeholder/organizations/{id}      → 更新组织
DELETE /api/v1/stakeholder/organizations/{id}      → 删除组织（级联删除 teams + relationships）

# Team CRUD
POST   /api/v1/stakeholder/organizations/{org_id}/teams           → 创建团队
GET    /api/v1/stakeholder/organizations/{org_id}/teams           → 列出团队
PUT    /api/v1/stakeholder/organizations/{org_id}/teams/{id}      → 更新团队
DELETE /api/v1/stakeholder/organizations/{org_id}/teams/{id}      → 删除团队

# Persona Relationships
POST   /api/v1/stakeholder/organizations/{org_id}/relationships           → 创建关系
GET    /api/v1/stakeholder/organizations/{org_id}/relationships           → 列出关系
PUT    /api/v1/stakeholder/organizations/{org_id}/relationships/{id}      → 更新关系
DELETE /api/v1/stakeholder/organizations/{org_id}/relationships/{id}      → 删除关系
```

### 前端组件

1. **侧边栏新增"组织"section**（在角色区上方）：
   - 显示当前组织名（如果存在）
   - 点击进入组织管理

2. **OrganizationDialog** — 组织管理对话框：
   - Tab 1: 基本信息（名称、行业、描述、上下文 prompt）
   - Tab 2: 团队管理（团队列表 + 增删改）
   - Tab 3: 关系图（可视化 + 添加关系）

3. **OrgChart** — 关系可视化：
   - 使用 HTML/CSS 实现简单层级树（不引入重图形库）
   - 节点 = Persona Avatar + 名称
   - 连线 = 关系类型标签
   - 点击节点跳转编辑角色

4. **PersonaEditorDialog 扩展**：
   - 新增"所属团队"下拉选择
   - 新增"角色关系"区域（列出与此角色相关的关系，可增删）

5. **CreateRoomDialog 智能推荐**：
   - 选择一个角色后，自动推荐与其有关系的其他角色
   - 推荐以 chip/tag 形式显示，用户一键添加

## §11 执行步骤

### Step 1: 后端 Domain + Infrastructure（新增 3 个实体 + ORM + 迁移）
- 创建 `domain/stakeholder/organization_entity.py`
- 创建 `infrastructure/models/organization.py`
- 在 `domain/stakeholder/repository.py` 追加仓储接口
- 创建 `infrastructure/repositories/organization_repository.py`
- 更新 `infrastructure/unit_of_work.py` 注册新仓储
- 生成 alembic migration
- 验证：`alembic upgrade head` + 检查表创建

### Step 2: 后端 Application + API（CRUD 服务 + 端点）
- 在 `dto.py` 追加 Organization/Team/Relationship DTOs
- 创建 `application/services/stakeholder/organization_service.py`
- 在 `api/routes/stakeholder.py` 追加端点
- 验证：curl 测试 CRUD

### Step 3: Persona 扩展（frontmatter 新字段 + loader + editor）
- 更新 `persona_loader.py` Persona dataclass + 解析逻辑
- 更新 `persona_editor_service.py` 写入新字段
- 更新 persona API（返回 organization_id, team_id）
- 验证：创建/编辑 persona 带 org/team

### Step 4: Prompt 注入（对话 + 复盘注入组织上下文）
- 更新 `prompt_builder.py` — 增加 `org_context` 参数
- 更新 `stakeholder_chat_service.py` — 查询 org 并传入 prompt builder
- 更新 `coaching_service.py` — 复盘 prompt 增加组织上下文
- 更新 `analysis_service.py` — 分析 prompt 增加组织上下文
- 验证：对话中角色能引用公司/其他角色/组织关系

### Step 5: 前端 API + 组织管理 UI
- `api.ts` 追加 Organization/Team/Relationship 接口 + 函数
- 创建 `OrganizationDialog.tsx` + `.css`
- 侧边栏增加"组织"section
- PersonaEditorDialog 增加 team 下拉
- 验证：前端创建组织、团队、关联角色

### Step 6: 前端关系图 + 智能推荐
- 创建 `OrgChart.tsx` + `.css`（层级树可视化）
- 创建 `RelationshipEditor.tsx`（关系增删 UI）
- CreateRoomDialog 智能角色推荐
- 验证：关系图显示、创建房间时推荐

## 验证方式

每个 Step 完成后：
1. 后端：`cd backend && uv run pytest tests/ -v`（如有测试）
2. 后端：`cd backend && uv run python main.py` 启动 + curl 测试 API
3. 前端：`cd frontend && npm run build`（TypeScript 检查）
4. 端到端：`npm run dev` + 浏览器验证
5. Step 4 后：创建带组织上下文的角色 → 对话中观察角色是否引用组织信息
