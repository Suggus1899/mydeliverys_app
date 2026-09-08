"""Idempotencia persistente (PostgreSQL) + Redis (rápido).

Doble capa según spec 03_checkout_payments_ledger RF-PAY-05:
- Redis SET NX para procesamiento en vuelo.
- Tabla idempotency_keys para persistencia 24h.
Misma clave + mismo hash -> replay. Distinto hash -> conflicto.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import delete, select

from app.core.database import get_db_context
from app.models.payment import IdempotencyKey


class IdempotencyResult(BaseModel):
    status_code: int
    response_body: dict[str, Any]

    def to_cache_json(self) -> str:  # helper para middleware
        import json

        return json.dumps({"status_code": self.status_code, "body": self.response_body})


class IdempotencyConflictError(Exception):
    def __init__(self, message: str = "Clave reutilizada con contenido diferente.") -> None:
        super().__init__(message)
        self.code = "IDEMPOTENCY_KEY_REUSED_DIFFERENT_PAYLOAD"


async def check_idempotency(key: str, scope: str, request_hash: str) -> IdempotencyResult | None:
    """Devuelve resultado guardado si misma clave+scope y mismo hash.

    Lanza IdempotencyConflictError si misma clave+scope pero distinto hash.
    """
    async with get_db_context() as db:
        stmt = select(IdempotencyKey).where(
            IdempotencyKey.key == key,
            IdempotencyKey.scope == scope,
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        # Expirado -> tratar como ausente y limpiar
        if row.expires_at < datetime.now(UTC):
            await db.delete(row)
            await db.commit()
            return None
        if row.request_hash != request_hash:
            raise IdempotencyConflictError()
        return IdempotencyResult(
            status_code=row.response_status,
            response_body=row.response_body,
        )


async def store_idempotency(
    key: str,
    scope: str,
    request_hash: str,
    response_status: int,
    response_body: dict[str, Any],
    ttl_hours: int = 24,
) -> None:
    now = datetime.now(UTC)
    async with get_db_context() as db:
        row = IdempotencyKey(
            key=key,
            scope=scope,
            request_hash=request_hash,
            response_status=response_status,
            response_body=response_body,
            created_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
        )
        db.add(row)
        await db.commit()


async def cleanup_expired_idempotency() -> int:
    now = datetime.now(UTC)
    async with get_db_context() as db:
        stmt = delete(IdempotencyKey).where(IdempotencyKey.expires_at < now)
        result = await db.execute(stmt)
        await db.commit()
        return int(getattr(result, "rowcount", 0) or 0)


def new_key() -> str:
    return str(uuid4())
