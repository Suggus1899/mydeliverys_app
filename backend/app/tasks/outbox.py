import asyncio
import json
import logging
from datetime import UTC, datetime

from celery import shared_task
from sqlalchemy import select

from app.core.database import get_db_context
from app.infrastructure.redis import get_redis
from app.models.audit import OrderEvent

logger = logging.getLogger(__name__)


async def _publish_pending_async() -> dict[str, int]:
    published = 0
    async with get_db_context() as db:
        events = list(
            (
                await db.execute(
                    select(OrderEvent)
                    .where(OrderEvent.published_at.is_(None))
                    .order_by(OrderEvent.created_at)
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        redis = get_redis()
        for event in events:
            event.attempts += 1
            await redis.publish(
                f"order:{event.order_id}:events",
                json.dumps({"event_type": event.event_type, **event.payload}),
            )
            event.published_at = datetime.now(UTC)
            published += 1
    return {"published": published}


@shared_task(
    bind=True,
    max_retries=10,
    default_retry_delay=30,
    name="app.tasks.outbox.publish_order_events",
)
def publish_order_events(self) -> dict[str, int]:  # type: ignore[no-untyped-def]
    try:
        return asyncio.run(_publish_pending_async())
    except Exception as exc:
        logger.exception("Fallo al publicar el outbox")
        raise self.retry(exc=exc) from exc
