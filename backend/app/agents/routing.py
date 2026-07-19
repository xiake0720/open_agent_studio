from agents import Runner

from backend.app.agents.context import AppRunContext
from backend.app.agents.contracts import RouteDecision
from backend.app.agents.triage_agent import build_route_decision_agent
from backend.app.services.model_factory import BuiltModel


def fallback_route_decision(user_input: str) -> RouteDecision:
    text = user_input.lower()

    compare_words = ("比较", "对比", "评测", "多个模型", "哪个模型", "compare")
    image_words = ("生成图片", "生成一张", "画一张", "画图", "海报", "生图", "flux", "图片提示词")
    tech_words = (
        "traceback", "error", "exception", "报错", "python", "fastapi",
        "react", "typescript", "数据库", "api", "代码", "modulenotfounderror",
        "typeerror", "syntaxerror", "importerror",
    )
    ecommerce_words = (
        "电商", "商品", "标题", "卖点", "文案", "敏感词", "违规词",
        "全网第一", "全网最低", "100%", "绝对", "永久", "转化",
    )

    if any(word in text for word in compare_words):
        return RouteDecision(
            intent="多模型对比评测",
            specialist="compare",
            orchestration_mode="compare_pipeline",
            confidence=0.94,
            reason="输入明确要求比较或评测多个模型。",
        )
    if any(word in text for word in image_words):
        return RouteDecision(
            intent="图片方案或提示词生成",
            specialist="image",
            orchestration_mode="agent_as_tool",
            confidence=0.9,
            reason="输入包含生成图片、海报或图片提示词意图。",
        )
    if any(word in text for word in tech_words):
        return RouteDecision(
            intent="技术问题或报错分析",
            specialist="tech",
            orchestration_mode="agent_as_tool",
            confidence=0.88,
            reason="输入包含代码、报错或工程技术关键词。",
        )
    if any(word in text for word in ecommerce_words):
        return RouteDecision(
            intent="电商文案审核与优化",
            specialist="ecommerce",
            orchestration_mode="agent_as_tool",
            confidence=0.87,
            reason="输入包含商品文案、营销或风险词关键词。",
        )

    return RouteDecision(
        intent="通用问答",
        specialist="general",
        orchestration_mode="direct",
        confidence=0.72,
        reason="未识别到需要专家处理的明确意图。",
    )


async def resolve_route_decision(
    built_model: BuiltModel,
    user_input: str,
    context: AppRunContext,
) -> tuple[RouteDecision, str]:
    """优先由结构化 Triage Agent 路由，失败时使用可解释的规则降级。"""

    try:
        result = await Runner.run(
            build_route_decision_agent(built_model),
            user_input,
            context=context,
            max_turns=2,
        )
        if isinstance(result.final_output, RouteDecision):
            return result.final_output, "agent"
    except Exception:
        pass

    return fallback_route_decision(user_input), "fallback"
