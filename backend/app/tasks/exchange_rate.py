import asyncio
import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import httpx
from celery import shared_task
from sqlalchemy import desc, select

from app.core.config import settings
from app.core.database import get_db_context
from app.infrastructure.redis import get_redis
from app.models.audit import AuditLog
from app.models.financial import ExchangeRate
from app.models.user import RoleEnum, User

logger = logging.getLogger(__name__)


def _parse_dolarapi(data: dict) -> tuple[Decimal, date, date]:
    for field in ("moneda", "fuente", "promedio", "fechaActualizacion"):
        if field not in data:
            raise ValueError(f"Campo faltante en DolarAPI: {field}")
    if data["moneda"] != "USD":
        raise ValueError(f"Moneda inesperada: {data['moneda']}")
    if data["fuente"] != "oficial":
        raise ValueError(f"Fuente inesperada: {data['fuente']}")
    rate_value = Decimal(str(data["promedio"]))
    if rate_value <= 0:
        raise ValueError(f"Tasa invalida: {rate_value}")
    provider_date = datetime.fromisoformat(
        str(data["fechaActualizacion"]).replace("Z", "+00:00")
    ).date()
    reported = provider_date
    effective = provider_date
    today = datetime.now(UTC).date()
    if reported > today or effective > today:
        raise ValueError("Fecha futura no permitida")
    return rate_value, reported, effective


async def _get_last_valid_async() -> ExchangeRate | None:
    async with get_db_context() as db:
        stmt = (
            select(ExchangeRate)
            .where(ExchangeRate.is_valid.is_(True))
            .order_by(desc(ExchangeRate.queried_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


async def _store_rate_async(
    rate: Decimal,
    reported: date,
    effective: date,
    valid: bool,
    details: dict,
) -> None:
    async with get_db_context() as db:
        # Busca existente mismo dia+fuente para actualizar (evita necesitar constraint)
        stmt = select(ExchangeRate).where(
            ExchangeRate.reported_date == reported,
            ExchangeRate.source == "dolarapi_oficial",
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        now = datetime.now(UTC)
        if existing is None:
            db.add(
                ExchangeRate(
                    id=uuid4(),
                    rate=rate,
                    source="dolarapi_oficial",
                    reported_date=reported,
                    effective_date=effective,
                    queried_at=now,
                    is_valid=valid,
                    validation_details=details,
                )
            )
        else:
            existing.rate = rate
            existing.effective_date = effective
            existing.queried_at = now
            existing.is_valid = valid
            existing.validation_details = details
        await db.commit()


def get_last_valid_rate_sync() -> ExchangeRate | None:
    return asyncio.run(_get_last_valid_async())


async def _invalidate_rate_cache_async() -> None:
    await get_redis().delete("cache:exchange_rate:latest")


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.tasks.exchange_rate.fetch_exchange_rate",
)
def fetch_exchange_rate(self) -> dict:  # type: ignore[no-untyped-def]
    """Consulta DolarAPI oficial cada 30 min y persiste tasa validada."""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(settings.DOLARAPI_URL)
            response.raise_for_status()
            data = response.json()
        rate_value, reported, effective = _parse_dolarapi(data)
        last = asyncio.run(_get_last_valid_async())
        if last is not None and (reported - last.reported_date).days < -1:
            raise ValueError("Regresion de fecha detectada")
        asyncio.run(
            _store_rate_async(rate_value, reported, effective, True, {"validation_passed": True})
        )
        try:
            asyncio.run(_invalidate_rate_cache_async())
        except Exception:
            logger.exception("No se pudo invalidar la cache de tasa")
        return {
            "status": "success",
            "rate": str(rate_value),
            "reported_date": str(reported),
            "effective_date": str(effective),
        }
    except Exception as exc:
        try:
            asyncio.run(
                _store_rate_async(
                    Decimal("0"),
                    date.today(),
                    date.today(),
                    False,
                    {"error": str(exc), "validation_passed": False},
                )
            )
        except Exception:
            logger.exception("No se pudo registrar la consulta invalida de DolarAPI")
        raise self.retry(exc=exc) from exc


@shared_task(name="app.tasks.exchange_rate.check_exchange_rate_health")
def check_exchange_rate_health() -> dict:
    last = asyncio.run(_get_last_valid_async())
    if last is None:
        asyncio.run(
            _alert_async("EXCHANGE_RATE_CRITICAL", "Sin tasa valida. Cotizaciones bloqueadas.")
        )
        return {"status": "critical"}
    hours = (datetime.now(UTC) - last.queried_at).total_seconds() / 3600
    if hours > settings.EXCHANGE_RATE_STALE_HOURS:
        asyncio.run(
            _alert_async(
                "EXCHANGE_RATE_STALE",
                f"Tasa obsoleta: {hours:.1f}h sin actualizar. Ultima: {last.rate}.",
            )
        )
        return {"status": "stale", "hours_since_last": hours}
    return {"status": "ok", "hours_since_last": hours}


async def _alert_async(alert_type: str, message: str) -> None:
    logger.error("Alerta %s: %s", alert_type, message)
    try:
        async with get_db_context() as db:
            admin_id = await db.scalar(
                select(User.id).where(User.role == RoleEnum.SUPER_ADMIN).limit(1)
            )
            if admin_id is None:
                logger.error("No existe Super Admin para persistir la alerta %s", alert_type)
                return
            db.add(
                AuditLog(
                    id=uuid4(),
                    admin_user_id=admin_id,
                    action=f"EXCHANGE_RATE_ALERT_{alert_type}",
                    entity_name="exchange_rates",
                    entity_id=uuid4(),
                    details={"alert_type": alert_type, "message": message},
                    ip_address="127.0.0.1",
                )
            )
            await db.commit()
    except Exception:
        logger.exception("No se pudo persistir la alerta %s", alert_type)


def alert_super_admin(alert_type: str, message: str) -> None:
    asyncio.run(_alert_async(alert_type, message))
