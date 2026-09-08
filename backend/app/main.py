import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.exceptions import register_exception_handlers
from app.core.middleware import IdempotencyMiddleware, RateLimitMiddleware
from app.infrastructure.redis import close_redis, init_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    # Startup (tolerante: no tumbar import si DB/Redis no disponibles en dev/test)
    try:
        import app.models  # noqa: F401  # registra metadata para init_db

        await init_db()
    except Exception as exc:
        logger.warning("No se pudo inicializar PostgreSQL: %s", exc)
    try:
        await init_redis()
    except Exception as exc:
        logger.warning("No se pudo inicializar Redis: %s", exc)
    yield
    # Shutdown
    try:
        await close_redis()
    except Exception:
        logger.exception("Fallo al cerrar Redis")
    try:
        await close_db()
    except Exception:
        logger.exception("Fallo al cerrar PostgreSQL")


def create_app() -> FastAPI:
    app = FastAPI(
        title="MyDeliveryS API",
        description="API para plataforma de delivery San Juan de los Morros",
        version="0.1.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
        ],
    )

    # Rate limiting (must be before idempotency to protect DB)
    app.add_middleware(RateLimitMiddleware)

    # Idempotency
    app.add_middleware(IdempotencyMiddleware)

    # Exception handlers
    register_exception_handlers(app)

    # Health checks
    @app.get("/health", tags=["Health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.ENVIRONMENT}

    @app.get("/healthz", tags=["Health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["Health"])
    async def ready() -> dict[str, Any]:
        # Check DB and Redis connectivity
        from app.core.database import engine
        from app.infrastructure.redis import get_redis

        db_ok = False
        redis_ok = False

        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception as exc:
            logger.warning("Readiness PostgreSQL fallo: %s", exc)

        try:
            await get_redis().ping()
            redis_ok = True
        except Exception as exc:
            logger.warning("Readiness Redis fallo: %s", exc)

        if db_ok and redis_ok:
            return {"status": "ready", "database": "ok", "redis": "ok"}
        return {
            "status": "not ready",
            "database": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
        }

    # Import and include routers
    from app.api.v1.router import api_router

    app.include_router(api_router, prefix="/api/v1")

    # WebSocket endpoints
    from app.api.v1.endpoints.websocket import router as ws_router

    app.include_router(ws_router)

    return app


app = create_app()
