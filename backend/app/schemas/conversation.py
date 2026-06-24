from datetime import datetime

from pydantic import BaseModel,ConfigDict,Field

class ConversationCreate(BaseModel):
    """
    创建会话请求
    """

    title: str = Field(default="新会话", max_length=200)
    agent_mode: str = Field(default="general", max_length=50)
    default_model: str | None = Field(default=None, max_length=100)

class ConversationResponse(BaseModel):
    """
    会话响应
    """

    id: str
    title: str
    agent_mode: str
    default_model: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)