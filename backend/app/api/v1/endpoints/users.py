"""Perfil y direcciones del usuario."""

from uuid import UUID, uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import AppException, create_success_response
from app.models.user import UserAddress
from app.schemas.common import UserAddressCreate, UserAddressUpdate, UserProfileUpdate

router = APIRouter()


def _wkt(lat: float, lon: float) -> str:
    return f"POINT({lon} {lat})"


@router.get("/me")
async def get_profile(user: CurrentUser) -> JSONResponse:
    return create_success_response(
        {
            "id": str(user.id),
            "phone_number": user.phone_number,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
        }
    )


@router.patch("/me")
async def update_profile(body: UserProfileUpdate, user: CurrentUser, db: DbSession) -> JSONResponse:
    if body.full_name is not None:
        if not body.full_name.strip():
            raise AppException("INVALID_NAME", "Nombre invalido.", 422)
        user.full_name = body.full_name.strip()
    if body.email is not None:
        user.email = body.email
    await db.commit()
    return create_success_response({"id": str(user.id), "full_name": user.full_name})


@router.get("/me/addresses")
async def list_addresses(user: CurrentUser, db: DbSession) -> JSONResponse:
    stmt = select(UserAddress).where(UserAddress.user_id == user.id).order_by(UserAddress.label)
    rows = list((await db.execute(stmt)).scalars().all())
    return create_success_response([{"id": str(a.id), "label": a.label} for a in rows])


@router.post("/me/addresses", status_code=201)
async def create_address(body: UserAddressCreate, user: CurrentUser, db: DbSession) -> JSONResponse:
    addr = UserAddress(
        id=uuid4(),
        user_id=user.id,
        label=body.label,
        address_line=body.address_line,
        reference_point=body.reference_point,
        location=_wkt(float(body.latitude), float(body.longitude)),
        is_default=body.is_default,
    )
    if body.is_default:
        await db.execute(
            update(UserAddress).where(UserAddress.user_id == user.id).values(is_default=False)
        )
    db.add(addr)
    await db.commit()
    return create_success_response({"id": str(addr.id)}, "Direccion creada.", 201)


@router.patch("/me/addresses/{address_id}")
async def update_address(
    address_id: UUID, body: UserAddressUpdate, user: CurrentUser, db: DbSession
) -> JSONResponse:
    stmt = select(UserAddress).where(UserAddress.id == address_id, UserAddress.user_id == user.id)
    addr = (await db.execute(stmt)).scalar_one_or_none()
    if addr is None:
        raise AppException("ADDRESS_NOT_OWNED", "Direccion no encontrada.", 403)
    if body.label is not None:
        addr.label = body.label
    if body.address_line is not None:
        addr.address_line = body.address_line
    if body.reference_point is not None:
        addr.reference_point = body.reference_point
    if body.latitude is not None and body.longitude is not None:
        addr.location = _wkt(float(body.latitude), float(body.longitude))
    if body.is_default is True:
        await db.execute(
            update(UserAddress).where(UserAddress.user_id == user.id).values(is_default=False)
        )
        addr.is_default = True
    elif body.is_default is False:
        addr.is_default = False
    await db.commit()
    return create_success_response({"id": str(addr.id)})


@router.delete("/me/addresses/{address_id}")
async def delete_address(address_id: UUID, user: CurrentUser, db: DbSession) -> JSONResponse:
    stmt = select(UserAddress).where(UserAddress.id == address_id, UserAddress.user_id == user.id)
    addr = (await db.execute(stmt)).scalar_one_or_none()
    if addr is None:
        raise AppException("ADDRESS_NOT_OWNED", "Direccion no encontrada.", 403)
    # No borrar si tiene pedidos activos
    from app.models.order import Order, OrderStatusEnum

    active = [
        s.value
        for s in OrderStatusEnum
        if s.value
        not in ("DELIVERED", "CANCELLED", "REJECTED", "CANCELLED_WITH_REFUND", "DELIVERY_FAILED")
    ]
    cnt = await db.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.delivery_address_id == addr.id, Order.status.in_(active))  # type: ignore[arg-type]
    )
    if cnt:
        raise AppException("ADDRESS_IN_USE", "Direccion en uso por pedido activo.", 409)
    await db.delete(addr)
    await db.commit()
    return create_success_response({"id": str(address_id)}, "Direccion eliminada.")
