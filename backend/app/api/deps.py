"""Dependencias FastAPI: DB, usuario actual, roles, propiedad de recurso."""

import secrets
from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.security import decode_token
from app.models.order import Order
from app.models.user import RestaurantStaff, RoleEnum, User, UserSession

bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    bearer_token = creds.credentials if creds is not None else None
    cookie_token = request.cookies.get("mds_session")
    token = bearer_token or cookie_token
    if not token:
        raise AppException(
            "UNAUTHENTICATED", "Falta token de autenticacion.", status.HTTP_401_UNAUTHORIZED
        )
    try:
        payload = decode_token(token)
    except ValueError as err:
        raise AppException(
            "SESSION_EXPIRED", "Sesion expirada o invalida.", status.HTTP_401_UNAUTHORIZED
        ) from err
    if payload.type not in ("access", "web_session"):
        raise AppException(
            "INVALID_TOKEN_TYPE", "Se requiere access token.", status.HTTP_401_UNAUTHORIZED
        )
    if payload.type == "web_session":
        session_id = await db.scalar(
            select(UserSession.id).where(
                UserSession.user_id == UUID(payload.sub),
                UserSession.refresh_token_hash == sha256(token.encode()).hexdigest(),
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > datetime.now(UTC),
            )
        )
        if session_id is None:
            raise AppException("SESSION_EXPIRED", "Sesion web expirada.", 401)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            csrf_cookie = request.cookies.get("mds_csrf")
            csrf_header = request.headers.get("X-CSRF-Token")
            if (
                not csrf_cookie
                or not csrf_header
                or not secrets.compare_digest(csrf_cookie, csrf_header)
            ):
                raise AppException("CSRF_INVALID", "Token CSRF invalido.", 403)
    stmt = select(User).where(User.id == UUID(payload.sub))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppException(
            "USER_INACTIVE", "Usuario inactivo o inexistente.", status.HTTP_401_UNAUTHORIZED
        )
    # Adjunta IP para auditoria
    request.state.user_id = str(user.id)
    request.state.role = user.role.value
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed: RoleEnum):  # type: ignore[no-untyped-def]
    async def _check(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise AppException(
                "FORBIDDEN_ROLE",
                "No tienes permiso para esta operacion.",
                status.HTTP_403_FORBIDDEN,
            )
        return user

    return _check


async def require_restaurant_ownership(
    restaurant_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> User:
    """RESTAURANT_ADMIN solo su restaurante; SUPER_ADMIN pasa."""
    if user.role == RoleEnum.SUPER_ADMIN:
        return user
    if user.role != RoleEnum.RESTAURANT_ADMIN:
        raise AppException(
            "FORBIDDEN_ROLE", "Solo operador de restaurante.", status.HTTP_403_FORBIDDEN
        )
    from app.models.user import RestaurantStaff

    stmt = select(RestaurantStaff).where(
        RestaurantStaff.user_id == user.id,
        RestaurantStaff.restaurant_id == restaurant_id,
        RestaurantStaff.is_active.is_(True),
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise AppException(
            "RESOURCE_OWNERSHIP_MISMATCH",
            "No perteneces a este restaurante.",
            status.HTTP_403_FORBIDDEN,
        )
    return user


async def require_order_access(order: Order, user: User, db: AsyncSession) -> None:
    """Autoriza un pedido por rol, asignacion y pertenencia al comercio."""
    if user.role == RoleEnum.SUPER_ADMIN:
        return
    if user.role == RoleEnum.CUSTOMER and order.customer_id == user.id:
        return
    if user.role == RoleEnum.DRIVER and order.driver_id == user.id:
        return
    if user.role == RoleEnum.RESTAURANT_ADMIN:
        staff_id = await db.scalar(
            select(RestaurantStaff.id).where(
                RestaurantStaff.user_id == user.id,
                RestaurantStaff.restaurant_id == order.restaurant_id,
                RestaurantStaff.is_active.is_(True),
            )
        )
        if staff_id is not None:
            return
    raise AppException(
        "RESOURCE_OWNERSHIP_MISMATCH",
        "No tienes permiso para consultar este pedido.",
        status.HTTP_403_FORBIDDEN,
    )


def client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
