# input: AbstractUnitOfWork, LLMPort, DocumentParser, ChatRoomApplicationService, PersonaLoader
# output: DefensePrepService 答辩准备编排服务
# owner: wanhua.gu
# pos: 应用层服务 - 答辩准备（文档解析→策略生成→模拟→评估）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Defense Prep service: document-based Q&A simulation workflow."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Callable, Optional

from application.ports.document_parser import DocumentParser
from application.ports.llm import LLMMessage, LLMPort
from application.services.stakeholder.chatroom_service import ChatRoomApplicationService
from application.services.stakeholder.dto import CreateChatRoomDTO
from application.services.stakeholder.persona_loader import PersonaLoader
from domain.common.unit_of_work import AbstractUnitOfWork
from domain.defense_prep.entity import DefenseSession
from domain.defense_prep.scenario import ScenarioType, SCENARIO_CONFIGS
from domain.defense_prep.value_objects import PlannedQuestion, QuestionStrategy

logger = logging.getLogger(__name__)

_STRATEGY_PROMPT = """\
你正在参加一场【{scenario_name}】。

## 场景要求（最高优先级，必须遵守）
{question_instruction}

## 你的角色
你是一位{role}，{tone}风格。
你的典型追问：{typical_questions}
注意：你的角色风格应服务于上述场景要求，不能偏离场景定位。

## 被评审者提交的文档内容
---
{document_text}
---

## 评估维度
{dimensions}

## 提问角度参考
{question_angles}

## 要求
1. 严格按照【场景要求】的定位来设计问题
2. 生成 {question_count} 个问题，按优先级排序
3. 每个问题标注：目标维度(dimension)、难度(difficulty: basic/advanced/stress_test)、期望回答方向(expected_direction)
4. 问题风格可体现你的角色特点，但内容必须围绕场景定位
"""

_STRATEGY_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "dimension": {"type": "string"},
                    "difficulty": {"type": "string", "enum": ["basic", "advanced", "stress_test"]},
                    "expected_direction": {"type": "string"},
                },
                "required": ["question", "dimension", "difficulty", "expected_direction"],
            },
        },
    },
    "required": ["questions"],
}

_REPORT_PROMPT = """\
你是一位职场沟通教练。请根据以下答辩模拟的对话记录，生成评估报告。

## 评估维度
{dimensions}

## 对话记录
{conversation}

请对每个维度打分（1-10分），并给出整体评分、逐题回顾和改进建议。
"""

_REPORT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "overall_score": {"type": "number"},
        "dimension_scores": {"type": "object", "additionalProperties": {"type": "number"}},
        "question_reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "user_answer_summary": {"type": "string"},
                    "score": {"type": "number"},
                    "feedback": {"type": "string"},
                    "improvement": {"type": "string"},
                },
                "required": ["question", "user_answer_summary", "score", "feedback", "improvement"],
            },
        },
        "summary": {"type": "string"},
        "top_improvements": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "overall_score",
        "dimension_scores",
        "question_reviews",
        "summary",
        "top_improvements",
    ],
}


class DefensePrepService:
    """Orchestrates the defense prep workflow."""

    def __init__(
        self,
        uow_factory: Callable[..., AbstractUnitOfWork],
        llm: LLMPort,
        document_parser: DocumentParser,
        chatroom_service: ChatRoomApplicationService,
        persona_loader: PersonaLoader,
    ) -> None:
        self._uow_factory = uow_factory
        self._llm = llm
        self._parser = document_parser
        self._chatroom_service = chatroom_service
        self._persona_loader = persona_loader

    async def create_session(
        self,
        file_content: bytes,
        filename: str,
        persona_ids: list[str],
        scenario_type: ScenarioType,
    ) -> DefenseSession:
        """Step 1: Parse document and create a defense session."""
        summary = await self._parser.parse(file_content, filename)
        session = DefenseSession(
            id=None, persona_ids=persona_ids, scenario_type=scenario_type, document_summary=summary
        )
        async with self._uow_factory() as uow:
            session = await uow.defense_session_repository.create(session)
            await uow.commit()
        return session

    async def start_session(self, session_id: int) -> DefenseSession:
        """Step 2: Generate question strategy, create room, start simulation."""
        async with self._uow_factory() as uow:
            session = await uow.defense_session_repository.get_by_id(session_id)
            if session is None:
                raise ValueError(f"Defense session {session_id} not found")
            strategy = await self._generate_strategy(session)
            session.question_strategy = strategy

            # Create a Scenario entity so the constraint is injected into
            # every persona system prompt during the ongoing conversation.
            config = SCENARIO_CONFIGS[session.scenario_type]
            instruction = config.get("question_instruction", "")
            scenario_context = (
                f"场景: {config['name']}\n" f"评估维度: {', '.join(config['dimensions'])}\n"
            )
            if instruction:
                scenario_context += f"\n## 场景行为约束（最高优先级，必须遵守）\n{instruction}"
            scenario_context += (
                "\n\n## 节奏控制（必须遵守）\n"
                "每个话题追问最多 2-3 轮，然后必须切换到文档中的下一个工作项或主题。"
                "确保在整场对话中覆盖文档中的多个不同内容，不要在单个话题上纠缠过久。"
                "如果对方回答含糊，最多再追问一次要求具体化，之后记下这个点并推进到下一个话题。"
            )

            from domain.stakeholder.scenario_entity import Scenario

            scenario = await uow.scenario_repository.create(
                Scenario(
                    id=None,
                    name=f"答辩: {config['name']}",
                    description=f"答辩准备会话 #{session_id}",
                    context_prompt=scenario_context,
                )
            )
            await uow.commit()

            persona_names = []
            for pid in session.persona_ids:
                p = self._persona_loader.get_persona(pid)
                persona_names.append(p.name if p else pid)
            room = await self._chatroom_service.create_room(
                CreateChatRoomDTO(
                    name=f"答辩: {', '.join(persona_names)}",
                    type="defense",
                    persona_ids=session.persona_ids,
                    scenario_id=scenario.id,
                )
            )
            session.start(room_id=room.id)
            await uow.defense_session_repository.update(session)
            await uow.commit()

        config = SCENARIO_CONFIGS[session.scenario_type]
        instruction = config.get("question_instruction", "")
        context_msg = (
            f"[答辩模式] 场景: {config['name']}\n"
            f"文档: {session.document_summary.title}\n"
            f"评估维度: {', '.join(config['dimensions'])}\n"
        )
        if instruction:
            context_msg += f"\n## 场景行为约束（必须遵守）\n{instruction}\n"
        context_msg += f"\n文档摘要:\n{session.document_summary.raw_text[:3000]}"
        first_q = strategy.questions[0] if strategy.questions else None
        first_q_text = first_q.question if first_q else "请介绍一下这份文档的核心内容。"
        first_q_sender = first_q.asked_by if first_q else session.persona_ids[0]

        from domain.stakeholder.entity import Message

        async with self._uow_factory() as uow:
            await uow.stakeholder_message_repository.create(
                Message(
                    id=None,
                    room_id=room.id,
                    sender_type="system",
                    sender_id="system",
                    content=context_msg,
                )
            )
            await uow.stakeholder_message_repository.create(
                Message(
                    id=None,
                    room_id=room.id,
                    sender_type="persona",
                    sender_id=first_q_sender,
                    content=first_q_text,
                )
            )
            await uow.commit()

        return session

    async def _generate_strategy(self, session: DefenseSession) -> QuestionStrategy:
        config = SCENARIO_CONFIGS[session.scenario_type]
        n = len(session.persona_ids)
        questions_per_persona = max(3, 12 // n)

        all_questions: list[PlannedQuestion] = []
        for pid in session.persona_ids:
            persona = self._persona_loader.get_persona(pid)
            role = persona.role if persona else "上级领导"
            tone = ""
            typical_questions = ""
            if persona:
                if persona.expression:
                    tone = persona.expression.tone
                if persona.decision:
                    typical_questions = ", ".join(persona.decision.typical_questions[:5])
            prompt = _STRATEGY_PROMPT.format(
                role=role,
                tone=tone or "专业严谨",
                typical_questions=typical_questions or "（无特定追问）",
                scenario_name=config["name"],
                question_instruction=config.get(
                    "question_instruction", "找出文档中数据薄弱、逻辑不严密、结论缺少支撑的地方"
                ),
                document_text=session.document_summary.raw_text[:8000],
                dimensions=", ".join(config["dimensions"]),
                question_angles="\n".join(f"- {a}" for a in config["question_angles"]),
                question_count=questions_per_persona,
            )
            messages = [LLMMessage(role="user", content=prompt)]
            try:
                parsed = await self._llm.generate_structured(
                    messages,
                    schema=_STRATEGY_SCHEMA,
                    schema_name="defense_question_strategy",
                    schema_description="生成答辩提问策略",
                    temperature=0.4,
                )
            except Exception as exc:
                logger.error("LLM strategy generation failed for persona %s: %s", pid, exc)
                raise ValueError("提问策略生成失败，请重试") from exc
            for q in parsed.get("questions", [])[:questions_per_persona]:
                all_questions.append(
                    PlannedQuestion(
                        question=q.get("question", ""),
                        dimension=q.get("dimension", ""),
                        difficulty=q.get("difficulty", "basic"),
                        expected_direction=q.get("expected_direction", ""),
                        asked_by=pid,
                    )
                )

        interleaved = self._interleave_by_dimension(all_questions)
        return QuestionStrategy(questions=interleaved)

    def _interleave_by_dimension(self, questions: list[PlannedQuestion]) -> list[PlannedQuestion]:
        """Group by dimension, then round-robin within each group to alternate personas."""
        from collections import defaultdict

        by_dim: dict[str, list[PlannedQuestion]] = defaultdict(list)
        dim_order: list[str] = []
        for q in questions:
            if q.dimension not in dim_order:
                dim_order.append(q.dimension)
            by_dim[q.dimension].append(q)
        result: list[PlannedQuestion] = []
        for dim in dim_order:
            result.extend(by_dim[dim])
        return result

    async def get_session(self, session_id: int) -> Optional[DefenseSession]:
        async with self._uow_factory(readonly=True) as uow:
            return await uow.defense_session_repository.get_by_id(session_id)

    async def generate_report(self, session_id: int) -> dict:
        async with self._uow_factory(readonly=True) as uow:
            session = await uow.defense_session_repository.get_by_id(session_id)
            if session is None:
                raise ValueError(f"Defense session {session_id} not found")
        if session.room_id is None:
            raise ValueError("Session has no room — simulation not started")
        detail = await self._chatroom_service.get_room_detail(session.room_id, message_limit=200)
        messages = detail.messages
        if not messages:
            raise ValueError("对话记录为空，无法生成报告")
        lines: list[str] = []
        for msg in messages:
            if msg.sender_type == "system":
                continue
            if msg.sender_type == "user":
                lines.append(f"[用户]: {msg.content}")
            else:
                p = self._persona_loader.get_persona(msg.sender_id)
                name = p.name if p else msg.sender_id
                lines.append(f"[{name}]: {msg.content}")
        config = SCENARIO_CONFIGS[session.scenario_type]
        prompt = _REPORT_PROMPT.format(
            dimensions=", ".join(config["dimensions"]), conversation="\n\n".join(lines)
        )
        messages_llm = [LLMMessage(role="user", content=prompt)]
        try:
            report = await self._llm.generate_structured(
                messages_llm,
                schema=_REPORT_SCHEMA,
                schema_name="defense_report",
                schema_description="答辩评估报告",
                temperature=0.3,
            )
        except Exception as exc:
            logger.error("LLM report generation failed: %s", exc)
            raise ValueError("评估报告生成失败，请重试") from exc
        async with self._uow_factory() as uow:
            session_fresh = await uow.defense_session_repository.get_by_id(session_id)
            if session_fresh:
                session_fresh.complete()
                await uow.defense_session_repository.update(session_fresh)
                await uow.commit()
        return report
