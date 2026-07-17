import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_admin
from backend.app.api.v1.auth import set_session_cookie
from backend.app.core.config import settings
from backend.app.core.exceptions import AppException
from backend.app.db.session import get_db
from backend.app.models.agent_run import AgentRun
from backend.app.models.auth_session import AuthSession
from backend.app.models.conversation import Conversation
from backend.app.models.message import Message
from backend.app.models.model_config import ModelConfig
from backend.app.models.system_exception import SystemException
from backend.app.models.token_usage import TokenUsage
from backend.app.models.user import User
from backend.app.schemas.admin import (
    AdminExceptionUpdate,
    AdminLoginRequest,
    AdminModelCreate,
    AdminModelUpdate,
    AdminUserUpdate,
)
from backend.app.schemas.response import success
from backend.app.services.auth_service import authenticate_user, revoke_session
from backend.app.services.system_exception_service import mark_exception_resolved


router = APIRouter(prefix="/admin", tags=["Admin"])


def set_admin_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.ADMIN_AUTH_COOKIE_NAME,
        value=token,
        max_age=settings.AUTH_SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.APP_ENV.lower() not in {"dev", "development", "test", "local"},
        samesite="lax",
        path="/",
    )


def model_data(item: ModelConfig) -> dict:
    return {
        "id": item.id,
        "provider": item.provider,
        "display_name": item.display_name,
        "model_id": item.model_id,
        "base_url": item.base_url,
        "api_key_env": item.api_key_env,
        "api_shape": item.api_shape,
        "support_streaming": item.support_streaming,
        "support_tools": item.support_tools,
        "support_image": item.support_image,
        "enabled": item.enabled,
        "extra_body_json": item.extra_body_json,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def validate_extra_json(value: str | None) -> None:
    if value:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise AppException("额外参数必须是合法 JSON", code=42210, status_code=422) from exc
        if not isinstance(parsed, dict):
            raise AppException("额外参数必须是 JSON 对象", code=42211, status_code=422)


@router.post("/auth/login")
async def admin_login_api(
    payload: AdminLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user, token, session = await authenticate_user(db, payload.username, payload.password, None, None)
    if not user.is_admin:
        await revoke_session(db, token)
        raise AppException("该账号没有管理员权限", code=40310, status_code=403)
    set_admin_cookie(response, token)
    return success({
        "user": {"id": user.id, "username": user.username, "is_admin": True},
        "expires_at": session.expires_at,
    })


@router.get("/auth/me")
async def admin_me_api(admin: User = Depends(get_current_admin)):
    return success({"id": admin.id, "username": admin.username, "is_admin": True})


@router.post("/auth/logout")
async def admin_logout_api(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    await revoke_session(db, request.cookies.get(settings.ADMIN_AUTH_COOKIE_NAME))
    response.delete_cookie(settings.ADMIN_AUTH_COOKIE_NAME, path="/", samesite="lax")
    return success(True)


@router.get("/overview")
async def overview_api(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    user_count = int(await db.scalar(select(func.count(User.id)).where(User.is_admin.is_(False))) or 0)
    active_users = int(await db.scalar(select(func.count(User.id)).where(User.is_admin.is_(False), User.is_active.is_(True))) or 0)
    conversation_count = int(await db.scalar(select(func.count(Conversation.id))) or 0)
    run_count = int(await db.scalar(select(func.count(AgentRun.id))) or 0)
    failed_runs = int(await db.scalar(select(func.count(AgentRun.id)).where(AgentRun.status == "failed")) or 0)
    total_tokens = int(await db.scalar(select(func.coalesce(func.sum(TokenUsage.total_tokens), 0))) or 0)
    unresolved = int(await db.scalar(select(func.count(SystemException.id)).where(SystemException.resolved.is_(False))) or 0)
    return success({
        "users": user_count,
        "active_users": active_users,
        "conversations": conversation_count,
        "runs": run_count,
        "failed_runs": failed_runs,
        "total_tokens": total_tokens,
        "unresolved_exceptions": unresolved,
    })


@router.get("/users")
async def list_users_api(
    query: str = Query(default="", max_length=64),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    conversation_count = select(func.count(Conversation.id)).where(Conversation.user_id == User.id).correlate(User).scalar_subquery()
    stmt = select(User, conversation_count.label("conversation_count")).where(User.is_admin.is_(False))
    if query.strip():
        stmt = stmt.where(User.username_key.contains(query.strip().casefold()))
    rows = (await db.execute(stmt.order_by(User.created_at.desc()).offset(offset).limit(limit))).all()
    return success([{
        "id": user.id,
        "username": user.username,
        "is_active": user.is_active,
        "failed_login_attempts": user.failed_login_attempts,
        "conversation_count": int(count or 0),
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
    } for user, count in rows])


@router.patch("/users/{user_id}")
async def update_user_api(
    user_id: str,
    payload: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    user = await db.get(User, user_id)
    if user is None or user.is_admin:
        raise AppException("用户不存在", code=40420, status_code=404)
    user.is_active = payload.is_active
    if not payload.is_active:
        sessions = (await db.scalars(select(AuthSession).where(AuthSession.user_id == user.id))).all()
        for session in sessions:
            await db.delete(session)
    await db.commit()
    return success({"id": user.id, "is_active": user.is_active})


@router.get("/token-stats")
async def token_stats_api(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    start = date_from or datetime.utcnow() - timedelta(days=29)
    end = date_to or datetime.utcnow() + timedelta(days=1)
    filters = (TokenUsage.created_at >= start, TokenUsage.created_at < end)
    summary = (await db.execute(select(
        func.coalesce(func.sum(TokenUsage.input_tokens), 0),
        func.coalesce(func.sum(TokenUsage.output_tokens), 0),
        func.coalesce(func.sum(TokenUsage.total_tokens), 0),
    ).where(*filters))).one()
    model_rows = (await db.execute(select(
        TokenUsage.model,
        func.sum(TokenUsage.input_tokens),
        func.sum(TokenUsage.output_tokens),
        func.sum(TokenUsage.total_tokens),
        func.count(TokenUsage.id),
    ).where(*filters).group_by(TokenUsage.model).order_by(func.sum(TokenUsage.total_tokens).desc()))).all()
    day_expr = func.date(TokenUsage.created_at)
    day_rows = (await db.execute(select(
        day_expr,
        func.sum(TokenUsage.input_tokens),
        func.sum(TokenUsage.output_tokens),
        func.sum(TokenUsage.total_tokens),
    ).where(*filters).group_by(day_expr).order_by(day_expr.asc()))).all()
    return success({
        "date_from": start,
        "date_to": end,
        "summary": {"input_tokens": int(summary[0]), "output_tokens": int(summary[1]), "total_tokens": int(summary[2])},
        "by_model": [{"model": row[0], "input_tokens": int(row[1] or 0), "output_tokens": int(row[2] or 0), "total_tokens": int(row[3] or 0), "requests": int(row[4] or 0)} for row in model_rows],
        "by_time": [{"date": str(row[0]), "input_tokens": int(row[1] or 0), "output_tokens": int(row[2] or 0), "total_tokens": int(row[3] or 0)} for row in day_rows],
    })


@router.get("/models")
async def admin_models_api(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin)):
    items = (await db.scalars(select(ModelConfig).order_by(ModelConfig.provider, ModelConfig.display_name))).all()
    return success([model_data(item) for item in items])


@router.post("/models")
async def create_model_api(
    payload: AdminModelCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    validate_extra_json(payload.extra_body_json)
    exists = await db.scalar(select(ModelConfig.id).where(ModelConfig.provider == payload.provider, ModelConfig.model_id == payload.model_id))
    if exists:
        raise AppException("该模型配置已存在", code=40920, status_code=409)
    item = ModelConfig(**payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return success(model_data(item))


@router.put("/models/{model_id}")
async def update_model_api(
    model_id: str,
    payload: AdminModelUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    validate_extra_json(payload.extra_body_json)
    item = await db.get(ModelConfig, model_id)
    if item is None:
        raise AppException("模型配置不存在", code=40421, status_code=404)
    duplicate = await db.scalar(select(ModelConfig.id).where(ModelConfig.provider == payload.provider, ModelConfig.model_id == payload.model_id, ModelConfig.id != model_id))
    if duplicate:
        raise AppException("该模型配置已存在", code=40920, status_code=409)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    await db.commit()
    await db.refresh(item)
    return success(model_data(item))


@router.get("/conversations")
async def admin_conversations_api(
    query: str = Query(default="", max_length=100),
    user_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    message_count = select(func.count(Message.id)).where(Message.conversation_id == Conversation.id).correlate(Conversation).scalar_subquery()
    run_count = select(func.count(AgentRun.id)).where(AgentRun.conversation_id == Conversation.id).correlate(Conversation).scalar_subquery()
    stmt = select(Conversation, User.username, message_count.label("message_count"), run_count.label("run_count")).outerjoin(User, User.id == Conversation.user_id)
    if user_id:
        stmt = stmt.where(Conversation.user_id == user_id)
    if query.strip():
        keyword = f"%{query.strip()}%"
        stmt = stmt.where(or_(Conversation.title.ilike(keyword), User.username.ilike(keyword)))
    rows = (await db.execute(stmt.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit))).all()
    return success([{
        "id": item.id,
        "title": item.title,
        "username": username or "历史数据",
        "user_id": item.user_id,
        "agent_mode": item.agent_mode,
        "default_model": item.default_model,
        "message_count": int(messages or 0),
        "run_count": int(runs or 0),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    } for item, username, messages, runs in rows])


@router.get("/conversations/{conversation_id}")
async def admin_conversation_detail_api(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise AppException("会话不存在", code=40422, status_code=404)
    messages = (await db.scalars(select(Message).where(Message.conversation_id == conversation_id, Message.is_visible.is_(True)).order_by(Message.sequence_no, Message.created_at).limit(500))).all()
    return success({
        "conversation": {"id": conversation.id, "title": conversation.title, "agent_mode": conversation.agent_mode, "default_model": conversation.default_model, "created_at": conversation.created_at},
        "messages": [{"id": item.id, "role": item.role, "content": item.content, "model": item.model, "agent_name": item.agent_name, "created_at": item.created_at} for item in messages],
    })


@router.get("/exceptions")
async def admin_exceptions_api(
    resolved: bool | None = None,
    category: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    stmt = select(SystemException)
    if resolved is not None:
        stmt = stmt.where(SystemException.resolved.is_(resolved))
    if category:
        stmt = stmt.where(SystemException.category == category)
    items = (await db.scalars(stmt.order_by(SystemException.created_at.desc()).offset(offset).limit(limit))).all()
    return success([{
        "id": item.id,
        "level": item.level,
        "category": item.category,
        "method": item.method,
        "path": item.path,
        "status_code": item.status_code,
        "error_code": item.error_code,
        "message": item.message,
        "detail": item.detail,
        "traceback": item.traceback_text,
        "user_id": item.user_id,
        "run_id": item.run_id,
        "resolved": item.resolved,
        "resolved_at": item.resolved_at,
        "created_at": item.created_at,
    } for item in items])


@router.patch("/exceptions/{exception_id}")
async def update_exception_api(
    exception_id: str,
    payload: AdminExceptionUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    item = await db.get(SystemException, exception_id)
    if item is None:
        raise AppException("异常记录不存在", code=40423, status_code=404)
    mark_exception_resolved(item, payload.resolved)
    await db.commit()
    return success({"id": item.id, "resolved": item.resolved, "resolved_at": item.resolved_at})
