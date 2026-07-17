from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.token_usage import TokenUsage


def extract_token_usage(result: Any) -> tuple[int, int, int]:
    usage = getattr(getattr(result, "context_wrapper", None), "usage", None)
    if usage is None:
        return 0, 0, 0
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or input_tokens + output_tokens)
    return input_tokens, output_tokens, total_tokens


async def record_token_usage(
    db: AsyncSession,
    *,
    run_id: str | None,
    model_config_id: str | None,
    model: str,
    usage_type: str,
    usage: tuple[int, int, int],
) -> TokenUsage | None:
    input_tokens, output_tokens, total_tokens = usage
    if total_tokens <= 0 and input_tokens <= 0 and output_tokens <= 0:
        return None
    item = TokenUsage(
        run_id=run_id,
        model_config_id=model_config_id,
        model=model,
        usage_type=usage_type,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens or input_tokens + output_tokens,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item
