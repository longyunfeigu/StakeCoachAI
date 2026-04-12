<div align="center">

<a name="readme-top"></a>

<h1>DaBoss — 打Boss</h1>

<p><strong>职场牛马人的会前练习场 —— 用 AI 模拟你的老板，把高风险对话变成可重复的练习。</strong></p>

<p>
喂入聊天记录和会议纪要，AI 帮你还原那个真实的 Boss。<br/>
开会前先打一遍，反复过招，直到找到最优策略再上场。
</p>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=flat&logo=typescript)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

---

[功能特性](#-核心功能) · [快速开始](#-30秒启动) · [架构设计](#-技术架构) · [路线图](#-roadmap)

---

<img src="docs/assets/hero-animation.svg" alt="DaBoss 工作流程动画" width="720"/>

</div>

---

## 背景问题

> 你精心准备了方案，走进会议室。
> CTO第二页就打断：「这和Q3路线图冲突。」
> 接下来30分钟，你在被动救火。
> 会后邮件：「方案暂缓，下季度再议。」

**这不是技术问题，是沟通问题。**

项目失败的头号原因不是技术——是沟通。PMI 研究显示，**56% 的项目风险源于沟通不畅**。一个关键会议的失误，可能意味着几个月的工作付诸东流。

但问题在于：**高风险对话没有彩排机会。**

| 现有方式 | 为什么不够 |
|:---------|:----------|
| 角色扮演工作坊 | 贵、频次低、对手不够真实 |
| 沟通技巧书籍/课程 | 知道 ≠ 做到，上场还是会卡壳 |
| 事后复盘总结 | 已经发生了，结果无法改变 |
| 找同事模拟 | 碍于面子，很难真正施压 |

**DaBoss** 用 AI 创造了一个「安全但真实」的练习场——角色会打断你、质疑你、带着隐藏议程和情绪跟你博弈。你可以反复练习同一个场景，直到找到最优策略，然后带着准备好的方案走进真实会议室。

---

## 核心功能

<div align="center">
  <img src="docs/assets/homepage.png" alt="DaBoss 主页" width="80%"/>
</div>

### 实时演练系统

创建聊天室，选择利益相关者角色，开始模拟对话：

<div align="center">
  <img src="docs/assets/create-room-dialog.png" alt="创建聊天室对话框" width="60%"/>
</div>

AI角色会根据角色设定做出真实反应——质疑、施压、带着隐藏议程博弈：

<div align="center">
  <img src="docs/assets/chat-conversation.png" alt="对话界面 - AI角色实时回复" width="80%"/>
</div>

实时查看每个角色的情绪变化曲线：

<div align="center">
  <img src="docs/assets/emotion-panel.png" alt="实时情绪面板" width="80%"/>
</div>

### LLM-as-Judge 评估框架

每次对话后，AI从六个维度评估你的表现：

| 维度 | 评估内容 |
|:---|:---|
| **说服力** | 论点的逻辑性和说服力 |
| **情绪管理** | 压力下的情绪调控能力 |
| **倾听回应** | 理解并回应对方关切的能力 |
| **结构化表达** | 表达的逻辑清晰度 |
| **冲突处理** | 化解分歧、达成共识的能力 |
| **利益对齐** | 识别并整合多方利益的能力 |

<div align="center">
  <img src="docs/assets/analysis-report.png" alt="对话分析报告 - 阻力排名与沟通建议" width="60%"/>
</div>

### AI Coach 复盘

对话结束后，AI教练对你的表现进行深度复盘，给出核心改进建议和反思问题：

<div align="center">
  <img src="docs/assets/ai-coaching.png" alt="AI Coach 复盘" width="80%"/>
</div>

### 成长追踪系统

<div align="center">
  <img src="docs/assets/growth-dashboard.png" alt="成长仪表板" width="80%"/>
</div>

### 语音对话

像打电话一样练习沟通——点击录音说话，AI 角色用独立音色语音回复。每个角色声音不同，群聊听起来像真实会议。

| 能力 | 说明 |
|:---|:---|
| **语音输入** | 点击录音 / 长按说话，VAD 自动检测语音起止 |
| **语音输出** | 每个 Persona 独立音色，逐句流式播放 |
| **多厂商支持** | TTS: MiniMax / ElevenLabs；STT: OpenAI Whisper 兼容 |
| **低延迟管道** | LLM 流式输出 → 按句切分 → TTS 并行合成 → 首句 ~1.5s 响应 |
| **无侵入** | 语音是文本的增强层，所有消息仍以文字存储，分析报告等功能不受影响 |

通过环境变量一键切换 TTS 厂商：

```bash
# MiniMax TTS（默认）
VOICE__TTS_PROVIDER=minimax
VOICE__TTS_API_KEY=your-minimax-key

# ElevenLabs TTS
VOICE__TTS_PROVIDER=elevenlabs
VOICE__TTS_API_KEY=your-elevenlabs-key

# STT（OpenAI Whisper 兼容）
VOICE__STT_PROVIDER=whisper
VOICE__STT_API_KEY=your-openai-key
VOICE__STT_BASE_URL=https://api.openai.com/v1
```

### 紧急备战模式

重要会议前 30 分钟，打开「紧急备战」：

1. **描述会议** — 输入你要谈什么、对方是谁
2. **AI 生成对手** — 自动创建高度还原的对方角色，支持微调和难度选择（温和/正常/强硬）
3. **快速对练** — 限时 12 轮模拟对话，AI 围绕你选择的训练重点施压
4. **话术纸条** — 对话结束后自动生成一页纸的实战话术：开场白、关键应对、避坑提醒、底线策略

支持一键复制文本或下载为 PNG 图片，带进会议室直接用。

### 沟通力名片

在「成长轨迹」页面，完成 2 次以上能力评估后，一键生成你的「沟通力名片」：

- AI 分析你的历史评分，生成个性化风格标签（如"数据驱动型说服者"）
- 6 维进度条直观展示能力分布
- 特征标签一眼看出优势和待提升方向
- 下载为精美 PNG 图片，分享到朋友圈

### 组织关系图谱

角色不是孤立的个体——他们之间有权力关系、联盟和历史恩怨。

```
     ┌─────────┐
     │  CTO   │ ◄──── 权力压制 ────┐
     └────┬────┘                    │
          │                       │
          │ 信任                   │
     ┌────▼────┐                  │
     │  你     │ ◄───── 隐藏议程 ──┘
     └────┬────┘
          │
          │ 历史分歧
     ┌────▼────┐
     │   PM   │
     └─────────┘
```

AI会根据这些关系做出反应——PM反对你，可能因为CTO已经表态。

---

## 30秒启动

```bash
git clone <repo-url> && cd DaBoss
docker-compose up -d

# 访问前端
open http://localhost:5173
```

```bash
# 本地开发
# 后端
cd backend && uv sync && uv run python main.py

# 前端（新终端）
cd frontend && npm install && npm run dev
```

---

## 技术架构

<div align="center">
  <img src="docs/assets/architecture-diagram.png" alt="DaBoss 技术架构" width="90%"/>
</div>

---

## 为什么选择 DaBoss？

| | DaBoss | 其他方案 |
|:---|:---|:---|
| **真实性** | AI有情绪、有隐藏议程、有组织关系 | 静态脚本，过于理想化 |
| **即时反馈** | 对话中可求助教练，实时获得建议 | 只有事后总结 |
| **科学评估** | LLM-as-Judge六维度评估 | 无评估或主观打分 |
| **成长追踪** | 跨会话趋势分析，可视化进步 | 无历史追踪 |
| **组织政治** | 角色间有权力关系和联盟博弈 | 角色相互独立 |

---

## Roadmap

- [x] 紧急备战模式（会前快速模拟 + 话术纸条）
- [x] 沟通力名片（6维评分社交分享卡片）
- [x] 语音对话支持（MiniMax / ElevenLabs TTS + OpenAI Whisper STT）
- [ ] 更多评估维度（跨文化沟通、谈判技巧等）
- [ ] 角色市场（预设的经典角色包）
- [ ] 团队协作模式（多人实时演练）
- [ ] 移动端适配

---

## 参与贡献

欢迎贡献！查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送并创建 Pull Request

---

## 许可证

[MIT](LICENSE) © 2024

---

<div align="center">

**如果这个项目对你有帮助，请给一个 Star**

你的支持是我持续更新的动力

**[回到顶部](#readme-top)**

</div>
