"""Pagos 50/50: reporte, verificacion admin, cobro driver, idempotencia persistente."""

import hashlib
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.domain.states import OrderStatus, transition
from app.models.order import Order, OrderReservation, OrderStatusEnum
from app.models.payment import (
    IdempotencyKey,
    Payment,
    PaymentMethodEnum,
    PaymentPhaseEnum,
    PaymentStatusEnum,
    ReconciliationStatusEnum,
)
from app.models.user import RoleEnum, User
from app.services.events import record_order_event

logger = logging.getLogger(__name__)


def _hash_body(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


async def _check_idempotency(db: AsyncSession, key: str, scope: str, body: dict) -> Payment | None:
    h = _hash_body(body)
    stmt = select(IdempotencyKey).where(IdempotencyKey.key == key, IdempotencyKey.scope == scope)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    if row.expires_at < datetime.now(UTC):
        await db.delete(row)
        return None
    if row.request_hash != h:
        raise AppException(
            "IDEMPOTENCY_KEY_REUSED_DIFFERENT_PAYLOAD", "Clave reutilizada con otro contenido.", 409
        )
    # Replay: busca pago creado con esa clave
    p = (
        await db.execute(
            select(Payment).where(
                Payment.idempotency_key == key, Payment.idempotency_scope == scope
            )
        )
    ).scalar_one_or_none()
    return p


async def _store_idempotency(
    db: AsyncSession, key: str, scope: str, body: dict, payment: Payment, status_code: int = 201
) -> None:
    now = datetime.now(UTC)
    db.add(
        IdempotencyKey(
            key=key,
            scope=scope,
            request_hash=_hash_body(body),
            response_status=status_code,
            response_body={"payment_id": str(payment.id), "status": payment.status.value},
            created_at=now,
            expires_at=now + timedelta_hours(24),
        )
    )


def timedelta_hours(h: int):  # type: ignore[no-untyped-def]
    from datetime import timedelta

    return timedelta(hours=h)


async def report_first_payment(
    db: AsyncSession,
    order: Order,
    customer: User,
    method: str,
    reference: str | None,
    bank: str | None,
    proof_url: str | None,
    idem_key: str,
) -> Payment:
    if order.customer_id != customer.id:
        raise AppException("ORDER_NOT_OWNED", "No es tu pedido.", 403)
    if order.status != OrderStatusEnum.PAYMENT_1_PENDING:
        raise AppException(
            "INVALID_ORDER_STATUS", f"Estado {order.status.value} no admite reporte.", 409
        )
    # Reserva vigente?
    res = (
        await db.execute(select(OrderReservation).where(OrderReservation.order_id == order.id))
    ).scalar_one_or_none()
    if res is None or res.status != "ACTIVE" or res.expires_at < datetime.now(UTC):
        raise AppException("ORDER_EXPIRED", "Reserva expirada. Crea nueva cotizacion.", 409)
    body = {
        "order": str(order.id),
        "phase": "FIRST_HALF",
        "method": method,
        "ref": reference,
        "bank": bank,
    }
    existing = await _check_idempotency(db, idem_key, "customer:payment_report", body)
    if existing is not None:
        return existing
    if method not in (
        PaymentMethodEnum.PAGO_MOVIL.value,
        PaymentMethodEnum.BANK_TRANSFER.value,
    ):
        raise AppException("INVALID_METHOD", "Metodo digital no permitido.", 422)
    if not reference or not bank:
        raise AppException("MISSING_REFERENCE", "Referencia y banco requeridos.", 422)
    payment = Payment(
        id=uuid4(),
        order_id=order.id,
        phase=PaymentPhaseEnum.FIRST_HALF,
        method=PaymentMethodEnum(method),
        amount=order.first_half_amount,
        ves_amount=order.first_half_ves_amount,
        exchange_rate_used=order.exchange_rate,
        status=PaymentStatusEnum.PENDING,
        reference_number=reference,
        origin_bank=bank,
        proof_image_url=proof_url,
        idempotency_key=idem_key,
        idempotency_scope="customer:payment_report",
    )
    db.add(payment)
    transition(OrderStatus(order.status.value), OrderStatus.PAYMENT_1_VERIFYING)
    order.status = OrderStatusEnum.PAYMENT_1_VERIFYING
    res.status = "UNDER_REVIEW"
    record_order_event(db, order, "FIRST_PAYMENT_REPORTED")
    await _store_idempotency(db, idem_key, "customer:payment_report", body, payment)
    await db.commit()
    try:
        from app.tasks.notifications import notify_admin_payment_pending

        notify_admin_payment_pending.delay(str(payment.id), "FIRST_HALF")
    except Exception:
        logger.exception("No se pudo encolar la notificacion del primer pago")
    return payment


async def verify_payment(db: AsyncSession, payment: Payment, admin: User) -> Order:
    if admin.role != RoleEnum.SUPER_ADMIN:
        raise AppException("FORBIDDEN_ROLE", "Solo Super Admin verifica.", 403)
    if payment.status != PaymentStatusEnum.PENDING:
        raise AppException("PAYMENT_ALREADY_VERIFIED", "Pago ya procesado.", 409)
    order = (
        await db.execute(select(Order).where(Order.id == payment.order_id))
    ).scalar_one_or_none()
    if order is None:
        raise AppException("ORDER_NOT_FOUND", "Pedido no encontrado.", 404)
    payment.status = PaymentStatusEnum.VERIFIED
    payment.verified_by = admin.id
    payment.verified_at = datetime.now(UTC)
    payment.reconciliation_status = ReconciliationStatusEnum.MATCHED
    if payment.phase == PaymentPhaseEnum.FIRST_HALF:
        transition(OrderStatus(order.status.value), OrderStatus.PREPARING, first_verified=True)
        order.status = OrderStatusEnum.PREPARING
        record_order_event(db, order, "FIRST_PAYMENT_VERIFIED")
        res = (
            await db.execute(select(OrderReservation).where(OrderReservation.order_id == order.id))
        ).scalar_one_or_none()
        if res is not None and res.status in ("ACTIVE", "UNDER_REVIEW"):
            res.status = "CONSUMED"
        try:
            from app.tasks.notifications import notify_restaurant_new_order

            notify_restaurant_new_order.delay(str(order.restaurant_id), order.order_number)
        except Exception:
            logger.exception("No se pudo encolar la notificacion al restaurante")
    else:
        if order.status != OrderStatusEnum.PAYMENT_2_VERIFYING:
            raise AppException(
                "INVALID_ORDER_STATUS", "El segundo pago no esta en verificacion.", 409
            )
        record_order_event(db, order, "SECOND_PAYMENT_VERIFIED")
        # La verificacion habilita el cierre, pero la entrega fisica sigue siendo
        # una accion explicita del conductor.
    # Auditoria
    from app.models.audit import AuditLog

    db.add(
        AuditLog(
            id=uuid4(),
            admin_user_id=admin.id,
            action="VERIFY_PAYMENT",
            entity_name="payments",
            entity_id=payment.id,
            details={
                "payment_id": str(payment.id),
                "phase": payment.phase.value,
                "order_id": str(order.id),
            },
            ip_address=None,
        )
    )
    await db.commit()
    return order


async def reject_payment(db: AsyncSession, payment: Payment, admin: User, reason: str) -> Order:
    if admin.role != RoleEnum.SUPER_ADMIN:
        raise AppException("FORBIDDEN_ROLE", "Solo Super Admin rechaza.", 403)
    if payment.status != PaymentStatusEnum.PENDING:
        raise AppException("PAYMENT_ALREADY_VERIFIED", "Pago ya procesado.", 409)
    order = (
        await db.execute(select(Order).where(Order.id == payment.order_id))
    ).scalar_one_or_none()
    if order is None:
        raise AppException("ORDER_NOT_FOUND", "No encontrado.", 404)
    payment.status = PaymentStatusEnum.REJECTED
    payment.verified_by = admin.id
    payment.verified_at = datetime.now(UTC)
    if payment.phase == PaymentPhaseEnum.FIRST_HALF:
        transition(OrderStatus(order.status.value), OrderStatus.PAYMENT_1_PENDING)
        order.status = OrderStatusEnum.PAYMENT_1_PENDING
        reservation = await db.scalar(
            select(OrderReservation).where(OrderReservation.order_id == order.id)
        )
        if reservation is not None:
            reservation.status = "ACTIVE"
            if reservation.expires_at < datetime.now(UTC):
                from app.services.orders import cancel_draft

                await cancel_draft(db, order, "Reserva expirada durante la revision del pago")
    else:
        transition(OrderStatus(order.status.value), OrderStatus.ARRIVED_AT_CUSTOMER)
        order.status = OrderStatusEnum.ARRIVED_AT_CUSTOMER
    record_order_event(db, order, "PAYMENT_REJECTED")
    from app.models.audit import AuditLog

    db.add(
        AuditLog(
            id=uuid4(),
            admin_user_id=admin.id,
            action="REJECT_PAYMENT",
            entity_name="payments",
            entity_id=payment.id,
            details={"reason": reason, "phase": payment.phase.value},
            ip_address=None,
        )
    )
    await db.commit()
    return order


async def driver_collect_cash(
    db: AsyncSession,
    order: Order,
    driver: User,
    amount_usd: Decimal,
    amount_ves: Decimal | None,
    idem_key: str,
) -> Payment:
    if order.driver_id != driver.id:
        raise AppException("NOT_ASSIGNED_DRIVER", "No eres el conductor asignado.", 403)
    if order.status != OrderStatusEnum.ARRIVED_AT_CUSTOMER:
        raise AppException("INVALID_ORDER_STATUS", "Orden no lista para cobro.", 409)
    body = {"order": str(order.id), "usd": str(amount_usd), "ves": str(amount_ves)}
    existing = await _check_idempotency(db, idem_key, "driver:payment_cash", body)
    if existing is not None:
        return existing
    if order.second_half_amount == Decimal("0"):
        method = PaymentMethodEnum.CASH_USD
    elif amount_ves and amount_ves > 0:
        # Valida contra VES congelado
        expected_ves = order.second_half_ves_amount
        if abs(amount_ves - expected_ves) > Decimal("0.01"):
            raise AppException("CASH_MISMATCH", f"Se esperaban VES {expected_ves}.", 422)
        method = PaymentMethodEnum.CASH_VES
    else:
        if abs(Decimal(amount_usd) - order.second_half_amount) > Decimal("0.01"):
            raise AppException(
                "CASH_MISMATCH", f"Se esperaban USD {order.second_half_amount}.", 422
            )
        method = PaymentMethodEnum.CASH_USD
    payment = Payment(
        id=uuid4(),
        order_id=order.id,
        phase=PaymentPhaseEnum.SECOND_HALF,
        method=method,
        amount=order.second_half_amount,
        ves_amount=order.second_half_ves_amount if method == PaymentMethodEnum.CASH_VES else None,
        exchange_rate_used=order.exchange_rate,
        status=PaymentStatusEnum.VERIFIED,
        verified_by=driver.id,
        verified_at=datetime.now(UTC),
        reconciliation_status=ReconciliationStatusEnum.MATCHED,
        idempotency_key=idem_key,
        idempotency_scope="driver:payment_cash",
    )
    db.add(payment)
    transition(OrderStatus(order.status.value), OrderStatus.DELIVERED, second_verified=True)
    order.status = OrderStatusEnum.DELIVERED
    record_order_event(db, order, "CASH_COLLECTED_AND_DELIVERED")
    await _store_idempotency(db, idem_key, "driver:payment_cash", body, payment, 200)
    await db.commit()
    return payment


async def driver_complete_delivery(db: AsyncSession, order: Order, driver: User) -> Order:
    """Confirma la entrega fisica tras validar la segunda obligacion."""
    if order.driver_id != driver.id:
        raise AppException("NOT_ASSIGNED_DRIVER", "No eres el conductor asignado.", 403)
    if order.status == OrderStatusEnum.DELIVERED:
        return order
    second_verified = order.second_half_amount == Decimal("0")
    if not second_verified:
        second_verified = bool(
            await db.scalar(
                select(Payment.id).where(
                    Payment.order_id == order.id,
                    Payment.phase == PaymentPhaseEnum.SECOND_HALF,
                    Payment.status == PaymentStatusEnum.VERIFIED,
                )
            )
        )
    if order.status not in (
        OrderStatusEnum.ARRIVED_AT_CUSTOMER,
        OrderStatusEnum.PAYMENT_2_VERIFYING,
    ):
        raise AppException("INVALID_ORDER_STATUS", "El pedido no esta listo para entregar.", 409)
    transition(
        OrderStatus(order.status.value),
        OrderStatus.DELIVERED,
        second_verified=second_verified,
    )
    order.status = OrderStatusEnum.DELIVERED
    record_order_event(db, order, "DELIVERY_COMPLETED")
    await db.commit()
    return order


async def driver_report_digital(
    db: AsyncSession,
    order: Order,
    driver: User,
    method: str,
    reference: str,
    bank: str,
    proof: str | None,
    idem_key: str,
) -> Payment:
    if order.driver_id != driver.id:
        raise AppException("NOT_ASSIGNED_DRIVER", "No asignado.", 403)
    if order.status != OrderStatusEnum.ARRIVED_AT_CUSTOMER:
        raise AppException("INVALID_ORDER_STATUS", "Debe estar en destino.", 409)
    if method not in (
        PaymentMethodEnum.PAGO_MOVIL.value,
        PaymentMethodEnum.BANK_TRANSFER.value,
    ):
        raise AppException("INVALID_METHOD", "Metodo digital no permitido.", 422)
    body = {"order": str(order.id), "method": method, "ref": reference, "bank": bank}
    existing = await _check_idempotency(db, idem_key, "driver:payment_digital", body)
    if existing is not None:
        return existing
    payment = Payment(
        id=uuid4(),
        order_id=order.id,
        phase=PaymentPhaseEnum.SECOND_HALF,
        method=PaymentMethodEnum(method),
        amount=order.second_half_amount,
        ves_amount=order.second_half_ves_amount,
        exchange_rate_used=order.exchange_rate,
        status=PaymentStatusEnum.PENDING,
        reference_number=reference,
        origin_bank=bank,
        proof_image_url=proof,
        idempotency_key=idem_key,
        idempotency_scope="driver:payment_digital",
    )
    db.add(payment)
    transition(OrderStatus(order.status.value), OrderStatus.PAYMENT_2_VERIFYING)
    order.status = OrderStatusEnum.PAYMENT_2_VERIFYING
    record_order_event(db, order, "SECOND_PAYMENT_REPORTED")
    await _store_idempotency(db, idem_key, "driver:payment_digital", body, payment)
    await db.commit()
    return payment
