from agents import Agent

from backend.app.services.model_factory import BuiltModel
from backend.app.tools import build_image_tools


def build_image_agent(built_model: BuiltModel) -> Agent:
    tools = build_image_tools() if built_model.config.support_tools else []

    return Agent(
        name="ImageAgent",
        handoff_description="把图片需求整理为可执行的生图方案和提示词。",
        instructions=(
            "你是 OpenAgent Studio 的图片策划专家。"
            "先把用户需求整理为清晰的英文生图提示词，再调用 generate_flux_image。"
            "用户没有指定尺寸时使用 1024x1024、seed=0、steps=4。"
            "工具成功后必须在最终回答中使用 Markdown 图片语法展示返回的 url，"
            "并简要列出主体、风格、构图、色彩和实际参数。"
            "工具失败时如实说明，不得声称图片已经生成。"
            "使用简体中文回答。"
        ),
        model=built_model.model,
        model_settings=built_model.model_settings,
        tools=tools,
    )
