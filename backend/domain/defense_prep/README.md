# domain/defense_prep — 答辩准备领域层

答辩准备（Defense Prep）聚合根，管理答辩会话的生命周期和场景配置。

## 文件索引

| 文件 | 职责 |
|------|------|
| `entity.py` | `DefenseSession` 聚合根实体，管理会话状态流转（preparing → in_progress → completed） |
| `value_objects.py` | 值对象：`DocumentSummary`（文档解析结果）、`QuestionStrategy` / `PlannedQuestion`（提问策略） |
| `scenario.py` | `ScenarioType` 枚举 + `SCENARIO_CONFIGS` 配置字典，定义所有答辩场景的维度、提问角度和行为约束 |
| `repository.py` | `DefenseSessionRepository` 抽象仓储接口（CRUD） |

## 场景类型

| 枚举值 | 名称 | 说明 |
|--------|------|------|
| `performance_review` | 述职答辩 | 年度/季度绩效汇报，追问业绩数据和归因 |
| `proposal_review` | 方案评审 | 技术/业务方案答辩，挑战设计决策和风险 |
| `project_report` | 项目汇报 | 项目进度与成果展示，追问里程碑和问题 |
| `general` | 通用答辩 | 自定义答辩场景，质疑文档论点和数据 |
| `interview` | 模拟面试 | 上传简历/JD，围绕具体项目经历深挖 |
| `probation_review` | 转正答辩 | 试用期转正述职，评估适应力、成长和团队融入 |

## 场景配置结构

每个场景包含 4 个字段：

```python
{
    "name": "显示名称",
    "dimensions": ["评估维度1", "评估维度2", ...],      # 5-6 个维度，用于评分
    "question_angles": ["提问角度1", "提问角度2", ...],  # 4-5 个角度，引导提问方向
    "question_instruction": "场景行为约束",               # 最高优先级指令，约束 AI 提问行为
}
```

`question_instruction` 的设计原则：
- 要求 AI 从文档**具体内容**中挑点提问，不允许泛泛而谈
- 给出示例说明什么叫"具体"（如"文档提到 X%，追问怎么算的"）
- 场景定位约束（如转正答辩不追问商业数字）

## 实体状态流转

```
preparing → in_progress → completed
  (创建)      (开始模拟)    (生成报告)
```

## 依赖关系

- 本层不依赖任何外部框架
- `infrastructure/repositories/` 实现 `DefenseSessionRepository`
- `application/services/defense_prep_service.py` 编排使用
