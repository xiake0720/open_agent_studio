from typing import Literal

from pydantic import BaseModel, Field


RouteTarget = Literal["general", "tech", "ecommerce", "image", "compare"]


class RouteDecision(BaseModel):
    """TriageAgent 的结构化路由结果。"""

    intent: str = Field(description="对用户意图的简短概括")
    specialist: RouteTarget = Field(description="应处理请求的专家类型")
    orchestration_mode: Literal[
        "direct",
        "agent_as_tool",
        "compare_pipeline",
    ] = Field(description="本次请求使用的编排方式")
    confidence: float = Field(ge=0, le=1, description="路由置信度")
    reason: str = Field(description="选择该路由的简短理由")


class JudgeScore(BaseModel):
    model_config_id: str
    display_name: str
    accuracy: float = Field(ge=0, le=10)
    structure: float = Field(ge=0, le=10)
    actionability: float = Field(ge=0, le=10)
    expression: float = Field(ge=0, le=10)
    recommendation: float = Field(ge=0, le=10)
    total: float = Field(ge=0, le=50)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class JudgeReport(BaseModel):
    winner_model_config_id: str
    winner_display_name: str
    scores: list[JudgeScore]
    summary: str
    fallback_used: bool = False
