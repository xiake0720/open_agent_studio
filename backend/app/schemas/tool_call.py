from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ToolCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    sdk_tool_call_id: str | None = None
    seq: int | None = None
    tool_name: str
    arguments_json: Any | None = None
    output: str | None = None
    status: str
    duration_ms: int | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None