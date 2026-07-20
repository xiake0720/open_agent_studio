import re

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user
from backend.app.core.config import DATA_DIR
from backend.app.core.exceptions import AppException
from backend.app.db.session import get_db
from backend.app.models.agent_run import AgentRun
from backend.app.models.user import User
from backend.app.services.conversation_service import get_conversation


router = APIRouter(prefix="/generated", tags=["GeneratedImages"])
_SAFE_FILENAME = re.compile(r"^[0-9a-f-]{36}\.(?:png|jpg|webp)$")


@router.get("/{run_id}/{filename}")
async def get_generated_image(
    run_id: str,
    filename: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = await db.get(AgentRun, run_id)
    if run is None:
        raise AppException(message="Agent运行记录不存在", code=40406)
    await get_conversation(db, run.conversation_id, user.id)
    if not _SAFE_FILENAME.fullmatch(filename):
        raise AppException(message="图片文件名无效", code=40410)
    path = DATA_DIR / "generated" / run_id / filename
    if not path.is_file():
        raise AppException(message="生成图片不存在", code=40410)
    return FileResponse(path)
