# input: LLMPort, PersonaLoader (画像摘要), 用户消息, 对话历史, mentioned_ids (@提及角色列表)
# output: Dispatcher 群聊调度器 — decide_responders(mentioned_ids) + check_followup()
# owner: wanhua.gu
# pos: 应用层服务 - 群聊调度决策（判断哪些角色回复及顺序）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Group chat dispatcher: decides which personas should reply and in what order."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from application.ports.llm import LLMMessage

logger = logging.getLogger(__name__)


class Dispatcher:
    """Decides which personas respond in a group chat and in what order.

    Uses LLM to analyze the user message, conversation history, and persona
    profiles to make intelligent scheduling decisions.
    """

    def __init__(self, llm, persona_loader) -> None:
        self._llm = llm
        self._persona_loader = persona_loader

    async def decide_responders(
        self,
        *,
        user_message: str,
        history: list[dict[str, str]],
        persona_ids: list[str],
        mentioned_ids: list[str] | None = None,
    ) -> list[dict[str, str]]:
        """Decide which personas should respond first to the user message.

        Returns list of ``{"persona_id": ..., "reason": ...}`` sorted by
        response priority.  Only valid *persona_ids* are returned.
        Personas in *mentioned_ids* are force-included in the result.
        """
        system_prompt = self._build_system_prompt(persona_ids)
        user_content = self._build_decide_user_prompt(
            user_message,
            history,
            mentioned_ids=mentioned_ids,
        )

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_content),
        ]

        raw = await self._call_llm(messages)
        valid_ids = set(persona_ids)
        result = self._filter_valid(raw, valid_ids)

        # Force-include mentioned personas
        if mentioned_ids:
            existing_ids = {r["persona_id"] for r in result}
            for mid in mentioned_ids:
                if mid in valid_ids and mid not in existing_ids:
                    result.insert(0, {"persona_id": mid, "reason": "被用户 @点名"})

        return result

    async def check_followup(
        self,
        *,
        last_reply: dict[str, str],
        history: list[dict[str, str]],
        persona_ids: list[str],
        already_responded: set[str],
    ) -> list[dict[str, str]]:
        """Check if other personas want to follow up after *last_reply*.

        Returns list of ``{"persona_id": ..., "reason": ...}`` or empty list.
        """
        system_prompt = self._build_system_prompt(persona_ids)
        user_content = self._build_followup_user_prompt(
            last_reply,
            history,
            already_responded,
            persona_ids=persona_ids,
        )

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_content),
        ]

        raw = await self._call_llm(messages)
        return self._filter_valid(raw, set(persona_ids))

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_system_prompt(self, persona_ids: list[str]) -> str:
        """Build system prompt containing all persona summaries."""
        persona_lines: list[str] = []
        for pid in persona_ids:
            persona = self._persona_loader.get_persona(pid)
            if persona is None:
                continue
            persona_lines.append(
                f"- {persona.name} ({persona.role}, id={persona.id}): {persona.profile_summary}"
            )

        personas_block = "\n".join(persona_lines) if persona_lines else "(无角色信息)"

        return (
            "你是一个群聊调度器。你的职责是分析对话，判断哪些利益相关者角色应该回复，以及回复顺序。\n\n"
            "## 核心原则\n"
            "- 模拟真实会议中的自然反应，像真人一样判断谁该说话\n"
            "- 至少要有一个角色回复用户——用户说了话不能冷场，哪怕只是简短回应\n"
            "- 但不需要所有人都发言：如果某角色只能重复别人的观点，就不该凑数\n"
            "- 判断依据：被点名？话题在其职责内？有独特观点？需要社交回应（如用户表达情绪）？\n\n"
            "## 参与角色\n"
            f"{personas_block}\n\n"
            "## 输出格式\n"
            '严格返回 JSON 数组，每个元素为 {"persona_id": "<角色id>", "reason": "<简述回复原因>"}。\n'
            "只返回 JSON，不要其他内容。"
        )

    def _build_decide_user_prompt(
        self,
        user_message: str,
        history: list[dict[str, str]],
        *,
        mentioned_ids: list[str] | None = None,
    ) -> str:
        history_text = self._format_history(history)
        prompt = (
            "请判断哪些角色应该对用户最新消息做出回复，并按回复优先级排序。\n"
            "至少选一个最相关的角色回复，但不需要让所有人都发言。\n\n"
            f"## 对话历史\n{history_text}\n\n"
            f"## 用户最新消息\n{user_message}"
        )

        if mentioned_ids:
            # Resolve IDs to names for readability
            names: list[str] = []
            for mid in mentioned_ids:
                persona = self._persona_loader.get_persona(mid)
                names.append(persona.name if persona else mid)
            prompt += (
                "\n\n## 被直接 @点名的角色\n"
                "以下角色被用户直接点名，必须回复（即使话题不在其职责范围内）："
                f"{', '.join(names)}"
            )

        return prompt

    def _build_followup_user_prompt(
        self,
        last_reply: dict[str, str],
        history: list[dict[str, str]],
        already_responded: set[str],
        persona_ids: list[str] | None = None,
    ) -> str:
        history_text = self._format_history(history)
        responded_text = ", ".join(already_responded) if already_responded else "无"
        not_responded = [pid for pid in persona_ids if pid not in already_responded]
        not_responded_text = ", ".join(not_responded) if not_responded else "无"
        return (
            "上一位角色刚发表了回复，请判断是否有其他角色需要跟进。\n"
            "跟进的标准：有不同意见要反驳、有重要补充信息、被直接点名、或需要回应用户情绪。\n"
            "不需要凑数——如果只能重复已有观点就不要跟进。\n\n"
            f"## 对话历史\n{history_text}\n\n"
            f"## 最新回复\n"
            f"发言者: {last_reply.get('sender_id', 'unknown')}\n"
            f"内容: {last_reply.get('content', '')}\n\n"
            f"## 本轮已回复角色\n{responded_text}\n"
            f"## 本轮尚未发言角色\n{not_responded_text}\n\n"
            "如果没有角色需要跟进，返回空数组 []。"
        )

    @staticmethod
    def _format_history(history: list[dict[str, str]]) -> str:
        if not history:
            return "(空)"
        lines: list[str] = []
        for msg in history[-20:]:  # last 20 messages for context window
            sender = msg.get("sender_id", msg.get("sender_type", "unknown"))
            lines.append(f"[{sender}]: {msg.get('content', '')}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # LLM call + parse
    # ------------------------------------------------------------------

    async def _call_llm(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Call LLM and parse the JSON array response."""
        try:
            response = await self._llm.generate(messages)
            return self._parse_json_array(response.content)
        except Exception:
            logger.exception("Dispatcher LLM call failed")
            return []

    @staticmethod
    def _parse_json_array(text: str) -> list[dict[str, Any]]:
        """Extract a JSON array from LLM response text.

        Handles common LLM output quirks: markdown code blocks, leading prose,
        trailing commentary.  Uses regex to locate the outermost ``[...]``.
        """
        text = text.strip()

        # Fast path: text is already a clean JSON array
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

        # Regex: find the first top-level [...] (greedy, dotall)
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to parse dispatcher response as JSON: %s", text[:200])
        return []

    @staticmethod
    def _filter_valid(
        items: list[dict[str, Any]],
        valid_ids: set[str],
    ) -> list[dict[str, str]]:
        """Keep only items whose persona_id is in *valid_ids*."""
        result: list[dict[str, str]] = []
        for item in items:
            pid = item.get("persona_id")
            if pid and pid in valid_ids:
                result.append(
                    {
                        "persona_id": str(pid),
                        "reason": str(item.get("reason", "")),
                    }
                )
        return result
