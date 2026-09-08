"""Conciliacion manual: reembolsos compensatorios y liquidaciones auditadas.

RF-PAY-18..22. Nunca borra ledger; crea movimientos compensatorios.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.domain.financial import money
from app.models.audit import AuditLog
from app.models.financial import (
    Refund,
    RefundReasonEnum,
    RefundStatusEnum,
    RefundTypeEnum,
    Settlement,
    SettlementEntityTypeEnum,
    SettlementStatusEnum,
)
from app.models.order import Order, OrderStatusEnum
from app.models.payment import Payment, PaymentStatusEnum, ReconciliationStatusEnum
from app.models.restaurant import Restaurant
from app.models.user import RoleEnum, User


async def _require_admin(user: User) -> None:
    if user.role != RoleEnum.SUPER_ADMIN:
        raise AppException("FORBIDDEN_ROLE", "Solo Super Admin.", 403)


async def create_refund(
    db: AsyncSession,
    admin: User,
    order_id: UUID,
    payment_id: UUID,
    rtype: str,
    reason: str,
    amount_usd: Decimal,
    proof_url: str | None,
) -> Refund:
    await _require_admin(admin)
    order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    payment = (
        await db.execute(select(Payment).where(Payment.id == payment_id).with_for_update())
    ).scalar_one_or_none()
    if order is None or payment is None or payment.order_id != order.id:
        raise AppException("REFUND_MISMATCH", "Pedido/pago no coinciden.", 422)
    if payment.status != PaymentStatusEnum.VERIFIED:
        raise AppException("REFUND_INVALID_STATUS", "Solo pagos VERIFIED.", 409)
    amount_usd = money(amount_usd)
    already_refunded = await db.scalar(
        select(func.coalesce(func.sum(Refund.amount_usd), 0)).where(
            Refund.payment_id == payment.id,
            Refund.status != RefundStatusEnum.REJECTED,
        )
    )
    refundable = payment.amount - Decimal(str(already_refunded or 0))
    if amount_usd <= 0 or amount_usd > refundable:
        raise AppException("REFUND_INVALID_AMOUNT", "Monto invalido.", 422)
    amount_ves = money(amount_usd * order.exchange_rate)
    refund = Refund(
        id=uuid4(),
        order_id=order.id,
        payment_id=payment.id,
        type=RefundTypeEnum(rtype),
        amount_usd=amount_usd,
        amount_ves=amount_ves,
        reason=RefundReasonEnum(reason),
        proof_image_url=proof_url,
        status=RefundStatusEnum.PENDING,
        requested_by=admin.id,
    )
    db.add(refund)
    db.add(
        AuditLog(
            id=uuid4(),
            admin_user_id=admin.id,
            action="CREATE_REFUND",
            entity_name="refunds",
            entity_id=refund.id,
            details={"order_id": str(order.id), "amount_usd": str(amount_usd), "reason": reason},
            ip_address=None,
        )
    )
    await db.commit()
    return refund


async def approve_refund(db: AsyncSession, admin: User, refund_id: UUID, approve: bool) -> Refund:
    await _require_admin(admin)
    refund = (await db.execute(select(Refund).where(Refund.id == refund_id))).scalar_one_or_none()
    if refund is None:
        raise AppException("REFUND_NOT_FOUND", "No encontrado.", 404)
    if refund.status != RefundStatusEnum.PENDING:
        raise AppException("REFUND_ALREADY_PROCESSED", "Ya procesado.", 409)
    if approve:
        refund.status = RefundStatusEnum.APPROVED
        refund.approved_by = admin.id
        # Marca pago como reembolsado para conciliacion (no lo borra)
        payment = (
            await db.execute(select(Payment).where(Payment.id == refund.payment_id))
        ).scalar_one_or_none()
        if payment is not None:
            payment.reconciliation_status = ReconciliationStatusEnum.REFUNDED
    else:
        refund.status = RefundStatusEnum.REJECTED
        refund.approved_by = admin.id
    db.add(
        AuditLog(
            id=uuid4(),
            admin_user_id=admin.id,
            action="APPROVE_REFUND" if approve else "REJECT_REFUND",
            entity_name="refunds",
            entity_id=refund.id,
            details={"status": refund.status.value},
            ip_address=None,
        )
    )
    await db.commit()
    return refund


async def create_settlement(
    db: AsyncSession,
    admin: User,
    entity_type: str,
    entity_id: UUID,
    start: date,
    end: date,
    currency: str = "USD",
) -> Settlement:
    await _require_admin(admin)
    if start > end:
        raise AppException("INVALID_PERIOD", "Periodo invalido.", 422)
    if currency not in ("USD", "VES"):
        raise AppException("INVALID_CURRENCY", "Moneda USD o VES.", 422)
    etype = SettlementEntityTypeEnum(entity_type)
    overlapping = await db.scalar(
        select(Settlement.id)
        .where(
            Settlement.entity_type == etype,
            Settlement.entity_id == entity_id,
            Settlement.currency == currency,
            Settlement.status != SettlementStatusEnum.CANCELLED,
            Settlement.period_start <= end,
            Settlement.period_end >= start,
        )
        .with_for_update()
    )
    if overlapping is not None:
        raise AppException(
            "SETTLEMENT_PERIOD_OVERLAP", "Ya existe una liquidacion para ese periodo.", 409
        )

    start_at = datetime(start.year, start.month, start.day, tzinfo=UTC)
    end_at = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(days=1)

    gross = Decimal("0")
    commission = Decimal("0")
    delivery_fees = Decimal("0")
    platform_fees = Decimal("0")
    if etype == SettlementEntityTypeEnum.RESTAURANT:
        restaurant = (
            await db.execute(select(Restaurant).where(Restaurant.id == entity_id))
        ).scalar_one_or_none()
        if restaurant is None:
            raise AppException("RESTAURANT_NOT_FOUND", "No encontrado.", 404)
        # Subtotal periodo de ese restaurante (ordenes DELIVERED)
        sub = await db.scalar(
            select(func.coalesce(func.sum(Order.subtotal_amount), 0)).where(
                Order.restaurant_id == entity_id,
                Order.status == OrderStatusEnum.DELIVERED,  # type: ignore[comparison-overlap]
                Order.created_at >= start_at,
                Order.created_at < end_at,
            )
        )
        sub = Decimal(str(sub or 0))
        gross = sub
        commission = money(sub * restaurant.commission_rate / 100)
    else:
        _fees = await db.scalar(
            select(func.coalesce(func.sum(Order.delivery_fee), 0)).where(
                Order.driver_id == entity_id,
                Order.status == OrderStatusEnum.DELIVERED,  # type: ignore[comparison-overlap]
                Order.created_at >= start_at,
                Order.created_at < end_at,
            )
        )
        delivery_fees = Decimal(str(_fees or 0))
        gross = delivery_fees
    # Ajustes: reembolsos APPROVED del periodo (restan)
    entity_filter = (
        Order.restaurant_id == entity_id
        if etype == SettlementEntityTypeEnum.RESTAURANT
        else Order.driver_id == entity_id
    )
    adj = await db.scalar(
        select(func.coalesce(func.sum(Refund.amount_usd), 0))
        .join(Order, Order.id == Refund.order_id)
        .where(
            Refund.status == RefundStatusEnum.APPROVED,
            entity_filter,
            Refund.created_at >= start_at,
            Refund.created_at < end_at,
        )
    )
    adjustments = -Decimal(str(adj or 0))
    net = money(gross - commission - platform_fees + adjustments)

    settlement = Settlement(
        id=uuid4(),
        entity_type=etype,
        entity_id=entity_id,
        period_start=start,
        period_end=end,
        currency=currency,
        gross_amount=money(gross),
        commission_amount=money(commission),
        delivery_fees_collected=money(delivery_fees),
        platform_fees_collected=money(platform_fees),
        adjustments=money(adjustments),
        net_amount=net,
        status=SettlementStatusEnum.DRAFT,
        created_by=admin.id,
    )
    db.add(settlement)
    db.add(
        AuditLog(
            id=uuid4(),
            admin_user_id=admin.id,
            action="CREATE_SETTLEMENT",
            entity_name="settlements",
            entity_id=settlement.id,
            details={"entity": entity_type, "period": [str(start), str(end)], "net": str(net)},
            ip_address=None,
        )
    )
    await db.commit()
    return settlement


async def confirm_settlement(
    db: AsyncSession, admin: User, settlement_id: UUID, status: str, proof_url: str | None
) -> Settlement:
    await _require_admin(admin)
    s = (
        await db.execute(select(Settlement).where(Settlement.id == settlement_id))
    ).scalar_one_or_none()
    if s is None:
        raise AppException("SETTLEMENT_NOT_FOUND", "No encontrada.", 404)
    if s.status != SettlementStatusEnum.DRAFT and status == "CONFIRMED":
        raise AppException("SETTLEMENT_INVALID_TRANSITION", "Solo DRAFT->CONFIRMED.", 409)
    if status == "CONFIRMED":
        if not proof_url:
            raise AppException(
                "SETTLEMENT_PROOF_REQUIRED", "Adjunta el comprobante de liquidacion.", 422
            )
        s.status = SettlementStatusEnum.CONFIRMED
        s.confirmed_by = admin.id
        s.confirmed_at = datetime.now(UTC)
        s.proof_image_url = proof_url
    elif status == "PAID":
        if s.status != SettlementStatusEnum.CONFIRMED:
            raise AppException("SETTLEMENT_INVALID_TRANSITION", "Solo CONFIRMED->PAID.", 409)
        s.status = SettlementStatusEnum.PAID
    elif status == "CANCELLED":
        s.status = SettlementStatusEnum.CANCELLED
    else:
        raise AppException("INVALID_STATUS", "Estado invalido.", 422)
    if s.net_amount < 0 and not s.notes:
        raise AppException(
            "SETTLEMENT_NEGATIVE_NOTE_REQUIRED",
            "Una liquidacion con neto negativo requiere una nota.",
            422,
        )
    db.add(
        AuditLog(
            id=uuid4(),
            admin_user_id=admin.id,
            action=f"SETTLEMENT_{status}",
            entity_name="settlements",
            entity_id=s.id,
            details={"status": status},
            ip_address=None,
        )
    )
    await db.commit()
    return s


async def flag_discrepancy(
    db: AsyncSession, admin: User, payment_id: UUID, reported_amount: Decimal
) -> Payment:
    """Marca diferencia entre monto esperado y reportado para conciliacion."""
    from app.domain.financial import discrepancy as calc_discrepancy

    await _require_admin(admin)
    payment = (
        await db.execute(select(Payment).where(Payment.id == payment_id))
    ).scalar_one_or_none()
    if payment is None:
        raise AppException("PAYMENT_NOT_FOUND", "Pago no encontrado.", 404)
    diff = calc_discrepancy(payment.amount, reported_amount)
    payment.discrepancy_amount = diff
    payment.reconciliation_status = (
        ReconciliationStatusEnum.MATCHED if diff == 0 else ReconciliationStatusEnum.DISCREPANCY
    )
    db.add(
        AuditLog(
            id=uuid4(),
            admin_user_id=admin.id,
            action="FLAG_DISCREPANCY",
            entity_name="payments",
            entity_id=payment.id,
            details={
                "expected": str(payment.amount),
                "reported": str(reported_amount),
                "diff": str(diff),
            },
            ip_address=None,
        )
    )
    await db.commit()
    return payment
