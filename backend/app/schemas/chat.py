from pydantic import AliasChoices, BaseModel, Field
from backend.app.agents.modes import AgentMode

class ChatRequest(BaseModel):
    """
    普通聊天请求。

    Day 8 暂时不做流式，只返回完整回答。
    """

    conversation_id: str = Field(description="会话ID")
    content: str = Field(min_length=1, description="用户输入内容")
    primary_model_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("primary_model_id", "model_config_id"),
        description="模型配置ID。不传则使用默认模型。",
    )
    agent_mode: AgentMode | None = Field(
        default=None,
        description="本次运行使用的 Agent 模式。",
    )

class ChatResponse(BaseModel):
    run_id: str
    conversation_id: str
    user_message_id: str
    assistant_message_id: str
    model_config_id: str
    model: str
    agent_name: str
    final_output: str
