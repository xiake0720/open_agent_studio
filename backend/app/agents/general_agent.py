from agents import Agent

from backend.app.services.model_factory import BuiltModel
from backend.app.tools import build_general_tools


def build_general_agent(
    built_model: BuiltModel,
) -> Agent:
    tools = (
        build_general_tools()
        if built_model.config.support_tools
        else []
    )

    return Agent(
        name="GeneralAgent",
        instructions=(
            "你是 OpenAgent Studio 中的通用中文助手。"
            "回答要准确、清晰、结构化。"
            "普通知识问题由你直接回答。"
            "用户询问当前时间时，调用 get_current_time。"
            "用户要求进行数学计算时，调用 calculator。"
            "不要处理专业的代码报错分析和电商合规审核。"
        ),
        model=built_model.model,
        model_settings=built_model.model_settings,
        tools=tools,
    )