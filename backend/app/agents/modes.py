from enum import StrEnum


class AgentMode(StrEnum):
    """
    系统支持的 Agent 模式。

    StrEnum 同时具备：
    1. Enum 的枚举约束；
    2. str 的字符串行为。
    """

    AUTO = "auto"
    GENERAL = "general"
    TECH = "tech"
    ECOMMERCE = "ecommerce"
    IMAGE = "image"
    COMPARE = "compare"


_AGENT_NAME_BY_MODE: dict[AgentMode, str] = {
    AgentMode.AUTO: "TriageAgent",
    AgentMode.GENERAL: "GeneralAgent",
    AgentMode.TECH: "TechAgent",
    AgentMode.ECOMMERCE: "EcommerceAgent",
    AgentMode.IMAGE: "ImageAgent",
    AgentMode.COMPARE: "CompareAgent",
}

_MODE_BY_AGENT_NAME: dict[str, AgentMode] = {
    agent_name: mode
    for mode, agent_name in _AGENT_NAME_BY_MODE.items()
}


def resolve_agent_mode(
    requested_mode: AgentMode | None,
    conversation_mode: str | None,
) -> AgentMode:
    """
    解析本次运行使用的 Agent 模式。

    优先级：
    1. 本次请求明确传入的模式；
    2. 会话默认模式；
    3. general。
    """

    if requested_mode is not None:
        return requested_mode

    if conversation_mode:
        try:
            return AgentMode(conversation_mode)
        except ValueError:
            pass

    return AgentMode.GENERAL


def agent_name_for_mode(mode: AgentMode) -> str:
    return _AGENT_NAME_BY_MODE[mode]


def mode_from_agent_name(agent_name: str) -> AgentMode:
    try:
        return _MODE_BY_AGENT_NAME[agent_name]
    except KeyError as exc:
        raise ValueError(f"未知 Agent 名称：{agent_name}") from exc