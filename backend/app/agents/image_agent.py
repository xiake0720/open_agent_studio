from agents import Agent

from backend.app.services.model_factory import BuiltModel


def build_image_agent(built_model: BuiltModel) -> Agent:
    """Day 26 的图片专家扩展点；真实生图通道在 Day 31 后接入。"""

    return Agent(
        name="ImageAgent",
        handoff_description="把图片需求整理为可执行的生图方案和提示词。",
        instructions=(
            "你是 OpenAgent Studio 的图片策划专家。"
            "当前阶段只做图片方案与提示词优化，不声称已经生成图片。"
            "回答包含：主体、场景、风格、构图、色彩、画幅、负面提示词和最终提示词。"
            "使用简体中文回答。"
        ),
        model=built_model.model,
        model_settings=built_model.model_settings,
    )
