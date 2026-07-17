from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.exceptions import AppException
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.services.auth_service import get_user_by_session_token


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await get_user_by_session_token(db, request.cookies.get(settings.AUTH_COOKIE_NAME))
    if user is None:
        raise AppException("请先登录", code=40100, status_code=401)
    return user

