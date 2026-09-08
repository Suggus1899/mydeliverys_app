"""Pricing: subtotal, fees por tramos, split 50/50, VES congelado."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.domain.financial import line_total, money, split_payment, to_ves
from app.models.financial import DeliveryFeeTier, ExchangeRate, PlatformFeeConfig
from app.models.restaurant import Modifier, Product


async def get_valid_rate(db: AsyncSession) -> ExchangeRate:
    stmt = (
        select(ExchangeRate)
        .where(ExchangeRate.is_valid.is_(True))
        .order_by(ExchangeRate.queried_at.desc())
        .limit(1)
    )
    rate = (await db.execute(stmt)).scalar_one_or_none()
    if rate is None:
        raise AppException("EXCHANGE_RATE_MISSING", "Sin tasa de cambio valida.", 422)
    hours = (datetime.now(UTC) - rate.queried_at).total_seconds() / 3600
    if hours > settings.EXCHANGE_RATE_STALE_HOURS:
        raise AppException(
            "EXCHANGE_RATE_STALE",
            "Tasa obsoleta. Nuevas cotizaciones bloqueadas.",
            422,
            {"hours_since_last": round(hours, 1)},
        )
    return rate


async def get_platform_fee(db: AsyncSession) -> Decimal:
    stmt = select(PlatformFeeConfig).where(PlatformFeeConfig.is_active.is_(True)).limit(1)
    cfg = (await db.execute(stmt)).scalar_one_or_none()
    if cfg is None:
        raise AppException("PLATFORM_FEE_MISSING", "Sin tarifa de plataforma configurada.", 422)
    return cfg.fee_usd


async def get_delivery_fee(db: AsyncSession, distance_m: Decimal) -> tuple[Decimal, UUID | None]:
    stmt = (
        select(DeliveryFeeTier)
        .where(DeliveryFeeTier.is_active.is_(True))
        .order_by(DeliveryFeeTier.min_distance_m)
    )
    tiers = list((await db.execute(stmt)).scalars().all())
    if not tiers:
        raise AppException("DELIVERY_FEE_MISSING", "Sin tramos de envio configurados.", 422)
    for t in tiers:
        if t.min_distance_m <= distance_m <= t.max_distance_m:
            return t.fee_usd, t.id
    raise AppException("DELIVERY_OUT_OF_COVERAGE", "Fuera de cobertura de entrega.", 422)


async def compute_line(
    db: AsyncSession, product: Product, quantity: int, modifier_ids: list[UUID]
) -> tuple[Decimal, list[Modifier]]:
    from app.services.catalog import validate_modifiers_for_draft

    mods = await validate_modifiers_for_draft(db, product, modifier_ids)
    extras = [m.extra_price for m in mods]
    total = line_total(product.base_price, extras, quantity)
    return total, mods


def build_payment_breakdown(total: Decimal, rate: Decimal) -> dict:
    parts = split_payment(total)
    first_ves = to_ves(parts.first_half, rate)
    second_ves = money(parts.total * rate) - first_ves
    # second por diferencia para conservar total VES exacto
    total_ves = money(parts.total * rate)
    second_ves = money(total_ves - first_ves)
    return {
        "total": str(parts.total),
        "first_half": str(parts.first_half),
        "second_half": str(parts.second_half),
        "first_half_ves": str(first_ves),
        "second_half_ves": str(second_ves),
        "exchange_rate": str(rate),
        "total_ves": str(total_ves),
    }
