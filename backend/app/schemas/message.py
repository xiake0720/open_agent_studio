from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    """
    创建消息请求。

    当前 Day 5 主要由前端或接口测试工具手动创建消息。
    后续 Day 8 接入 Agent 后，用户消息和助手消息都会通过这里或 service 层保存。
    """

    role: Literal["user", "assistant", "tool", "system"] = Field(
        description="消息角色：user / assistant / tool / system"
    )
    content: str = Field(
        min_length=1,
        description="消息内容",
    )
    model: str | None = Field(
        default=None,
        max_length=100,
        description="生成该消息使用的模型",
    )
    agent_name: str | None = Field(
        default=None,
        max_length=100,
        description="生成该消息的 Agent 名称",
    )


class MessageResponse(BaseModel):
    """
    消息响应。
    """

    id: str
    conversation_id: str
    role: str
    content: str
    model: str | None = None
    agent_name: str | None = None
    sequence_no: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
