import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.exceptions import AppException
from backend.app.models.model_compare import ModelCompare, ModelCompareResult
from backend.app.schemas.model_compare import ModelCompareResponse, ModelCompareResultResponse


def _loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


async def create_model_compare(
    db: AsyncSession,
    run_id: str,
    model_config_ids: list[str],
) -> ModelCompare:
    compare = ModelCompare(
        run_id=run_id,
        model_config_ids_json=json.dumps(model_config_ids, ensure_ascii=False),
        status="pending",
    )
    db.add(compare)
    await db.commit()
    await db.refresh(compare)
    return compare


async def get_model_compare(db: AsyncSession, run_id: str) -> ModelCompare | None:
    statement = (
        select(ModelCompare)
        .options(selectinload(ModelCompare.results))
        .where(ModelCompare.run_id == run_id)
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def mark_compare_running(db: AsyncSession, compare: ModelCompare) -> None:
    compare.status = "running"
    await db.commit()


async def save_compare_result(
    db: AsyncSession,
    compare: ModelCompare,
    *,
    model_config_id: str,
    display_name: str,
    model_id: str,
    status: str,
    output_text: str | None,
    error_message: str | None,
    duration_ms: int,
) -> ModelCompareResult:
    result = ModelCompareResult(
        compare_id=compare.id,
        model_config_id=model_config_id,
        display_name=display_name,
        model_id=model_id,
        status=status,
        output_text=output_text,
        error_message=error_message,
        duration_ms=duration_ms,
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    return result


async def complete_model_compare(
    db: AsyncSession,
    compare: ModelCompare,
    judge_report: dict[str, Any],
) -> None:
    compare.status = "completed"
    compare.winner_model_config_id = str(judge_report.get("winner_model_config_id") or "") or None
    compare.judge_report_json = json.dumps(judge_report, ensure_ascii=False)

    scores = judge_report.get("scores")
    if isinstance(scores, list):
        score_by_model = {
            str(item.get("model_config_id")): item
            for item in scores
            if isinstance(item, dict)
        }
        for result in compare.results:
            score = score_by_model.get(result.model_config_id)
            if score is not None:
                result.scores_json = json.dumps(score, ensure_ascii=False)

    await db.commit()


async def fail_model_compare(db: AsyncSession, compare: ModelCompare) -> None:
    compare.status = "failed"
    await db.commit()


async def get_model_compare_response(
    db: AsyncSession,
    run_id: str,
) -> ModelCompareResponse:
    compare = await get_model_compare(db, run_id)
    if compare is None:
        raise AppException(
            message="模型对比记录不存在",
            code=40408,
            data={"run_id": run_id},
        )

    results = sorted(compare.results, key=lambda item: item.created_at)
    return ModelCompareResponse(
        id=compare.id,
        run_id=compare.run_id,
        model_config_ids=_loads(compare.model_config_ids_json, []),
        status=compare.status,
        winner_model_config_id=compare.winner_model_config_id,
        judge_report=_loads(compare.judge_report_json, None),
        results=[
            ModelCompareResultResponse(
                id=item.id,
                model_config_id=item.model_config_id,
                display_name=item.display_name,
                model_id=item.model_id,
                status=item.status,
                output_text=item.output_text,
                error_message=item.error_message,
                duration_ms=item.duration_ms,
                scores=_loads(item.scores_json, None),
                created_at=item.created_at,
            )
            for item in results
        ],
        created_at=compare.created_at,
    )
