import base64
import hashlib
import hmac
import html
import secrets
import string
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.exceptions import AppException
from backend.app.models.auth_session import AuthSession
from backend.app.models.conversation import Conversation
from backend.app.models.login_challenge import LoginChallenge
from backend.app.models.user import User


SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
DUMMY_PASSWORD_HASH = (
    "scrypt$16384$8$1$00000000000000000000000000000000$"
    "8c8399f165a2b53a2b512849409c65ce2e8909734f499482217b815edcc20247"
)


def utcnow() -> datetime:
    return datetime.utcnow()


def username_key(username: str) -> str:
    return username.strip().casefold()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, expected_hex = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(expected_hex)),
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected_hex))
    except (ValueError, TypeError):
        return False


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def hash_captcha(answer: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{answer.upper()}".encode("utf-8")).hexdigest()


async def create_session(db: AsyncSession, user: User) -> tuple[str, AuthSession]:
    token = secrets.token_urlsafe(32)
    expires_at = utcnow() + timedelta(days=settings.AUTH_SESSION_DAYS)
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=expires_at,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return token, session


async def register_user(db: AsyncSession, username: str, password: str) -> tuple[User, str, AuthSession]:
    key = username_key(username)
    if key == username_key(settings.DEFAULT_ADMIN_USERNAME):
        raise AppException("该用户名为管理员保留账号", code=40902, status_code=409)
    existing = await db.scalar(select(User.id).where(User.username_key == key))
    if existing is not None:
        raise AppException("用户名已被注册", code=40901, status_code=409)

    # 默认管理员不占用“首个普通用户”名额；首个注册用户仍应接管旧库中的无主会话。
    user_count = int(
        await db.scalar(select(func.count(User.id)).where(User.is_admin.is_(False))) or 0
    )
    user = User(username=username.strip(), username_key=key, password_hash=hash_password(password))
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError as exc:
        await db.rollback()
        raise AppException("用户名已被注册", code=40901, status_code=409) from exc

    # 升级前的历史会话归首个注册用户，避免部署认证后原数据消失。
    if user_count == 0:
        await db.execute(
            update(Conversation).where(Conversation.user_id.is_(None)).values(user_id=user.id)
        )
        await db.commit()

    token, session = await create_session(db, user)
    return user, token, session


async def create_captcha(db: AsyncSession) -> tuple[LoginChallenge, str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    answer = "".join(secrets.choice(alphabet) for _ in range(5))
    salt = secrets.token_hex(16)
    challenge = LoginChallenge(
        answer_hash=hash_captcha(answer, salt),
        answer_salt=salt,
        expires_at=utcnow() + timedelta(seconds=settings.LOGIN_CAPTCHA_TTL_SECONDS),
    )
    db.add(challenge)
    await db.execute(delete(LoginChallenge).where(LoginChallenge.expires_at < utcnow() - timedelta(days=1)))
    await db.commit()
    await db.refresh(challenge)

    escaped = html.escape(answer)
    lines = "".join(
        f'<line x1="{secrets.randbelow(180)}" y1="{secrets.randbelow(58)}" '
        f'x2="{secrets.randbelow(180)}" y2="{secrets.randbelow(58)}" '
        f'stroke="#{secrets.choice(("38bdf8", "5eead4", "a78bfa", "64748b"))}" opacity=".45" />'
        for _ in range(7)
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="180" height="58" viewBox="0 0 180 58">'
        '<rect width="180" height="58" rx="12" fill="#0f172a"/>'
        f'{lines}<text x="90" y="39" text-anchor="middle" fill="#e2e8f0" '
        'font-family="Consolas,monospace" font-size="28" font-weight="700" letter-spacing="8">'
        f'{escaped}</text></svg>'
    )
    image_data_uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return challenge, image_data_uri


async def verify_captcha(db: AsyncSession, captcha_id: str | None, captcha_code: str | None) -> bool:
    if not captcha_id or not captcha_code:
        return False
    challenge = await db.get(LoginChallenge, captcha_id)
    if challenge is None or challenge.used_at is not None or challenge.expires_at <= utcnow():
        return False
    challenge.used_at = utcnow()
    valid = hmac.compare_digest(
        challenge.answer_hash,
        hash_captcha(captcha_code.strip(), challenge.answer_salt),
    )
    await db.commit()
    return valid


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
    captcha_id: str | None,
    captcha_code: str | None,
) -> tuple[User, str, AuthSession]:
    user = await db.scalar(select(User).where(User.username_key == username_key(username)))
    captcha_required = bool(
        user is not None
        and user.failed_login_attempts >= settings.LOGIN_CAPTCHA_AFTER_FAILURES
    )

    if captcha_required and not await verify_captcha(db, captcha_id, captcha_code):
        raise AppException(
            "请输入正确的验证码",
            code=40102,
            data={"captcha_required": True, "refresh_captcha": True},
            status_code=401,
        )

    # 即使用户名不存在也执行同等成本的 scrypt，降低基于响应时间枚举账号的风险。
    password_ok = verify_password(
        password,
        user.password_hash if user is not None else DUMMY_PASSWORD_HASH,
    ) and user is not None
    if not password_ok:
        if user is not None:
            user.failed_login_attempts += 1
            await db.commit()
            captcha_required = user.failed_login_attempts >= settings.LOGIN_CAPTCHA_AFTER_FAILURES
        raise AppException(
            "用户名或密码错误",
            code=40101,
            data={"captcha_required": captcha_required, "refresh_captcha": captcha_required},
            status_code=401,
        )

    if not user.is_active:
        raise AppException("账号已停用，请联系管理员", code=40301, status_code=403)

    user.failed_login_attempts = 0
    user.last_login_at = utcnow()
    await db.commit()
    token, session = await create_session(db, user)
    return user, token, session


async def get_user_by_session_token(db: AsyncSession, token: str | None) -> User | None:
    if not token:
        return None
    row = (
        await db.execute(
            select(User, AuthSession)
            .join(AuthSession, AuthSession.user_id == User.id)
            .where(AuthSession.token_hash == hash_session_token(token))
        )
    ).first()
    if row is None:
        return None
    user, session = row
    if not user.is_active:
        await db.delete(session)
        await db.commit()
        return None
    if session.expires_at <= utcnow():
        await db.delete(session)
        await db.commit()
        return None
    return user


async def revoke_session(db: AsyncSession, token: str | None) -> None:
    if not token:
        return
    await db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_session_token(token)))
    await db.commit()
