from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ModelCompareResultResponse(BaseModel):
    id: str
    model_config_id: str
    display_name: str
    model_id: str
    status: str
    output_text: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    scores: dict[str, Any] | None = None
    created_at: datetime


class ModelCompareResponse(BaseModel):
    id: str
    run_id: str
    model_config_ids: list[str]
    status: str
    winner_model_config_id: str | None = None
    judge_report: dict[str, Any] | None = None
    results: list[ModelCompareResultResponse]
    created_at: datetime
