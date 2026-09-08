"""Servicio de identidad: OTP, sesiones, login password, 2FA TOTP.

Implementa RF-AUTH-01..22 de docs/sdd/features/normalized/01_auth_and_sessions.md
"""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pyotp
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.security import (
    create_pending_2fa_token,
    create_token_pair,
    create_web_session_token,
    decode_token,
    decrypt_credential,
    encrypt_credential,
    generate_otp,
    hash_password,
    hash_recovery_code,
    normalize_phone,
    otp_attempts_key,
    otp_blocked_key,
    otp_ip_blocked_key,
    otp_key,
    verify_password,
)
from app.infrastructure.redis import get_redis
from app.models.user import RestaurantStaff, RoleEnum, User, UserSession

ACCESS_EXPIRES = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
REFRESH_EXPIRES = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
logger = logging.getLogger(__name__)


def _sha256(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def request_otp(phone_raw: str, ip: str) -> dict:
    try:
        phone = normalize_phone(phone_raw)
    except ValueError as err:
        raise AppException("INVALID_PHONE", "Numero de telefono invalido.", 422) from err
    redis = get_redis()
    # Bloqueo por telefono?
    if await redis.exists(otp_blocked_key(phone)):
        raise AppException(
            "OTP_PHONE_BLOCKED", "Telefono bloqueado 10 minutos por intentos fallidos.", 429
        )
    # Bloqueo por IP?
    if await redis.exists(otp_ip_blocked_key(ip)):
        raise AppException("OTP_IP_BLOCKED", "Demasiadas solicitudes desde esta IP.", 429)
    # Rate por IP: cuenta requests en ventana
    ip_count_key = f"otp_ip_count:{ip}"
    count = await redis.incr(ip_count_key)
    if count == 1:
        await redis.expire(ip_count_key, settings.OTP_IP_WINDOW_MINUTES * 60)
    if count > settings.OTP_IP_MAX_REQUESTS:
        await redis.setex(otp_ip_blocked_key(ip), settings.OTP_BLOCK_MINUTES * 60, "1")
        raise AppException("OTP_IP_BLOCKED", "Demasiadas solicitudes desde esta IP.", 429)

    code = generate_otp(6)
    # SET NX? Permitimos reenvio: sobrescribe y resetea TTL 180s
    await redis.setex(otp_key(phone), settings.OTP_TTL_SECONDS, code)
    await redis.delete(otp_attempts_key(phone))
    # Encola envio WhatsApp (dev: log)
    try:
        from app.tasks.notifications import send_whatsapp_otp

        send_whatsapp_otp.delay(phone, code)
    except Exception as exc:
        raise AppException(
            "OTP_DELIVERY_UNAVAILABLE",
            "No se pudo enviar el codigo por WhatsApp. Intenta nuevamente.",
            503,
        ) from exc
    return {"message": "OTP enviado", "expires_in_seconds": settings.OTP_TTL_SECONDS}


async def verify_otp(
    db: AsyncSession, phone_raw: str, code: str, user_agent: str | None, ip: str
) -> dict:
    try:
        phone = normalize_phone(phone_raw)
    except ValueError as err:
        raise AppException("INVALID_PHONE", "Numero de telefono invalido.", 422) from err
    redis = get_redis()
    if await redis.exists(otp_blocked_key(phone)):
        raise AppException("OTP_PHONE_BLOCKED", "Telefono bloqueado 10 minutos.", 429)
    stored = await redis.get(otp_key(phone))
    if stored is None:
        raise AppException("OTP_EXPIRED", "Codigo expirado o inexistente. Solicita uno nuevo.", 401)
    if stored != code:
        attempts = await redis.incr(otp_attempts_key(phone))
        if attempts == 1:
            await redis.expire(otp_attempts_key(phone), settings.OTP_BLOCK_MINUTES * 60)
        if attempts >= settings.OTP_MAX_ATTEMPTS:
            await redis.setex(otp_blocked_key(phone), settings.OTP_BLOCK_MINUTES * 60, "1")
            await redis.delete(otp_key(phone))
            raise AppException(
                "OTP_PHONE_BLOCKED", "3 intentos fallidos. Telefono bloqueado 10 minutos.", 429
            )
        raise AppException("OTP_INVALID", f"Codigo incorrecto. Intento {attempts}/3.", 401)
    # Consume atomico
    await redis.delete(otp_key(phone))
    await redis.delete(otp_attempts_key(phone))

    # Upsert CUSTOMER
    stmt = select(User).where(User.phone_number == phone)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        user = User(id=uuid4(), phone_number=phone, full_name="", role=RoleEnum.CUSTOMER)
        db.add(user)
        await db.flush()
    elif user.role != RoleEnum.CUSTOMER:
        raise AppException(
            "PARTNER_OTP_FORBIDDEN",
            "Las cuentas de socios ingresan con contrasena.",
            403,
        )
    if not user.is_active:
        raise AppException("USER_INACTIVE", "Cuenta bloqueada. Contacta soporte.", 403)

    pair = create_token_pair(str(user.id), user.role.value)
    await _store_session(db, user.id, pair.refresh_token, user_agent, ip)
    await db.commit()
    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "token_type": "bearer",
        "expires_in": pair.expires_in,
        "user": {"id": str(user.id), "role": user.role.value, "phone": user.phone_number},
        "is_new": not bool(user.full_name.strip()),
    }


async def _store_session(
    db: AsyncSession, user_id: UUID, refresh_token: str, user_agent: str | None, ip: str | None
) -> None:
    payload = decode_token(refresh_token)
    exp = datetime.fromtimestamp(payload.exp, tz=UTC)
    db.add(
        UserSession(
            id=uuid4(),
            user_id=user_id,
            refresh_token_hash=_sha256(refresh_token),
            user_agent=user_agent,
            ip_address=ip,
            expires_at=exp,
        )
    )


async def login_password(
    db: AsyncSession,
    phone_raw: str,
    password: str,
    user_agent: str | None,
    ip: str | None,
    *,
    web: bool = False,
) -> dict:
    """Login DRIVER / RESTAURANT_ADMIN / SUPER_ADMIN. Super admin requiere 2FA aparte."""
    if "@" in phone_raw:
        stmt = select(User).where(User.email == phone_raw.strip().lower())
    else:
        try:
            phone = normalize_phone(phone_raw)
        except ValueError as err:
            raise AppException("INVALID_PHONE", "Numero invalido.", 422) from err
        stmt = select(User).where(User.phone_number == phone)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None or user.password_hash is None:
        raise AppException("INVALID_CREDENTIALS", "Credenciales invalidas.", 401)
    if not user.is_active:
        raise AppException("USER_INACTIVE", "Cuenta bloqueada.", 403)
    if user.role == RoleEnum.CUSTOMER:
        raise AppException("USE_OTP_LOGIN", "Los clientes ingresan con WhatsApp OTP.", 400)
    if not verify_password(password, user.password_hash):
        raise AppException("INVALID_CREDENTIALS", "Credenciales invalidas.", 401)
    if user.role == RoleEnum.SUPER_ADMIN:
        return {
            "requires_2fa": True,
            "pending_token": create_pending_2fa_token(str(user.id), user.role.value),
        }
    if web:
        token = create_web_session_token(str(user.id), user.role.value)
        await _store_session(db, user.id, token, user_agent, ip)
        restaurant_id = await db.scalar(
            select(RestaurantStaff.restaurant_id).where(
                RestaurantStaff.user_id == user.id, RestaurantStaff.is_active.is_(True)
            )
        )
        await db.commit()
        return {
            "session_token": token,
            "csrf_token": secrets.token_urlsafe(32),
            "role": user.role.value,
            "restaurant_id": str(restaurant_id) if restaurant_id else None,
        }
    pair = create_token_pair(str(user.id), user.role.value)
    await _store_session(db, user.id, pair.refresh_token, user_agent, ip)
    await db.commit()
    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "token_type": "bearer",
        "expires_in": pair.expires_in,
    }


async def refresh_tokens(
    db: AsyncSession, refresh_token: str, user_agent: str | None, ip: str | None
) -> dict:
    try:
        payload = decode_token(refresh_token)
    except ValueError as err:
        raise AppException("SESSION_EXPIRED", "Refresh expirado.", 401) from err
    if payload.type != "refresh":
        raise AppException("INVALID_TOKEN_TYPE", "Se requiere refresh token.", 401)
    # SELECT FOR UPDATE para evitar doble uso concurrente
    stmt = (
        select(UserSession)
        .where(
            UserSession.user_id == UUID(payload.sub),
            UserSession.refresh_token_hash == _sha256(refresh_token),
            UserSession.revoked_at.is_(None),
        )
        .with_for_update()
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if session is None or session.expires_at < datetime.now(UTC):
        raise AppException("SESSION_EXPIRED", "Sesion expirada. Ingresa de nuevo.", 401)
    # Rotacion: revoca anterior
    session.revoked_at = datetime.now(UTC)
    session.revoked_reason = "ROTATED"
    stmt_u = select(User).where(User.id == UUID(payload.sub))
    user = (await db.execute(stmt_u)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppException("USER_INACTIVE", "Usuario inactivo.", 401)
    pair = create_token_pair(str(user.id), user.role.value)
    await _store_session(db, user.id, pair.refresh_token, user_agent, ip)
    await db.commit()
    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "token_type": "bearer",
        "expires_in": pair.expires_in,
    }


async def logout(db: AsyncSession, refresh_token: str | None, user_id: UUID) -> dict:
    if refresh_token:
        await db.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.refresh_token_hash == _sha256(refresh_token),
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC), revoked_reason="LOGOUT")
        )
        await db.commit()
    return {"message": "Sesion cerrada."}


async def logout_all(db: AsyncSession, user_id: UUID, reason: str = "ADMIN_REVOKE") -> dict:
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC), revoked_reason=reason)
    )
    await db.commit()
    return {"message": "Todas las sesiones revocadas."}


async def change_password(db: AsyncSession, user: User, old: str, new: str) -> dict:
    if user.password_hash is None or not verify_password(old, user.password_hash):
        raise AppException("INVALID_CREDENTIALS", "Contrasena actual incorrecta.", 401)
    user.password_hash = hash_password(new)
    await logout_all(db, user.id, "PASSWORD_CHANGE")
    await db.commit()
    return {"message": "Contrasena cambiada. Ingresa de nuevo."}


# ---- 2FA TOTP (SUPER_ADMIN) ----
# Guardamos secreto en Redis temporal hasta confirmar; luego en... V1: campo password_hash no sirve.
# Creamos tabla implicita via Redis persistente? Simplificacion V1: secreto en Redis `totp:{user_id}` + recovery en Redis set.
# En produccion migrar a columna users.totp_secret. Documentado como deuda controlada.

TOTP_ISSUER = "MyDeliveryS"


async def totp_setup(user: User) -> dict:
    if user.role != RoleEnum.SUPER_ADMIN:
        raise AppException("FORBIDDEN_ROLE", "Solo Super Admin usa 2FA.", 403)
    secret = pyotp.random_base32()
    redis = get_redis()
    await redis.setex(f"totp:pending:{user.id}", 600, secret)
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email or user.phone_number, issuer_name=TOTP_ISSUER
    )
    codes = [secrets.token_hex(5).upper() for _ in range(8)]
    await redis.setex(f"totp:recovery_pending:{user.id}", 600, ",".join(codes))
    return {"secret": secret, "qr_code_url": uri, "recovery_codes": codes}


async def totp_confirm(db: AsyncSession, user: User, code: str) -> dict:
    redis = get_redis()
    secret = await redis.get(f"totp:pending:{user.id}")
    rec = await redis.get(f"totp:recovery_pending:{user.id}")
    if not secret:
        raise AppException("TOTP_NO_PENDING", "No hay configuracion pendiente.", 400)
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        raise AppException("TOTP_INVALID", "Codigo 2FA invalido.", 401)
    user.totp_secret_encrypted = encrypt_credential(secret)
    await redis.delete(f"totp:pending:{user.id}")
    if rec:
        user.totp_recovery_hashes = [hash_recovery_code(item) for item in rec.split(",")]
        await redis.delete(f"totp:recovery_pending:{user.id}")
    user.totp_enabled_at = datetime.now(UTC)
    await db.commit()
    return {"message": "2FA activado."}


async def totp_verify_login(
    db: AsyncSession,
    pending_token: str,
    code: str,
    user_agent: str | None,
    ip: str | None,
    *,
    web: bool = False,
) -> dict:
    try:
        pending = decode_token(pending_token)
    except ValueError as err:
        raise AppException("PENDING_2FA_EXPIRED", "El acceso temporal expiro.", 401) from err
    if pending.type != "pending_2fa" or pending.role != RoleEnum.SUPER_ADMIN.value:
        raise AppException("INVALID_PENDING_2FA", "Acceso temporal invalido.", 401)
    stmt = select(User).where(User.id == UUID(pending.sub), User.role == RoleEnum.SUPER_ADMIN)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppException("USER_INACTIVE", "Usuario invalido.", 401)
    # Intento recovery?
    if len(code) > 8:
        code_hash = hash_recovery_code(code)
        hashes = list(user.totp_recovery_hashes or [])
        if code_hash not in hashes:
            raise AppException("TOTP_INVALID", "Codigo de recuperacion invalido.", 401)
        hashes.remove(code_hash)
        user.totp_recovery_hashes = hashes
    else:
        redis = get_redis()
        if not user.totp_secret_encrypted:
            raise AppException("TOTP_NOT_CONFIGURED", "2FA no configurado.", 409)
        try:
            secret = decrypt_credential(user.totp_secret_encrypted)
        except ValueError as err:
            raise AppException("TOTP_CONFIGURATION_ERROR", "No se pudo validar 2FA.", 500) from err
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            # conteo fallos 5/15min
            k = f"totp_fail:{user.id}"
            n = await redis.incr(k)
            if n == 1:
                await redis.expire(k, 900)
            if n >= 5:
                raise AppException("TOTP_LOCKED", "Cuenta bloqueada 30 min por 2FA.", 429)
            raise AppException("TOTP_INVALID", "Codigo 2FA invalido.", 401)
        await redis.delete(f"totp_fail:{user.id}")
    if web:
        token = create_web_session_token(str(user.id), user.role.value)
        await _store_session(db, user.id, token, user_agent, ip)
        await db.commit()
        return {
            "session_token": token,
            "csrf_token": secrets.token_urlsafe(32),
            "role": user.role.value,
            "restaurant_id": None,
        }
    pair = create_token_pair(str(user.id), user.role.value)
    await _store_session(db, user.id, pair.refresh_token, user_agent, ip)
    await db.commit()
    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "token_type": "bearer",
        "expires_in": pair.expires_in,
    }


async def create_restaurant_staff(
    db: AsyncSession, restaurant_id: UUID, phone_raw: str, full_name: str, temp_password: str
) -> User:
    phone = normalize_phone(phone_raw)
    stmt = select(User).where(User.phone_number == phone)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise AppException("PHONE_ALREADY_REGISTERED", "Telefono ya registrado.", 409)
    user = User(
        id=uuid4(),
        phone_number=phone,
        full_name=full_name,
        role=RoleEnum.RESTAURANT_ADMIN,
        password_hash=hash_password(temp_password),
    )
    db.add(user)
    await db.flush()
    db.add(RestaurantStaff(id=uuid4(), user_id=user.id, restaurant_id=restaurant_id))
    await db.commit()
    try:
        from app.tasks.notifications import send_whatsapp_otp

        send_whatsapp_otp.delay(phone, f"Tu acceso temporal: {temp_password}")
    except Exception:
        logger.exception("No se pudo notificar el acceso temporal al operador")
    return user


async def create_driver(
    db: AsyncSession, phone_raw: str, full_name: str, temp_password: str
) -> User:
    phone = normalize_phone(phone_raw)
    stmt = select(User).where(User.phone_number == phone)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise AppException("PHONE_ALREADY_REGISTERED", "Telefono ya registrado.", 409)
    user = User(
        id=uuid4(),
        phone_number=phone,
        full_name=full_name,
        role=RoleEnum.DRIVER,
        password_hash=hash_password(temp_password),
    )
    db.add(user)
    await db.commit()
    return user


async def cleanup_user_sessions(db: AsyncSession, user_id: UUID) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=90)
    await db.execute(
        delete(UserSession).where(
            UserSession.user_id == user_id,
            (UserSession.expires_at < cutoff) | (UserSession.revoked_at.is_not(None)),
        )
    )
