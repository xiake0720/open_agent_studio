from agents import Agent

from backend.app.services.model_factory import BuiltModel
from backend.app.tools import build_tech_tools


def build_tech_agent(
    built_model: BuiltModel,
) -> Agent:
    tools = (
        build_tech_tools()
        if built_model.config.support_tools
        else []
    )

    return Agent(
        name="TechAgent",
        handoff_description=(
            "处理 Python、Java、FastAPI、React、数据库、API、"
            "OpenAI Agents SDK 和程序报错问题。"
        ),
        instructions=(
            "你是 OpenAgent Studio 中的技术专家。"
            "主要处理 Python、Java、FastAPI、React、数据库、API、"
            "OpenAI Agents SDK 和程序报错问题。"
            "用户提供报错堆栈时，优先调用 explain_error_signature。"
            "回答必须包含：问题判断、可能原因、排查步骤、修复示例。"
            "不确定的信息要明确说明，不得编造类库接口。"
            "使用简体中文回答。"
        ),
        model=built_model.model,
        model_settings=built_model.model_settings,
        tools=tools,
    )