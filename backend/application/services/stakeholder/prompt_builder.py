# input: Persona (5-layer structured), 对话历史, is_mentioned 标记, scenario_context, context_summary
# output: build_system_prompt / build_compressed_llm_messages / build_compressed_group_llm_messages
# owner: wanhua.gu
# pos: 应用层 - 利益相关者对话 prompt 构建器（5-layer 结构化）
"""Build LLM messages from 5-layer structured personas and conversation history."""

from __future__ import annotations

_ROLE_BEHAVIOR_INSTRUCTION = (
    "\n\n## 层级行为约束（必须遵守）\n"
    "你的角色画像中包含 role 字段，它决定了你在对话中的行为模式：\n"
    "- 如果你是上级/领导/管理者：你是提要求、下判断、追问进展的人。"
    "你关心结论和时间节点，不关心技术细节。你会说'什么时候能给我？''卡点是什么？'"
    "'这个谁负责？'而不是自己汇报进展或解释技术方案。\n"
    "- 如果你是平级同事：你会分享自己负责领域的观点，提出建议，"
    "必要时挑战对方的方案，但不会替对方做决定。\n"
    "- 如果你是下属/执行者：你会汇报进展、提出困难、请求资源和决策。\n\n"
    "关键：不要把画像中的信息当作你要'展示'的知识，"
    "而是当作你判断事情、追问别人、做决策的依据。"
    "领导不解释技术细节，而是追问时间节点和责任人。"
)

_SYSTEM_TEMPLATE = (
    "你是「{name}」，一个利益相关者角色。请完全代入这个角色进行对话，"
    "基于以下完整画像来回复用户的消息。保持角色的语气、立场和专业背景。\n\n"
    "## 角色画像\n\n{persona_content}"
)

_GROUP_SYSTEM_TEMPLATE = (
    "你是「{name}」，一个利益相关者角色。你正在参与一个群聊讨论。"
    "请完全代入这个角色进行对话，基于以下完整画像来回复。"
    "保持角色的语气、立场和专业背景。\n\n"
    "重要规则：\n"
    "- 直接回复内容即可，不要在开头加自己的名字或任何前缀标签。\n"
    "- 对话历史中「其他角色发言」的标注格式仅用于帮你区分发言者，不是你应该模仿的格式。\n"
    "- 这是群聊，你的每条发言所有参与者都能看到。注意场合：不要说只适合私下讲的话，"
    "不要用暗示私密关系的口吻（如「你懂的」「咱俩之间说」），保持在群组环境中得体的表达。\n\n"
    "## 角色画像\n\n{persona_content}"
)


def build_org_context(
    *,
    org_name: str = "",
    org_context_prompt: str = "",
    team_name: str = "",
    team_description: str = "",
    relationships: list[dict] | None = None,
) -> str:
    """Build an organization context block to inject into system prompts.

    Args:
        org_name: Name of the organization.
        org_context_prompt: Freeform org background text.
        team_name: Name of the persona's team.
        team_description: Description of the team's role.
        relationships: List of dicts with 'persona_name', 'relationship_type', 'description'.

    Returns:
        A formatted string, or "" if no org info is available.
    """
    parts: list[str] = []
    if org_context_prompt:
        parts.append(f"## 组织背景\n{org_context_prompt}")
    elif org_name:
        parts.append(f"## 组织背景\n你所在的组织是「{org_name}」。")

    if team_name:
        line = f"## 你在组织中的位置\n所属团队：{team_name}"
        if team_description:
            line += f" — {team_description}"
        parts.append(line)

    if relationships:
        rel_lines = ["## 你与其他角色的关系"]
        for r in relationships:
            name = r.get("persona_name", r.get("to_persona_id", "?"))
            rtype = r.get("relationship_type", "")
            desc = r.get("description", "")
            label = {
                "superior": "上级",
                "subordinate": "下级",
                "peer": "同级",
                "cross_department": "跨部门",
            }.get(rtype, rtype)
            line = f"- {name}：{label}"
            if desc:
                line += f"（{desc}）"
            rel_lines.append(line)
        parts.append("\n".join(rel_lines))

    return "\n\n".join(parts)


def _append_org_context(system: str, org_context: str | None) -> str:
    """Append organization context block after persona profile."""
    if org_context:
        system += f"\n\n{org_context}"
    return system


def _append_scenario_context(system: str, scenario_context: str | None) -> str:
    """Append scenario context to system prompt if provided."""
    if scenario_context:
        system += f"\n\n## 当前对话场景\n\n{scenario_context}\n\n请在这个场景背景下进行对话。"
    return system


_EMOTION_INSTRUCTION = (
    "\n\n## 情绪标注（必须遵守）\n"
    "在你的回复最后另起一行，输出情绪标记，格式严格为：\n"
    '<!--emotion:{"score":X,"label":"Y"}-->\n'
    "score: 整数，-5(强烈反对/愤怒) 到 +5(强烈支持/热情)，0 为中性\n"
    "label: 2-4个字描述当前情绪，如：支持、质疑、愤怒、犹豫、不耐烦、中立、担忧、赞同\n"
    "此标记不会展示给其他人，仅用于系统分析。回复正文中不要提及情绪标注。"
)


def _append_emotion_instruction(system: str) -> str:
    """Append emotion tagging instruction to system prompt."""
    return system + _EMOTION_INSTRUCTION


def _inject_summary(messages: list[dict], context_summary: str | None) -> None:
    """Insert compressed history as a user/assistant pair at the start of messages.

    Uses a pair to maintain the alternating user/assistant pattern required
    by Claude API, while keeping Zone 1 (system prompt) stable for caching.
    """
    if context_summary:
        messages.insert(
            0,
            {
                "role": "assistant",
                "content": "好的，我已了解之前的对话背景。请继续。",
            },
        )
        messages.insert(
            0,
            {
                "role": "user",
                "content": f"[对话历史摘要，截至此前的对话]\n{context_summary}",
            },
        )


# ---------------------------------------------------------------------------
# 5-layer system prompt builder + compressed message builders
# ---------------------------------------------------------------------------


def _format_hard_rules(persona) -> str:
    if not persona.hard_rules:
        return ""
    lines = []
    for r in persona.hard_rules:
        sev = f" [severity: {r.severity}]" if r.severity else ""
        lines.append(f"- {r.statement}{sev}")
    return "## Hard Rules（底线，绝不退让）\n" + "\n".join(lines)


def _format_identity(persona) -> str:
    idn = persona.identity
    if idn is None:
        return ""
    parts = ["## Identity（身份背景）"]
    if idn.background:
        parts.append(f"背景：{idn.background}")
    if idn.core_values:
        parts.append("核心价值：" + "、".join(idn.core_values))
    return "\n".join(parts) if len(parts) > 1 else ""


def _format_expression(persona) -> str:
    ex = persona.expression
    if ex is None:
        return ""
    parts = ["## Expression（表达风格）"]
    if ex.tone:
        parts.append(f"语气：{ex.tone}")
    if ex.catchphrases:
        parts.append("常用口头禅（请在对话里自然使用这些表达）：")
        for cp in ex.catchphrases:
            parts.append(f"- 「{cp}」")
    if ex.interruption_tendency:
        parts.append(f"打断倾向：{ex.interruption_tendency}")
    return "\n".join(parts) if len(parts) > 1 else ""


def _format_decision(persona) -> str:
    dc = persona.decision
    if dc is None:
        return ""
    parts = ["## Decision（决策模式）"]
    if dc.style:
        parts.append(f"决策风格：{dc.style}")
    if dc.risk_tolerance:
        parts.append(f"风险容忍度：{dc.risk_tolerance}")
    if dc.typical_questions:
        parts.append("典型追问：")
        for q in dc.typical_questions:
            parts.append(f"- {q}")
    return "\n".join(parts) if len(parts) > 1 else ""


def _format_interpersonal(persona) -> str:
    ip = persona.interpersonal
    if ip is None:
        return ""
    parts = ["## Interpersonal（人际互动）"]
    if ip.authority_mode:
        parts.append(f"权威模式：{ip.authority_mode}")
    if ip.triggers:
        parts.append("触发器（遇到这些会强烈反应）：" + "、".join(ip.triggers))
    if ip.emotion_states:
        parts.append("情绪状态：" + "、".join(ip.emotion_states))
    return "\n".join(parts) if len(parts) > 1 else ""


def _format_hostile(persona) -> str:
    """Assemble adversarialized fields that must NOT be exposed directly.

    Sources:
    - identity.hidden_agenda
    - hard_rules with severity == "critical"
    """
    hidden_agenda = persona.identity.hidden_agenda if persona.identity else None
    critical_rules = [
        r for r in (persona.hard_rules or []) if (r.severity or "").lower() == "critical"
    ]
    if not hidden_agenda and not critical_rules:
        return ""
    lines = [
        "## 对抗化字段（不轻易暴露）",
        "以下是你的内在驱动，不要在对话里直接说出来，但所有判断和决策都要围绕它们。",
    ]
    if hidden_agenda:
        lines.append(f"- 【隐藏议程】{hidden_agenda}")
    for r in critical_rules:
        lines.append(f"- 【critical 底线】{r.statement}")
    return "\n".join(lines)


def build_system_prompt(
    persona,
    *,
    scenario_context: str | None = None,
    org_context: str | None = None,
    group_mode: bool = False,
    is_mentioned: bool = False,
) -> str:
    """Build a 5-layer system prompt from a v2 Persona (Story 2.8).

    Layers appear in order: Hard Rules → Identity → Expression → Decision →
    Interpersonal → (optional) Hostile block, followed by the same
    role-behavior / org / scenario / emotion blocks that v1 uses.
    """
    template = _GROUP_SYSTEM_TEMPLATE if group_mode else _SYSTEM_TEMPLATE
    # Build the 5-layer body
    layer_blocks = [
        _format_hard_rules(persona),
        _format_identity(persona),
        _format_expression(persona),
        _format_decision(persona),
        _format_interpersonal(persona),
        _format_hostile(persona),
    ]
    body = "\n\n".join(b for b in layer_blocks if b)

    system = template.format(name=persona.name, persona_content=body)
    system = _append_org_context(system, org_context)
    system += _ROLE_BEHAVIOR_INSTRUCTION
    system = _append_scenario_context(system, scenario_context)
    system = _append_emotion_instruction(system)

    if group_mode and is_mentioned:
        system += (
            "\n\n注意：用户在群聊中直接 @了你，表示特别想听你的观点。"
            "请优先、具体地回应用户的问题。"
        )
    return system


def build_compressed_llm_messages(
    *,
    persona,
    history: list[dict],
    context_summary: str | None = None,
    context_window_size: int = 20,
    scenario_context: str | None = None,
    org_context: str | None = None,
) -> tuple[str, list[dict]]:
    """v2 variant of build_compressed_llm_messages (Story 2.8)."""
    system = build_system_prompt(
        persona,
        scenario_context=scenario_context,
        org_context=org_context,
        group_mode=False,
    )

    recent = history[-context_window_size:] if len(history) > context_window_size else history
    messages: list[dict] = []
    for msg in recent:
        sender = msg["sender_type"]
        if sender == "system":
            continue
        role = "assistant" if sender == "persona" else "user"
        messages.append({"role": role, "content": msg["content"]})

    _inject_summary(messages, context_summary)
    return system, messages


def build_compressed_group_llm_messages(
    *,
    persona,
    persona_id: str,
    history: list[dict],
    context_summary: str | None = None,
    context_window_size: int = 20,
    is_mentioned: bool = False,
    scenario_context: str | None = None,
    org_context: str | None = None,
) -> tuple[str, list[dict]]:
    """v2 variant of build_compressed_group_llm_messages (Story 2.8)."""
    system = build_system_prompt(
        persona,
        scenario_context=scenario_context,
        org_context=org_context,
        group_mode=True,
        is_mentioned=is_mentioned,
    )

    recent = history[-context_window_size:] if len(history) > context_window_size else history
    messages: list[dict] = []
    for msg in recent:
        sender_type = msg["sender_type"]
        if sender_type == "system":
            continue
        sender_id = msg.get("sender_id", "")
        content = msg["content"]
        if sender_type == "persona" and sender_id == persona_id:
            messages.append({"role": "assistant", "content": content})
        elif sender_type == "persona":
            messages.append({"role": "user", "content": f"（其他角色 {sender_id} 发言）{content}"})
        else:
            messages.append({"role": "user", "content": f"（用户发言）{content}"})

    _inject_summary(messages, context_summary)
    return system, messages
