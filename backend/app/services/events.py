from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import OrderEvent
from app.models.order import Order


def record_order_event(db: AsyncSession, order: Order, event_type: str) -> None:
    db.add(
        OrderEvent(
            id=uuid4(),
            order_id=order.id,
            event_type=event_type,
            payload={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "status": order.status.value,
                "restaurant_id": str(order.restaurant_id),
                "driver_id": str(order.driver_id) if order.driver_id else None,
            },
        )
    )
