from datetime import datetime

from pydantic import BaseModel, ConfigDict


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