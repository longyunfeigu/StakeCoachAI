<div align="center">
<a name="readme-top"></a>

<h1>StakeCoachAI</h1>

<p><strong>用 AI 驱动的利益相关者模拟训练你的沟通能力。</strong></p>

<p>
创建包含多个 AI 角色的虚拟会议室，每个角色拥有独特的性格和议程。<br/>
运行场景化对话，实时追踪情绪动态，并获得教练反馈。
</p>

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-F7DF1E?style=for-the-badge)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](#快速开始)

<br/>

[快速开始](#快速开始) · [功能特性](#功能特性) · [配置说明](#配置说明) · [开发指南](#开发指南)

<br/>

<img src="docs/assets/hero-animation.svg" alt="StakeCoachAI 工作流程动画" width="720"/>

</div>

<br/>

---

## 为什么做这个？

> 你精心准备了方案，信心满满走进会议室。
> CTO 第二页就打断你："这和 Q3 路线图冲突了。"
> 你没准备这个问题。接下来 30 分钟你都在被动救火。
> 会后你收到邮件："方案暂缓，下季度再议。"

这种场景每天都在发生。

项目失败的头号原因不是技术——是沟通。PMI 研究显示，**56% 的项目风险源于沟通不畅**。一个关键会议的失误，可能意味着几个月的工作付诸东流。

但问题在于：**高风险对话没有彩排机会。**

| 现有方式 | 为什么不够 |
|:---------|:----------|
| 角色扮演工作坊 | 贵、频次低、对手不够真实 |
| 沟通技巧书籍/课程 | 知道 ≠ 做到，上场还是会卡壳 |
| 事后复盘总结 | 已经发生了，结果无法改变 |
| 找同事模拟 | 碍于面子，很难真正施压 |

**StakeCoachAI** 用 AI 创造了一个「安全但真实」的练习场——角色会打断你、质疑你、带着隐藏议程和情绪跟你博弈。你可以反复练习同一个场景，直到找到最优策略，然后带着准备好的方案走进真实会议室。

---

## 功能特性

🧑‍💼 **真实人物画像 (Persona)** — 喂入聊天记录、会议纪要、邮件往来，AI 提取沟通风格、决策偏好、情绪触发点，构建高保真角色。数据越多，角色越像那个「真人」——不是泛化的 CTO / PM 模板，而是**你要面对的那个人**。

🎭 **多角色聊天室** — 创建私聊（1 对 1）或群聊（2+ 角色）房间，每个 AI 角色拥有独立的性格、说话风格和隐藏议程。

🎬 **场景模拟** — 定义会议背景、你的目标和约束条件。将 Persona 放入特定场景，AI 角色按各自立场做出反应——就像真实的利益相关者会议。

📈 **情绪曲线** — 可视化每个角色在对话中的情感变化，精确定位转折点。结合 Persona 画像，理解为什么这句话触发了对方的防御反应。

🏅 **教练复盘** — 每次对话后获得 AI 生成的反馈：哪些做得好，哪些不足，以及针对具体角色的改进建议。

⚡ **实时流式输出** — 基于 SSE 的逐 token 响应，自然地观看对话展开。

📤 **导出与回放** — 将任意对话导出为 JSON 或 HTML，回顾历史会话，分享给团队，或作为培训素材。

---

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
git clone <repo-url> && cd StakeCoachAI
docker-compose up -d
```

### 方式二：本地开发

```bash
# 后端
cd backend
uv venv --python 3.11 .venv && source .venv/bin/activate
uv sync --extra dev
cp env.example .env          # 编辑 SECRET_KEY 和 DATABASE__URL
uv run python main.py

# 前端（另开终端）
cd frontend
npm install && npm run dev
```

### 服务地址

| 服务 | 地址 |
|:-----|:-----|
| API | [localhost:8000](http://localhost:8000) |
| Swagger 文档 | [localhost:8000/docs](http://localhost:8000/docs) |
| 前端 | [localhost:5173](http://localhost:5173) |

---

## 配置说明

基于 **Pydantic Settings v2**，使用 `__` 分隔符通过环境变量设置嵌套配置。

```bash
# 必填
SECRET_KEY=change-me
DATABASE__URL=postgresql+asyncpg://user:pass@localhost:5432/mydb

# LLM（驱动 AI 角色）
LLM__PROVIDER=openai
LLM__API_KEY=sk-...

# 可选
REDIS__URL=redis://localhost:6379/0      # 缓存与分布式功能
STORAGE__TYPE=local                       # local | s3 | oss
METRICS__ENABLED=true                     # Prometheus 指标
TRACING__ENABLED=true                     # OpenTelemetry 链路追踪
```

完整配置参考：[`backend/env.example`](backend/env.example)

---

## 开发指南

```bash
cd backend

# 运行测试
uv run pytest tests/ -v

# 覆盖率报告
uv run pytest tests/ --cov=. --cov-report=html

# 数据库迁移
uv run alembic revision --autogenerate -m "add feature"
uv run alembic upgrade head

# 代码质量检查
uv run pre-commit run --all-files
```

---

## 技术栈

| 组件 | 技术 |
|:-----|:-----|
| 后端 | Python 3.11, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL |
| 前端 | React, TypeScript, Vite |
| AI | LLM 集成 (OpenAI / Anthropic), SSE 流式输出 |
| 基础设施 | Docker Compose, Alembic, Redis, Prometheus, OpenTelemetry |

---

## 参与贡献

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/awesome`)
3. 提交更改 (`git commit -m 'feat: add awesome feature'`)
4. 推送并创建 Pull Request

---

## 许可证

[MIT](LICENSE)

---

<div align="center">

**[回到顶部](#readme-top)**

</div>
