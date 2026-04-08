# Growth Dashboard — LLM-as-Judge 多维能力评估 + 成长轨迹

## Context

StakeCoachAI 用户练习完对话后，只能看到单次 session 的分析报告。缺乏跨 session 的能力评估和成长追踪，导致每次练习孤立，无法形成"练习→评估→改进→再练习"的闭环。

本特性引入三个核心技术点：
1. **LLM-as-Judge 多维能力评分** — 每次分析报告生成后，自动用 LLM 按 6 维 rubric 评估用户表现
2. **能力雷达图** — 用 recharts RadarChart 可视化多维能力，叠加历史数据看趋势
3. **跨 Session LLM 成长洞察** — 用户主动触发，LLM 综合所有评估数据生成定性成长分析

## §0 Triage

| # | 问题 | 答案 |
|---|------|------|
| 1 | 单一用户目标？ | YES |
| 2 | 单一业务模块？ | YES |
| 3 | 不改 DB schema？ | **NO** — 新增 competency_evaluations 表 |
| 4 | 不改公共 API？ | **NO** — 新增 growth endpoints |
| 5 | 不改 domain 规则？ | **NO** — 新增 CompetencyEvaluation 实体 |
| 6 | 不涉及外部系统？ | YES（LLM 已有） |
| 7 | 不涉及权限安全？ | YES |
| 8 | 少量文件？ | **NO** — ~15 files |

**→ Flow C**（4 个 NO），填全部 3 层。

---

## 第 1 层：范围与风险

### 目标

1. 分析报告生成后，**自动触发** LLM-as-Judge 评估，按 6 个沟通能力维度打分（1-5）并给出证据和改进建议
2. Sidebar 新增"成长轨迹"入口，展示 **能力雷达图**（最新 + 历史叠加）和统计总览
3. 用户可主动触发 **LLM 成长洞察**，获得跨 session 的定性分析

### 6 个能力维度（Rubric）

| 维度 Key | 中文 | 评什么 |
|----------|------|--------|
| `persuasion` | 说服力 | 论点构建质量、证据使用、逻辑链完整性 |
| `emotional_management` | 情绪管理 | 被质疑/反对时是否保持冷静、避免防守性回答 |
| `active_listening` | 倾听回应 | 是否回应对方关切、确认理解、不自说自话 |
| `structured_expression` | 结构化表达 | 先说结论还是铺垫过长、信息组织是否清晰 |
| `conflict_resolution` | 冲突处理 | 面对分歧时的策略选择、是否寻求共识 |
| `stakeholder_alignment` | 利益对齐 | 是否识别并利用各方共同利益点 |

每个维度输出：`score`（1-5）+ `evidence`（对话原文引用）+ `suggestion`（改进建议）

### 影响范围

- **后端新增**：1 实体 + 1 ORM + 1 仓储 + 1 迁移 + 1 Service + DTOs + DI + API
- **后端修改**：analysis route 链接 background task
- **前端新增**：GrowthDashboard 组件 + CSS + AnalysisResultDialog 组件
- **前端修改**：App.tsx 集成 Growth tab + 新增独立"分析"按钮 + api.ts 新增调用
- **依赖**：无新增（recharts 已有 RadarChart）

### 风险

| 风险 | 应对 |
|------|------|
| 评估 LLM 调用额外成本 | 用 background task 异步执行，不阻塞分析报告返回 |
| 评分不稳定（同一对话两次评分不同） | temperature=0.2 + 详细 rubric 约束打分一致性 |
| 数据不足时雷达图无意义 | 少于 2 次评估时显示 empty state |
| 成长洞察 LLM 幻觉 | prompt 强制引用具体分数变化，不允许编造 |

### 验收标准

- [ ] 生成分析报告后，后台自动产出能力评估（6 维分数 + 证据 + 建议）
- [ ] Dashboard 雷达图正确展示最新评估，可叠加历史对比
- [ ] 统计卡片数据准确
- [ ] "生成成长洞察"返回有价值的跨 session 分析文本
- [ ] Empty state 友好

---

## 第 2 层：方案设计

### 现状说明

当前前端**没有独立的"分析"按钮**。AnalysisReport 的生成嵌套在 AI Coach 流程内部：
- 用户点击 AI Coach（GraduationCap 图标）→ 内部先调 `POST /rooms/{id}/analysis` 生成报告 → 再启动 Coaching Session

本次变更同时**新增独立的"分析"按钮**，与 AI Coach 并列在聊天室 header，让用户可以只做分析+能力评估而不启动 coaching。

### 核心流程

```
路径 A：用户点击新增的"分析"按钮（独立入口）
    → POST /rooms/{room_id}/analysis
    → AnalysisService.generate_report()  [现有]
    → 返回 report 给前端（前端展示分析摘要）
    → background_task: GrowthService.evaluate_competency(report_id)  [新增]
        → 加载对话记录 + persona 信息
        → LLM-as-Judge prompt（6 维 rubric）
        → 解析 JSON → 存入 competency_evaluations 表

路径 B：用户点击 AI Coach（现有流程，不变）
    → 内部同样先生成 AnalysisReport → 启动 Coaching
    → 同样触发 background_task: evaluate_competency

用户点击"成长轨迹" tab
    → GET /growth/dashboard
    → GrowthService 聚合所有 evaluations → 返回 dashboard 数据
    → 前端渲染雷达图 + 统计卡片

用户点击"生成成长洞察"
    → POST /growth/insight
    → GrowthService 加载所有评估 → LLM 生成跨 session 分析 → 返回文本
```

### 新增 Domain Entity

```python
# backend/domain/stakeholder/competency_entity.py
@dataclass
class CompetencyEvaluation:
    id: Optional[int]
    report_id: int          # FK → analysis_reports
    room_id: int            # FK → chat_rooms（冗余，方便查询）
    scores: dict            # JSON: {dimension: {score, evidence, suggestion}}
    overall_score: float    # 6 维平均分
    created_at: Optional[datetime]
```

`scores` JSON 结构：
```json
{
  "persuasion": {"score": 3, "evidence": "用户提出了ROI数据支撑...", "suggestion": "建议增加具体案例"},
  "emotional_management": {"score": 4, "evidence": "被CFO质疑时保持冷静...", "suggestion": "..."},
  "active_listening": {"score": 2, "evidence": "...", "suggestion": "..."},
  "structured_expression": {"score": 3, "evidence": "...", "suggestion": "..."},
  "conflict_resolution": {"score": 3, "evidence": "...", "suggestion": "..."},
  "stakeholder_alignment": {"score": 4, "evidence": "...", "suggestion": "..."}
}
```

### DB Schema

```sql
CREATE TABLE stakeholder_competency_evaluations (
    id SERIAL PRIMARY KEY,
    report_id INTEGER NOT NULL REFERENCES stakeholder_analysis_reports(id) ON DELETE CASCADE,
    room_id INTEGER NOT NULL REFERENCES stakeholder_chat_rooms(id) ON DELETE CASCADE,
    scores JSON NOT NULL,
    overall_score REAL NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_competency_eval_room_id ON stakeholder_competency_evaluations(room_id);
CREATE UNIQUE INDEX uq_competency_eval_report_id ON stakeholder_competency_evaluations(report_id);
```

`report_id` 加 UNIQUE — 一个分析报告只对应一个能力评估。

### API 设计

```
GET  /api/v1/stakeholder/growth/dashboard
Response: {
  overview: { total_sessions, total_evaluations, avg_overall_score, latest_score },
  evaluations: [
    { id, report_id, room_id, room_name, scores, overall_score, created_at }
  ],
  dimension_trends: {
    "persuasion": [{ date, score }],
    "emotional_management": [{ date, score }],
    ...
  }
}

POST /api/v1/stakeholder/growth/insight
Response: {
  insight: "在最近 5 次练习中，你的情绪管理从 2.0 提升到 3.5..."
}
```

### LLM-as-Judge Prompt 设计要点

```
你是一位专业的沟通能力评估师。请根据以下 Rubric 对用户的沟通表现打分。

## 评分维度与标准

### 说服力 (persuasion)
- 1分：无有效论点，纯粹陈述观点
- 2分：有论点但缺乏支撑证据
- 3分：有论点和部分证据，但逻辑链不完整
- 4分：论点清晰、证据充分，有说服力
- 5分：论点精准、多角度论证、预判反驳

### 情绪管理 (emotional_management)
- 1分：明显情绪失控或强烈防守性回答
- 2分：在压力下偶尔失控
- 3分：基本保持冷静但有防守倾向
- 4分：压力下保持冷静，积极回应
- 5分：将对方压力转化为建设性对话

### 倾听回应 (active_listening)
- 1分：完全忽视对方观点，自说自话
- 2分：偶尔提及对方观点但未真正回应
- 3分：能复述对方观点但回应不够深入
- 4分：准确理解并回应对方关切，有追问
- 5分：深度倾听，挖掘对方未明确表达的需求

### 结构化表达 (structured_expression)
- 1分：表达混乱，没有逻辑结构
- 2分：有一定结构但铺垫过长，重点不突出
- 3分：基本清晰，先说结论但论述不够精炼
- 4分：结构清晰，结论先行，论据有序
- 5分：表达精准，金字塔结构，适配听众认知

### 冲突处理 (conflict_resolution)
- 1分：回避冲突或激化矛盾
- 2分：被动应对，缺乏策略
- 3分：能识别分歧但解决方案不够创造性
- 4分：主动管理冲突，提出双赢方案
- 5分：将冲突转化为建设性讨论，达成共识

### 利益对齐 (stakeholder_alignment)
- 1分：只关注自身诉求，忽视对方利益
- 2分：意识到对方利益但未主动对齐
- 3分：尝试寻找共同利益但不够精准
- 4分：准确识别共同利益并以此为锚点推进
- 5分：创造性地重构问题框架，实现多方利益最大化

## 评分规则
- 必须引用对话原文作为 evidence
- score 必须是 1-5 整数
- suggestion 必须具体可操作，不要笼统建议
```

### 前端 Dashboard 布局

```
┌─────────────────────────────────────────────────┐
│  成长轨迹                                        │
├──────────┬──────────┬──────────┬──────────┤
│  练习次数  │  评估次数  │  平均分    │  最新分   │
│    12     │    8     │   3.2    │   3.8    │
├──────────┴──────────┴──────────┴──────────┤
│                                                 │
│         ◆ 能力雷达图 (RadarChart)                │
│     说服力                                       │
│      /    \        ── 最新评估（实线）             │
│    利益    情绪      ── 历史平均（虚线）             │
│    对齐    管理                                   │
│      \    /                                     │
│     冲突  倾听                                    │
│      结构化                                      │
│                                                 │
├─────────────────────────────────────────────────┤
│  📊 各维度趋势（点击维度展开）                      │
│  说服力:   ●──●──●──●──●  2→3→3→4→4              │
│  情绪管理: ●──●──●──●──●  1→2→3→3→4              │
│  ...                                            │
├─────────────────────────────────────────────────┤
│  💡 成长洞察                     [生成洞察]        │
│  "在最近 5 次练习中..."                           │
└─────────────────────────────────────────────────┘
```

使用 recharts `RadarChart` + `Radar` 组件（已有依赖，EmotionCurve.tsx 已验证 recharts 可用）。

---

## 第 3 层：关键实现细节

### DB 迁移

Alembic autogenerate，新增 `stakeholder_competency_evaluations` 表。`report_id` UNIQUE 确保幂等（重复触发不会产生重复评估）。

### Background Task 链接

在 `backend/api/routes/stakeholder.py` 的 analysis 生成 endpoint 中，report 创建成功后追加 background task：

```python
@router.post("/rooms/{room_id}/analysis")
async def create_analysis(
    room_id: int,
    background_tasks: BackgroundTasks,
    analysis_svc: AnalysisService = Depends(get_analysis_service),
    growth_svc: GrowthService = Depends(get_growth_service),
):
    report = await analysis_svc.generate_report(room_id)
    # 异步触发能力评估，不阻塞返回
    background_tasks.add_task(growth_svc.evaluate_competency, report.id)
    return success_response(data={"id": report.id}, status_code=201)
```

### LLM 调用幂等性

`evaluate_competency` 先检查 `report_id` 是否已有评估记录，有则跳过。UNIQUE 约束兜底。

### 成长洞察 Prompt

输入：所有评估的分数时间线 + 最近 3 次的 evidence/suggestion。
输出：自然语言文本，强制引用具体分数变化。
用 `LLMPort.generate(temperature=0.4)` 非流式调用。

---

## §11 执行步骤

| Step | 任务 | 文件 | 类型 |
|------|------|------|------|
| 1 | Domain: 新建 CompetencyEvaluation 实体 | `domain/stakeholder/competency_entity.py` | 新建 |
| 2 | Domain: 新增 CompetencyEvaluationRepository ABC | `domain/stakeholder/repository.py` | 修改 |
| 3 | Infra: 新建 ORM model | `infrastructure/models/competency.py` | 新建 |
| 4 | Infra: 注册 model | `infrastructure/models/__init__.py` | 修改 |
| 5 | Infra: 新建 Repository 实现 | `infrastructure/repositories/competency_repository.py` | 新建 |
| 6 | Infra: UoW 注册新 repository | `infrastructure/unit_of_work.py` | 修改 |
| 7 | DB: 生成 Alembic migration | `alembic/versions/...` | 新建 |
| 8 | Application: 新增 Growth DTOs | `application/services/stakeholder/dto.py` | 修改 |
| 9 | Application: 新建 GrowthService（评估 + Dashboard + 洞察） | `application/services/stakeholder/growth_service.py` | 新建 |
| 10 | API: 新增 DI + Growth endpoints + 链接 background task | `api/dependencies.py`, `api/routes/stakeholder.py` | 修改 |
| 11 | Frontend: api.ts 新增 Growth API 调用 | `frontend/src/services/api.ts` | 修改 |
| 12 | Frontend: 新建 GrowthDashboard 组件 + CSS | `frontend/src/components/GrowthDashboard.tsx`, `.css` | 新建 |
| 13 | Frontend: App.tsx 新增独立"分析"按钮 + 分析结果展示 | `frontend/src/App.tsx` | 修改 |
| 14 | Frontend: App.tsx 集成 Growth tab | `frontend/src/App.tsx` | 修改 |
| 15 | 端到端验证 | - | 手动 |

---

## 验证方式

1. `cd backend && alembic upgrade head` 执行迁移
2. `cd backend && uv run python main.py` 启动后端
3. `cd frontend && npm run dev` 启动前端
4. 创建聊天室，进行 2-3 轮对话
5. 点击"分析"生成报告 → 检查后台日志确认 competency evaluation 被触发
6. 等待几秒后点击"成长轨迹" → 验证雷达图 + 统计卡片
7. 多做 2 个 session 后再看 → 验证历史叠加和趋势
8. 点击"生成成长洞察" → 验证 LLM 返回有意义的分析
9. 无评估数据时 → 验证 empty state
