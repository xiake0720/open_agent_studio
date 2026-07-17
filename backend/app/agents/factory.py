from agents import Agent

from backend.app.agents.general_agent import build_general_agent
from backend.app.agents.ecommerce_agent import build_ecommerce_agent
from backend.app.agents.image_agent import build_image_agent
from backend.app.agents.modes import AgentMode
from backend.app.agents.tech_agent import build_tech_agent
from backend.app.core.exceptions import AppException
from backend.app.services.model_factory import BuiltModel


class AgentFactory:
    """
    根据 AgentMode 创建对应 Agent。

    类似 Java 中的工厂类。
    """

    def __init__(
        self,
        built_model: BuiltModel,
    ) -> None:
        self._built_model = built_model

    def build(
        self,
        mode: AgentMode,
    ) -> Agent:
        if mode is AgentMode.GENERAL:
            return build_general_agent(self._built_model)

        if mode is AgentMode.TECH:
            return build_tech_agent(self._built_model)

        if mode is AgentMode.ECOMMERCE:
            return build_ecommerce_agent(self._built_model)

        if mode is AgentMode.IMAGE:
            return build_image_agent(self._built_model)

        raise AppException(
            message=f"当前 Agent 模式尚未实现：{mode.value}",
            code=40020,
            data={
                "agent_mode": mode.value,
            },
        )
