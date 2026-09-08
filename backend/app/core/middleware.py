import logging
import time
from collections.abc import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.security import idempotency_key as make_idempotency_redis_key
from app.core.security import rate_limit_key
from app.infrastructure.redis import get_redis

logger = logging.getLogger(__name__)

# Rate limit configuration per endpoint group
RATE_LIMITS = {
    "auth_request_otp": {"limit": 3, "window_seconds": 600},  # 3 per 10 min
    "auth_verify_otp": {"limit": 5, "window_seconds": 180},  # 5 per 3 min
    "auth_login": {"limit": 10, "window_seconds": 300},  # 10 per 5 min
    "orders_draft": {"limit": 10, "window_seconds": 60},  # 10 per minute
    "payments_report": {"limit": 5, "window_seconds": 60},  # 5 per minute
    "restaurants_list": {"limit": 60, "window_seconds": 60},  # 60 per minute
    "menu_get": {"limit": 60, "window_seconds": 60},  # 60 per minute
    "ws_driver_track": {"limit": 1, "window_seconds": 3},  # 1 per 3 seconds
    "api_general": {"limit": 120, "window_seconds": 60},  # 120 per minute
}

# Path to rate limit group mapping
PATH_RATE_LIMIT_MAP = {
    "/api/v1/auth/request-otp": "auth_request_otp",
    "/api/v1/auth/verify-otp": "auth_verify_otp",
    "/api/v1/auth/login": "auth_login",
    "/api/v1/orders/draft": "orders_draft",
    "/api/v1/payments": "payments_report",  # will match /payments/{id}/report
    "/api/v1/restaurants": "restaurants_list",
    "/api/v1/restaurants/": "menu_get",  # /restaurants/{id}/menu
    "/ws/driver/track": "ws_driver_track",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiting using Redis sorted sets."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Skip rate limiting for health checks
        if request.url.path in ("/health", "/healthz", "/ready"):
            return await call_next(request)

        # Determine rate limit group
        rate_limit_group = self._get_rate_limit_group(request)
        if not rate_limit_group:
            return await call_next(request)

        # Get identifier (user_id if authenticated, else IP)
        identifier = await self._get_identifier(request)

        # Los controles protegidos fallan cerrados si Redis no esta disponible.
        limit_config = RATE_LIMITS[rate_limit_group]
        limit = limit_config["limit"]
        window = limit_config["window_seconds"]
        now = time.time()

        try:
            redis = get_redis()
            key = rate_limit_key(identifier, rate_limit_group)
            window_start = now - window
            # Use Redis sorted set for sliding window
            pipe = redis.pipeline()
            pipe.zadd(key, {str(now): now})
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.expire(key, window)
            results = await pipe.execute()
            current_count = results[2]
        except Exception:
            logger.exception("Redis no disponible para rate limiting")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "success": False,
                    "error_code": "RATE_LIMIT_UNAVAILABLE",
                    "message": "El control de solicitudes no esta disponible. Intenta nuevamente.",
                    "data": None,
                },
            )

        # Add rate limit headers
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(0, limit - current_count)),
            "X-RateLimit-Reset": str(int(now + window)),
        }

        if current_count > limit:
            # Rate limited
            retry_after = int(window - (now - window_start)) + 1
            headers["Retry-After"] = str(retry_after)

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers=headers,
                content={
                    "success": False,
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": "Has excedido el límite de solicitudes permitidas. Por favor espera antes de intentar nuevamente.",
                    "data": {
                        "retry_after_seconds": retry_after,
                        "limit": limit,
                        "window": f"{window}s",
                    },
                },
            )

        # Proceed with request
        response = await call_next(request)

        # Add headers to response
        for key, value in headers.items():
            response.headers[key] = value

        return response

    def _get_rate_limit_group(self, request: Request) -> str | None:
        """Determine rate limit group from request path."""
        path = request.url.path

        # Exact match
        if path in PATH_RATE_LIMIT_MAP:
            return PATH_RATE_LIMIT_MAP[path]

        # Pattern match for payments report
        if path.startswith("/api/v1/payments/") and "/report" in path:
            return "payments_report"

        # Pattern match for restaurant menu
        if path.startswith("/api/v1/restaurants/") and path.endswith("/menu"):
            return "menu_get"

        # Default for authenticated API routes
        if path.startswith("/api/v1/"):
            return "api_general"

        return None

    async def _get_identifier(self, request: Request) -> str:
        """Get rate limit identifier (user_id or IP)."""
        # Try to get user_id from JWT token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                from app.core.security import decode_token_unsafe

                payload = decode_token_unsafe(token)
                if payload and payload.sub:
                    return f"user:{payload.sub}"
            except Exception:
                logger.info("Token no utilizable para identificar la cuota")

        # Fallback to IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"


# Idempotency middleware for mutating endpoints
IDEMPOTENCY_PATHS = {
    "/api/v1/orders/draft": "customer:order_draft",
    "/api/v1/payments/": "customer:payment_report",  # /payments/{id}/report
    "/api/v1/driver/orders/": "driver:",  # /driver/orders/{id}/accept, /pickup, /arrived, /collect-cash, /confirm-digital
    "/api/v1/admin/payments/": "admin:payment_verify",  # /admin/payments/{id}/verify, /reject
    "/api/v1/admin/refunds": "admin:refund_create",
    "/api/v1/admin/orders/": "admin:order_reassign",  # /admin/orders/{id}/reassign
}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Idempotency middleware using Redis (fast) + PostgreSQL (persistent)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only apply to mutating methods with idempotency key
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)

        # Check if path requires idempotency
        scope = self._get_idempotency_scope(request)
        if not scope:
            return await call_next(request)

        # Get idempotency key from header
        idempotency_key_header = request.headers.get("X-Idempotency-Key")
        if not idempotency_key_header:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "error_code": "MISSING_IDEMPOTENCY_KEY",
                    "message": "Se requiere la cabecera X-Idempotency-Key para esta operación.",
                    "data": None,
                },
            )

        # Validate UUID format
        import uuid

        try:
            uuid.UUID(idempotency_key_header)
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "error_code": "INVALID_IDEMPOTENCY_KEY",
                    "message": "X-Idempotency-Key debe ser un UUID válido.",
                    "data": None,
                },
            )

        # Fast path: Redis lock to avoid duplicate in-flight processing.
        # Persistent idempotency (PostgreSQL) is enforced at service layer
        # via tabla idempotency_keys (ver app/services/idempotency.py).
        try:
            redis = get_redis()
            redis_key = make_idempotency_redis_key(scope, idempotency_key_header)
            acquired = await redis.set(
                f"{redis_key}:lock",
                "processing",
                nx=True,
                ex=120,
            )
            if not acquired:
                import asyncio
                import json

                await asyncio.sleep(0.1)
                cached = await redis.get(f"{redis_key}:result")
                if cached:
                    try:
                        return JSONResponse(
                            status_code=status.HTTP_200_OK,
                            content=json.loads(cached),
                        )
                    except Exception:
                        logger.exception("Respuesta idempotente en Redis invalida")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "success": False,
                        "error_code": "IDEMPOTENCY_PROCESSING",
                        "message": "Operacion en proceso con la misma clave. Intente nuevamente.",
                        "data": None,
                    },
                )
        except Exception:
            logger.exception("Redis no disponible para exclusion idempotente")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "success": False,
                    "error_code": "IDEMPOTENCY_UNAVAILABLE",
                    "message": "El control de duplicados no esta disponible. Intenta nuevamente.",
                    "data": None,
                },
            )

        try:
            response = await call_next(request)
            return response
        finally:
            if redis is not None and redis_key is not None:
                try:
                    await redis.delete(f"{redis_key}:lock")
                except Exception:
                    logger.exception("No se pudo liberar la exclusion idempotente")

    def _get_idempotency_scope(self, request: Request) -> str | None:
        """Determine idempotency scope from request path."""
        path = request.url.path

        for pattern, scope_prefix in IDEMPOTENCY_PATHS.items():
            if path.startswith(pattern):
                # For driver endpoints, include specific action
                if scope_prefix == "driver:":
                    if "/accept" in path:
                        return "driver:order_accept"
                    elif "/pickup" in path:
                        return "driver:order_pickup"
                    elif "/arrived" in path or "/arrive" in path:
                        return "driver:order_arrived"
                    elif "/collect-cash" in path:
                        return "driver:payment_cash"
                    elif "/confirm-digital" in path:
                        return "driver:payment_digital"
                    elif "/complete-delivery" in path:
                        return "driver:complete_delivery"
                elif scope_prefix == "admin:payment_verify":
                    if "/verify" in path:
                        return "admin:payment_verify"
                    elif "/reject" in path:
                        return "admin:payment_reject"
                elif scope_prefix == "admin:order_reassign":
                    return "admin:order_reassign"
                return scope_prefix

        return None
