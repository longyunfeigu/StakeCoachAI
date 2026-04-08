# input: persona full_content, 对话历史, is_mentioned 标记, scenario_context 场景上下文
# output: build_llm_messages() 私聊 prompt, build_group_llm_messages() 群聊 prompt（区分当前角色 vs 其他角色, @提及增强, 场景上下文注入）
# owner: wanhua.gu
# pos: 应用层 - 利益相关者对话 prompt 构建器（私聊 + 群聊）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Build LLM messages from persona profile and conversation history."""

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


def build_llm_messages(
    *,
    persona_full_content: str,
    persona_name: str,
    history: list[dict],
    scenario_context: str | None = None,
    org_context: str | None = None,
) -> tuple[str, list[dict]]:
    """Build system prompt and message list for LLM call.

    Args:
        persona_full_content: Full markdown content of the persona file.
        persona_name: Display name of the persona.
        history: List of dicts with 'sender_type' and 'content' keys.
        org_context: Pre-built organization context block.

    Returns:
        (system_prompt, messages) where messages use 'role'/'content' format.
        sender_type 'persona' maps to 'assistant', 'system' messages are excluded.
    """
    system = _SYSTEM_TEMPLATE.format(
        name=persona_name,
        persona_content=persona_full_content,
    )
    system = _append_org_context(system, org_context)
    system += _ROLE_BEHAVIOR_INSTRUCTION
    system = _append_scenario_context(system, scenario_context)
    system = _append_emotion_instruction(system)

    messages = []
    for msg in history:
        sender = msg["sender_type"]
        if sender == "system":
            continue
        role = "assistant" if sender == "persona" else "user"
        messages.append({"role": role, "content": msg["content"]})

    return system, messages


def build_group_llm_messages(
    *,
    persona_full_content: str,
    persona_name: str,
    persona_id: str,
    history: list[dict],
    is_mentioned: bool = False,
    scenario_context: str | None = None,
    org_context: str | None = None,
) -> tuple[str, list[dict]]:
    """Build prompt for a persona in a group chat context.

    Unlike the private-chat variant, this distinguishes between the current
    persona's own messages (→ assistant) and other personas' messages
    (→ user with a ``[sender_id]: ...`` prefix so the model knows who spoke).

    Args:
        persona_full_content: Full markdown content of the persona file.
        persona_name: Display name of the persona.
        persona_id: ID of the current persona being prompted.
        history: List of dicts with 'sender_type', 'sender_id', and 'content'.
        is_mentioned: Whether the user @mentioned this persona directly.
        org_context: Pre-built organization context block.

    Returns:
        (system_prompt, messages) where messages use 'role'/'content' format.
    """
    system = _GROUP_SYSTEM_TEMPLATE.format(
        name=persona_name,
        persona_content=persona_full_content,
    )
    system = _append_org_context(system, org_context)
    system += _ROLE_BEHAVIOR_INSTRUCTION
    system = _append_scenario_context(system, scenario_context)
    system = _append_emotion_instruction(system)

    if is_mentioned:
        system += (
            "\n\n注意：用户在群聊中直接 @了你，表示特别想听你的观点。"
            "请优先、具体地回应用户的问题。"
        )

    messages = []
    for msg in history:
        sender_type = msg["sender_type"]
        if sender_type == "system":
            continue

        sender_id = msg.get("sender_id", "")
        content = msg["content"]

        if sender_type == "persona" and sender_id == persona_id:
            # Current persona's own messages → assistant
            messages.append({"role": "assistant", "content": content})
        elif sender_type == "persona":
            # Other persona's messages → user with clear label
            messages.append({"role": "user", "content": f"（其他角色 {sender_id} 发言）{content}"})
        else:
            # User messages → user with label to distinguish from persona messages
            messages.append({"role": "user", "content": f"（用户发言）{content}"})

    return system, messages
