from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from backend.app.agents.modes import AgentMode

class AgentRunResponse(BaseModel):
    id: str
    conversation_id: str
    user_message_id: str | None = None
    model_config_id: str | None = None
    agent_name: str
    model: str
    status: str
    input_text: str
    final_output: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    started_at: datetime
    finished_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AgentRunCreateRequest(BaseModel):
    """
    创建一次流式 Agent 运行。

    注意：
    这里只是创建运行记录，还不会马上执行模型。
    真正执行是在 GET /agent-runs/{run_id}/stream 里完成。
    """

    conversation_id: str = Field(description="会话ID")
    content: str = Field(min_length=1, description="用户输入内容")
    primary_model_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("primary_model_id", "model_config_id"),
        description="模型配置ID。不传则使用会话默认模型或系统默认模型。",
    )
    agent_mode: AgentMode | None = Field(
        default=None,
        description="本次运行使用的 Agent 模式。不传则使用会话默认模式。",
    )
    compare_model_ids: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Compare 模式选择的 2-3 个模型配置ID。",
    )


class AgentRunCreateResponse(BaseModel):
    run_id: str
    conversation_id: str
    user_message_id: str
    model_config_id: str
    model: str
    agent_name: str
    stream_url: str
