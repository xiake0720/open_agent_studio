from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RunEventResponse(BaseModel):
    id: str
    run_id: str
    seq: int
    event_type: str
    event_name: str | None = None
    payload_json: dict[str, Any]
    created_at: datetime