# 紧急备战模式 & 谈判力名片 — 设计文档

> 为 DaBoss（打Boss）新增两个核心功能：紧急备战模式（会前快速模拟 + 话术纸条）和谈判力名片（6维评分社交分享卡片）。

## 功能一：紧急备战模式（Battle Prep）

### 用户故事

> 作为一个即将参加重要会议的职场人，我希望在会前 30 分钟快速描述我要谈什么，AI 自动帮我生成对方角色并模拟对话，最后给我一张可以带进会议室的"话术纸条"。

### 交互流程

```
侧边栏点击「紧急备战」（闪电图标，视觉突出）
       ↓
 Step 1: 文本框描述会议情况（必填）
         placeholder: "描述你即将参加的会议：跟谁谈、谈什么、你的目标是什么、对方可能的态度..."
       ↓
 Step 2: AI 生成角色预览卡片
         展示：角色名、职位、沟通风格描述
         用户可微调描述（编辑文本）
         选择难度级别（温和 / 正常 / 强硬），默认"正常"
         点击「确认角色」
       ↓
 Step 3: AI 提取 2-3 个训练重点
         展示为勾选列表，如：
           ☑ 如何开场陈述
           ☑ 如何应对"预算紧"的推回
           ☐ 如何提出底线方案
         用户勾选想练的（至少选 1 个）
         点击「开始备战」
       ↓
 自动创建 ChatRoom（type="battle_prep"）+ 临时 Persona
 进入正常对话界面
       ↓
 对话结束后自动弹出「话术纸条」页面
 支持：复制全文 / 下载 PNG 图片
```

### 对话结束机制

| 机制 | 说明 |
|------|------|
| 默认上限 | 12 轮用户消息 |
| 智能提前结束 | 训练重点都覆盖后，AI 在第 6 轮后可主动收尾 |
| 用户主动结束 | 输入框旁增加「结束备战」按钮 |
| 超时保护 | 30 分钟无消息自动结束 |

对话结束的触发条件（任一满足即触发）：
1. 用户消息达到 12 轮（前端计数 + 后端防御：`send_message` 中检查 battle_prep 房间的用户消息数，>=12 时返回 HTTP 422）
2. 用户点击「结束备战」按钮
3. AI 判断训练重点已充分覆盖并主动收尾（通过 system prompt 指令实现）
4. 30 分钟无新消息（前端 setTimeout 实现，每次发送消息重置计时器；浏览器关闭则不触发，用户重新打开房间可手动结束）

### 后端设计

#### 新增 Service

`BattlePrepService`（`application/services/stakeholder/battle_prep_service.py`）

职责：编排整个备战流程。依赖 `LLMPort`、`ChatRoomApplicationService`、`PersonaEditorService`。

```python
class BattlePrepService:
    async def generate_prep(self, description: str) -> BattlePrepDTO:
        """Step 1→2: 用户描述 → LLM 生成角色 + 场景 + 训练重点"""

    async def start_battle(self, prep: StartBattleDTO) -> ChatRoomDTO:
        """Step 3→对话: 确认配置 → 创建临时 Persona + ChatRoom → 返回 room"""

    async def generate_cheat_sheet(self, room_id: int) -> CheatSheetDTO:
        """对话结束 → LLM 生成话术纸条"""
```

#### 新增 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/stakeholder/battle-prep/generate` | 输入会议描述 → 返回角色预览 + 训练重点 |
| POST | `/stakeholder/battle-prep/start` | 确认配置 → 创建房间 → 返回 room_id |
| POST | `/stakeholder/rooms/{room_id}/cheat-sheet` | 生成话术纸条 |

#### 新增 DTO

```python
class BattlePrepGenerateDTO(BaseModel):
    """输入：用户的会议描述"""
    description: str = Field(..., min_length=10, max_length=5000)

class BattlePrepResultDTO(BaseModel):
    """输出：AI 生成的角色 + 场景 + 训练重点"""
    persona_name: str
    persona_role: str
    persona_style: str          # 沟通风格描述
    scenario_context: str       # 场景上下文
    training_points: list[str]  # 2-3 个训练重点

class StartBattleDTO(BaseModel):
    """输入：用户确认后的配置"""
    persona_name: str = Field(..., min_length=1, max_length=100)
    persona_role: str = Field(..., min_length=1, max_length=200)
    persona_style: str = Field(..., min_length=1, max_length=2000)
    scenario_context: str = Field(..., min_length=1, max_length=5000)
    selected_training_points: list[str] = Field(..., min_length=1, max_length=5)
    difficulty: str = Field(default="normal", pattern=r"^(easy|normal|hard)$")

class TacticItem(BaseModel):
    """话术纸条中的单个策略项"""
    situation: str             # 情境描述
    response: str              # 建议话术

class CheatSheetDTO(BaseModel):
    """输出：话术纸条"""
    opening: str               # 开场建议
    key_tactics: list[TacticItem]  # 关键话术
    pitfalls: list[str]        # 避坑提醒
    bottom_line: str           # 底线策略
```

#### LLM Prompt 设计

**Prompt 1: 角色生成（generate_prep 调用）**

输入：用户的会议描述文本
输出：JSON 格式的 BattlePrepResultDTO

系统指令要点：
- 从描述中推断对方的职位、权力关系、可能的沟通风格
- 生成 2-3 个最可能的交锋点作为训练重点
- 场景上下文要包含背景信息和冲突焦点
- 如果 LLM 返回不足 2 个训练重点，补充通用训练重点（如"如何开场""如何应对质疑"）

#### 错误处理

- LLM 返回无效 JSON：复用 `growth_service.py` 中的 markdown fence 剥离 + JSONDecodeError 捕获模式
- generate_prep / generate_cheat_sheet 失败：返回 HTTP 502 + 友好提示
- LLM 超时：返回 HTTP 504

**Prompt 2: 话术纸条生成（generate_cheat_sheet 调用）**

输入：对话记录 + 场景背景 + 训练重点
输出：JSON 格式的 CheatSheetDTO

系统指令要点：
- opening：基于对话中的有效策略，提炼 1-2 句开场白
- key_tactics：针对每个训练重点，提取"情境→建议话术"对
- pitfalls：从对话中用户的失误点提炼避坑提醒
- bottom_line：如果主要目标达不成，退而求其次的策略

#### 数据模型

**ChatRoom.type 扩展**（影响范围需全部更新）：
- `domain/stakeholder/entity.py`：`_ROOM_TYPES` 集合新增 `"battle_prep"`
- `application/services/stakeholder/dto.py`：`CreateChatRoomDTO.type` 的 pattern 改为 `r"^(private|group|battle_prep)$"`
- `api/routes/stakeholder.py`：export 端点的 type_label 映射增加 `"battle_prep": "备战"`
- `frontend/src/App.tsx`：room type badge 增加 `battle_prep` → "备战" 映射
- battle_prep 房间默认不显示在普通房间列表中（通过 `RoomList` 过滤 type），单独在备战区域展示

**临时 Persona 管理**：
- 使用 `PersonaEditorService.create_persona()` 创建，id 格式为 `bp-{uuid4_short}`（8位随机字符）避免并发冲突
- 在 Persona frontmatter 中标记 `temporary: true`
- 清理策略：`BattlePrepService` 在创建新 Persona 前，先删除超过 24 小时的 `bp-*` 文件（同步清理，不需要后台任务）

**话术纸条**：不单独建表，通过 API 实时生成返回

#### 难度级别实现

通过在 Persona 的 system prompt 中注入不同的行为指令：

| 难度 | 注入指令 |
|------|---------|
| easy（温和） | "你态度相对友好，愿意倾听，但会提出合理的质疑" |
| normal（正常） | "你按照画像正常沟通，会质疑不充分的论点，但不会刻意刁难" |
| hard（强硬） | "你非常强势，会频繁打断、质疑数据来源、用情绪施压" |

### 前端设计

#### 新增组件

**`BattlePrepDialog`**（`frontend/src/components/BattlePrepDialog.tsx`）

三步引导对话框：
- Step 1：大文本框 + 提示文案
- Step 2：角色卡片预览（可编辑） + 难度选择器（三个 radio）
- Step 3：训练重点勾选列表 + 开始按钮

每步之间有 loading 动画（Step 1→2 需要等 LLM 返回）。

**`CheatSheet`**（`frontend/src/components/CheatSheet.tsx`）

话术纸条展示页面，弹窗形式：
- 顶部：场景摘要 + 对方角色名
- 主体：四个板块（开场白 / 关键话术 / 避坑提醒 / 底线策略）
- 底部：「复制全文」+「下载图片」按钮
- 图片下载使用 `html2canvas` 截图

#### 侧边栏改动

在 `App.tsx` 侧边栏中，「成长轨迹」按钮上方增加「紧急备战」按钮：
- 图标：`Zap`（lucide-react 闪电图标）
- 样式：带强调色背景，与普通按钮区分

#### 对话界面改动

`battle_prep` 类型的房间：
- 顶部显示训练重点标签
- 输入框旁增加「结束备战」按钮（`Flag` 图标）
- 前端计数用户消息轮次，达到 12 轮时自动调用 cheat-sheet API
- 对话区域顶部显示"备战模式 · 剩余 X 轮"提示

---

## 功能二：谈判力名片（Profile Card）

### 用户故事

> 作为一个使用 DaBoss 练习过多次的用户，我希望生成一张精美的"沟通力名片"，展示我的沟通风格标签和 6 维能力，保存为图片分享到朋友圈。

### 交互流程

```
成长轨迹页面 → 点击「生成我的名片」
       ↓
 LLM 基于历史评估数据生成：
   - 风格标签（如"数据驱动型说服者"）
   - 3-4 个特征 tag
   - 一句话点评
       ↓
 弹窗展示名片预览
 点击「下载图片」保存 PNG
```

### 视觉设计

**确认的风格：简洁白底 + 标签 + 进度条**

卡片布局（上→下）：
1. **Header**：DaBoss logo + "DABOSS PROFILE" 标签 + 风格标签大标题
2. **Tags**：3-4 个特征标签，绿色=优势，橙色=待提升，蓝色=特点
3. **进度条**：6 个维度，每个一行（维度名 + 进度条 + 分数）
   - 进度条颜色：≥3.5 分紫色渐变（#4f46e5→#7c3aed），<3.5 分橙红渐变（#f59e0b→#ef4444）
4. **点评**：灰底圆角框内一句话总结
5. **Footer**："DaBoss · 测测你的职场沟通风格 →"

卡片尺寸：360px 宽，适合手机屏幕和社交分享。

### 后端设计

#### 新增 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/stakeholder/growth/card` | 基于历史评估 → LLM 生成风格标签 + tags + 点评 |

#### 新增 DTO

```python
class ProfileTag(BaseModel):
    """名片标签"""
    text: str                   # 如 "#逻辑清晰"
    type: str = Field(..., pattern=r"^(strength|weakness|trait)$")

class ProfileCardDTO(BaseModel):
    """输出：名片数据"""
    style_label: str            # 如"数据驱动型说服者"
    tags: list[ProfileTag]      # 3-4 个特征标签
    summary: str                # 一句话点评
    scores: dict[str, float]    # 6维平均分，key 使用 COMPETENCY_DIMENSIONS 定义的 6 个维度
                                # (persuasion, emotional_management, active_listening,
                                #  structured_expression, conflict_resolution, stakeholder_alignment)
```

#### Service 改动

在 `GrowthService` 中新增方法：

```python
async def generate_profile_card(self) -> ProfileCardDTO:
    """基于历史评估数据生成名片内容"""
    # 1. 获取所有评估，计算各维度平均分
    # 2. 调用 LLM 生成 style_label + tags + summary
    # 3. 返回 ProfileCardDTO
```

#### LLM Prompt 设计

输入：各维度平均分 + 趋势（进步/退步/稳定）+ 最近 3 次评估的 evidence
输出：JSON 格式的 style_label、tags、summary

系统指令要点：
- style_label 必须 2-6 个字，像 MBTI 标签一样简短有辨识度
- tags 3-4 个，格式为 "#xxx"，优势用 strength、弱项用 weakness、中性特征用 trait
- summary 一句话，20-40 字，指出最突出的优势和最需要提升的方向
- 语气正向但诚实，不要空洞表扬

#### 前置条件

- 至少完成 2 次能力评估才能生成（与成长洞察门槛一致）
- 不足时：service 返回带提示信息的 ProfileCardDTO（style_label 为空，summary 为提示文案），与 `generate_insight()` 处理模式保持一致，不抛 HTTP 异常

#### 错误处理

- LLM 返回无效 JSON：复用 `growth_service.py` 中的 markdown fence 剥离 + JSONDecodeError 捕获模式，返回 None 时路由层返回 HTTP 502
- LLM 超时：捕获后返回 HTTP 504

### 前端设计

#### GrowthDashboard 改动

在成长洞察区域下方增加「生成我的名片」按钮：
- 图标：`Share2`（lucide-react）
- 不足 2 次评估时按钮 disabled，tooltip："再完成 X 次练习即可解锁"

#### 新增组件

**`ProfileCard`**（`frontend/src/components/ProfileCard.tsx`）

纯渲染组件，接收 `ProfileCardDTO` 数据，渲染卡片 DOM。
- 进度条宽度 = `score / 5 * 100%`
- 进度条颜色：score >= 3.5 用紫色渐变，< 3.5 用橙红渐变
- tag 颜色：strength → 绿底，weakness → 橙底，trait → 蓝底

**`ProfileCardDialog`**（`frontend/src/components/ProfileCardDialog.tsx`）

弹窗组件，包裹 ProfileCard：
- 标题："我的沟通力名片"
- 底部按钮：「下载图片」
- 下载使用 `html2canvas`：截取 ProfileCard DOM → canvas → PNG blob → 触发下载

#### 依赖新增

- `html2canvas`：前端 DOM 截图，约 40KB gzipped
  - 注意：卡片 DOM 中避免使用外部图片、复杂 CSS filter 和 SVG 元素，确保截图保真
  - 需在 Safari mobile 上测试，因为社交分享场景以 iOS 为主

---

## 技术决策总结

| 决策 | 选择 | 理由 |
|------|------|------|
| 话术纸条存储 | 不建表，实时生成 | 简单；用户主要是即时使用而非查阅历史 |
| 临时 Persona 管理 | 复用 PersonaEditorService 创建，bp-{uuid} 前缀 + 24h 自动清理 | 复用现有 CRUD，不引入新实体 |
| generate/start 无状态 | 前端持有全部中间状态，两个 API 无服务端关联 | 简单可靠，无需 Redis/缓存，接受页面刷新丢失状态的 tradeoff |
| 名片图片生成 | 前端 html2canvas | 纯前端实现，不需要服务端 headless browser |
| 对话轮数限制 | 前端计数 + 后端 prompt 指令配合 | 简单可靠，不需要新的中间件 |
| 难度调节 | system prompt 注入 | 零成本实现，无需修改核心对话引擎 |

## 不做的事情

- 不做话术纸条的历史记录功能（用户可以截图保存）
- 不做名片的服务端渲染（html2canvas 足够）
- 不做名片的分享链接（MVP 只做图片下载）
- 不做备战模式的语音支持（复用现有语音即可，不需要额外适配）
- 不做训练重点的自定义编辑（用户只能从 AI 推荐中勾选）

## 文件清单

### 后端新增
- `application/services/stakeholder/battle_prep_service.py` — 备战服务
- `application/services/stakeholder/dto.py` — 新增 BattlePrepGenerateDTO、BattlePrepResultDTO、StartBattleDTO、CheatSheetDTO、ProfileCardDTO

### 后端修改
- `api/routes/stakeholder.py` — 新增 4 个端点
- `api/dependencies.py` — 新增 `get_battle_prep_service()` DI 注册
- `application/services/stakeholder/growth_service.py` — 新增 generate_profile_card()
- `application/services/stakeholder/dto.py` — CreateChatRoomDTO.type pattern 扩展
- `domain/stakeholder/entity.py` — `_ROOM_TYPES` 新增 "battle_prep"

### 前端新增
- `frontend/src/components/BattlePrepDialog.tsx` — 三步引导对话框
- `frontend/src/components/BattlePrepDialog.css`
- `frontend/src/components/CheatSheet.tsx` — 话术纸条
- `frontend/src/components/CheatSheet.css`
- `frontend/src/components/ProfileCard.tsx` — 名片渲染
- `frontend/src/components/ProfileCardDialog.tsx` — 名片弹窗
- `frontend/src/components/ProfileCard.css`

### 前端修改
- `frontend/src/App.tsx` — 侧边栏入口 + battle_prep 房间标识 + 对话结束触发
- `frontend/src/services/api.ts` — 新增 4 个 API 调用函数
- `frontend/package.json` — 新增 html2canvas 依赖
