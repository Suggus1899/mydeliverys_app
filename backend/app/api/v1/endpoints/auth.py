"""Autenticacion: OTP WhatsApp, login password, refresh, 2FA, sesiones."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession, client_ip
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException, create_success_response
from app.schemas.common import (
    ChangePasswordRequest,
    LoginRequest,
    OTPRequest,
    PhoneRequest,
    RecoveryCodeRequest,
    RefreshRequest,
    TOTPVerifyRequest,
)
from app.services import auth as auth_service

router = APIRouter()


def _web_session_response(data: dict, message: str) -> JSONResponse:
    session_token = str(data.pop("session_token"))
    csrf_token = str(data["csrf_token"])
    response = create_success_response(data, message)
    secure = settings.ENVIRONMENT not in ("development", "test")
    response.set_cookie(
        "mds_session",
        session_token,
        max_age=settings.WEB_SESSION_MAX_HOURS * 3600,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        "mds_csrf",
        csrf_token,
        max_age=settings.WEB_SESSION_MAX_HOURS * 3600,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
    )
    return response


@router.post("/request-otp")
async def request_otp(body: PhoneRequest, request: Request) -> JSONResponse:
    data = await auth_service.request_otp(body.phone, client_ip(request))
    return create_success_response(data, "Codigo enviado por WhatsApp.")


@router.post("/verify-otp")
async def verify_otp(
    body: OTPRequest,
    request: Request,
    db: DbSession,
) -> JSONResponse:
    data = await auth_service.verify_otp(
        db, body.phone, body.otp, request.headers.get("User-Agent"), client_ip(request)
    )
    return create_success_response(data, "Autenticacion exitosa.")


@router.post("/login")
async def login(body: LoginRequest, request: Request, db: DbSession) -> JSONResponse:
    data = await auth_service.login_password(
        db, body.phone, body.password, request.headers.get("User-Agent"), client_ip(request)
    )
    if data.get("requires_2fa"):
        return create_success_response(data, "Se requiere verificacion 2FA.")
    return create_success_response(data, "Bienvenido.")


@router.post("/web/login")
async def web_login(body: LoginRequest, request: Request, db: DbSession) -> JSONResponse:
    data = await auth_service.login_password(
        db,
        body.phone,
        body.password,
        request.headers.get("User-Agent"),
        client_ip(request),
        web=True,
    )
    if data.get("requires_2fa"):
        return create_success_response(data, "Se requiere verificacion 2FA.")
    return _web_session_response(data, "Bienvenido.")


@router.post("/refresh")
async def refresh(body: RefreshRequest, request: Request, db: DbSession) -> JSONResponse:
    data = await auth_service.refresh_tokens(
        db, body.refresh_token, request.headers.get("User-Agent"), client_ip(request)
    )
    return create_success_response(data, "Tokens renovados.")


@router.post("/logout")
async def logout(
    user: CurrentUser,
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
    refresh_token: str | None = None,
) -> JSONResponse:
    # refresh via body/query o header X-Refresh-Token
    data = await auth_service.logout(db, refresh_token, user.id)
    return create_success_response(data)


@router.post("/logout-all")
async def logout_all(user: CurrentUser, db: DbSession) -> JSONResponse:
    data = await auth_service.logout_all(db, user.id, "LOGOUT")
    return create_success_response(data)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest, user: CurrentUser, db: DbSession
) -> JSONResponse:
    data = await auth_service.change_password(db, user, body.old_password, body.new_password)
    return create_success_response(data)


@router.post("/2fa/setup")
async def totp_setup(user: CurrentUser) -> JSONResponse:
    data = await auth_service.totp_setup(user)
    return create_success_response(data, "Escanea el QR y confirma con un codigo.")


@router.post("/2fa/confirm")
async def totp_confirm(body: TOTPVerifyRequest, user: CurrentUser, db: DbSession) -> JSONResponse:
    data = await auth_service.totp_confirm(db, user, body.code)
    return create_success_response(data)


@router.post("/2fa/verify")
async def totp_verify(
    body: TOTPVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    pending = request.headers.get("X-Pending-Token")
    if not pending:
        raise AppException("MISSING_PENDING_TOKEN", "Falta X-Pending-Token.", 400)

    data = await auth_service.totp_verify_login(
        db, pending, body.code, request.headers.get("User-Agent"), client_ip(request)
    )
    return create_success_response(data, "Autenticacion 2FA exitosa.")


@router.post("/web/2fa/verify")
async def web_totp_verify(
    body: TOTPVerifyRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> JSONResponse:
    pending = request.headers.get("X-Pending-Token")
    if not pending:
        raise AppException("MISSING_PENDING_TOKEN", "Falta X-Pending-Token.", 400)
    data = await auth_service.totp_verify_login(
        db,
        pending,
        body.code,
        request.headers.get("User-Agent"),
        client_ip(request),
        web=True,
    )
    return _web_session_response(data, "Autenticacion 2FA exitosa.")


@router.post("/2fa/recovery")
async def totp_recovery(
    body: RecoveryCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    pending = request.headers.get("X-Pending-Token")
    if not pending:
        raise AppException("MISSING_PENDING_TOKEN", "Falta X-Pending-Token.", 400)

    data = await auth_service.totp_verify_login(
        db, pending, body.code, request.headers.get("User-Agent"), client_ip(request)
    )
    return create_success_response(data, "Recuperacion exitosa.")


@router.post("/web/logout")
async def web_logout(request: Request, user: CurrentUser, db: DbSession) -> JSONResponse:
    session_token = request.cookies.get("mds_session")
    data = await auth_service.logout(db, session_token, user.id)
    response = create_success_response(data)
    response.delete_cookie("mds_session", path="/")
    response.delete_cookie("mds_csrf", path="/")
    return response
