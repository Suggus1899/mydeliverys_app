import asyncio
from datetime import UTC, datetime, timedelta

from celery import shared_task
from sqlalchemy import delete
from sqlalchemy.engine import CursorResult

from app.core.database import get_db_context
from app.models.payment import IdempotencyKey
from app.models.user import UserSession


async def _cleanup_idempotency_async() -> dict:
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    async with get_db_context() as db:
        result = await db.execute(delete(IdempotencyKey).where(IdempotencyKey.expires_at < cutoff))
        await db.commit()
        return (
            {"deleted_count": result.rowcount or 0}
            if isinstance(result, CursorResult)
            else {"deleted_count": 0}
        )


@shared_task(name="app.tasks.maintenance.cleanup_idempotency_keys")
def cleanup_idempotency_keys() -> dict:
    return asyncio.run(_cleanup_idempotency_async())


async def _cleanup_sessions_async() -> dict:
    cutoff = datetime.now(UTC) - timedelta(days=90)
    async with get_db_context() as db:
        result = await db.execute(
            delete(UserSession).where(
                (UserSession.expires_at < cutoff) | (UserSession.revoked_at < cutoff)
            )
        )
        await db.commit()
        return (
            {"deleted_count": result.rowcount or 0}
            if isinstance(result, CursorResult)
            else {"deleted_count": 0}
        )


@shared_task(name="app.tasks.maintenance.cleanup_expired_sessions")
def cleanup_expired_sessions() -> dict:
    return asyncio.run(_cleanup_sessions_async())
