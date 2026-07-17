from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import (
    AuthResponse,
    CaptchaResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from backend.app.schemas.response import success
from backend.app.services.auth_service import (
    authenticate_user,
    create_captcha,
    register_user,
    revoke_session,
)


router = APIRouter(prefix="/auth", tags=["Auth"])


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        max_age=settings.AUTH_SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.APP_ENV.lower() not in {"dev", "development", "test", "local"},
        samesite="lax",
        path="/",
    )


@router.post("/register")
async def register_api(
    payload: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user, token, session = await register_user(db, payload.username, payload.password)
    set_session_cookie(response, token)
    data = AuthResponse(user=UserResponse.model_validate(user), expires_at=session.expires_at)
    return success(data.model_dump(mode="json"))


@router.post("/login")
async def login_api(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user, token, session = await authenticate_user(
        db,
        payload.username,
        payload.password,
        payload.captcha_id,
        payload.captcha_code,
    )
    set_session_cookie(response, token)
    data = AuthResponse(user=UserResponse.model_validate(user), expires_at=session.expires_at)
    return success(data.model_dump(mode="json"))


@router.get("/captcha")
async def captcha_api(db: AsyncSession = Depends(get_db)):
    challenge, image_data_uri = await create_captcha(db)
    data = CaptchaResponse(
        captcha_id=challenge.id,
        image_data_uri=image_data_uri,
        expires_in=settings.LOGIN_CAPTCHA_TTL_SECONDS,
    )
    return success(data.model_dump(mode="json"))


@router.get("/me")
async def me_api(user: User = Depends(get_current_user)):
    return success(UserResponse.model_validate(user).model_dump(mode="json"))


@router.post("/logout")
async def logout_api(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    await revoke_session(db, request.cookies.get(settings.AUTH_COOKIE_NAME))
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/", samesite="lax")
    return success(True)

