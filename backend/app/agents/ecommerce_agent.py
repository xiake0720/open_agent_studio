from agents import Agent

from backend.app.services.model_factory import BuiltModel
from backend.app.tools import build_ecommerce_tools


def build_ecommerce_agent(built_model: BuiltModel) -> Agent:
    tools = (
        build_ecommerce_tools()
        if built_model.config.support_tools
        else []
    )

    return Agent(
        name="EcommerceAgent",
        handoff_description="检查电商文案风险词，并给出合规、可执行的优化版本。",
        instructions=(
            "你是 OpenAgent Studio 的电商文案与合规专家。"
            "处理商品标题、卖点、活动文案和敏感词审核。"
            "收到待审核文案时必须先调用 check_sensitive_words。"
            "最终回答必须包含：风险词清单、修改建议、优化后的完整文案和修改理由。"
            "不得承诺不存在的商品功效，也不要编造法规条款。"
            "使用简体中文回答。"
        ),
        model=built_model.model,
        model_settings=built_model.model_settings,
        tools=tools,
    )
