from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.schemas.response import success
from backend.app.services.model_config_service import (
    list_model_configs,
)

router = APIRouter(
    prefix="/models",
    tags=["Models"],
)


@router.get("")
async def list_models_api(
        enabled_only: bool = Query(default=True, description="是否只查询启用的模型"),
        db: AsyncSession = Depends(get_db),
):
    """
    查询模型配置列表。

    前端模型下拉框使用。
    """

    model_configs = await list_model_configs(
        db=db,
        enabled_only=enabled_only,
    )

    data = [
        # ModelConfigResponse.model_validate(item).model_dump(mode="json")
        {"id": item.id, "name": item.display_name}
        for item in model_configs
    ]

    return success(data)

# 注释原因，这个接口容易暴漏模型配置，也不需要获取单独的模型信息
# @router.get("/{model_config_id}")
# async def get_model_api(
#     model_config_id: str,
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     查询单个模型配置。
#     """
#
#     model_config = await get_model_config(
#         db=db,
#         model_config_id=model_config_id,
#     )
#
#     return success(
#         ModelConfigResponse.model_validate(model_config).model_dump(mode="json")
#     )
