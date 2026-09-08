"""Restaurantes y catalogo publico + gestion menu (operador)."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_restaurant_ownership
from app.core.exceptions import AppException, create_success_response
from app.models.restaurant import Product
from app.models.user import RoleEnum
from app.schemas.common import ProductUpdate, RestaurantCreate, RestaurantUpdate
from app.services import catalog as catalog_service

router = APIRouter()


@router.get("")
async def list_restaurants(
    db: DbSession,
    open_only: bool = Query(default=True),
) -> JSONResponse:
    data = await catalog_service.list_restaurants(db, only_open=open_only)
    return create_success_response(data)


@router.get("/admin/menu")
async def admin_menu(restaurant_id: UUID, user: CurrentUser, db: DbSession) -> JSONResponse:
    await require_restaurant_ownership(restaurant_id, user, db)
    data = await catalog_service.get_menu(db, restaurant_id)
    return create_success_response(data)


@router.get("/{restaurant_id}")
async def get_restaurant(restaurant_id: UUID, db: DbSession) -> JSONResponse:
    data = await catalog_service.get_menu(db, restaurant_id)
    return create_success_response({"id": str(restaurant_id), "menu_items": len(data["products"])})


@router.get("/{restaurant_id}/menu")
async def get_menu(restaurant_id: UUID, db: DbSession) -> JSONResponse:
    data = await catalog_service.get_menu(db, restaurant_id)
    return create_success_response(data)


# ---- Admin: crear restaurante (SUPER_ADMIN) ----
@router.post("", status_code=201)
async def create_restaurant(
    body: RestaurantCreate, user: CurrentUser, db: DbSession
) -> JSONResponse:
    if user.role != RoleEnum.SUPER_ADMIN:
        raise AppException("FORBIDDEN_ROLE", "Solo Super Admin crea restaurantes.", 403)
    r = await catalog_service.create_restaurant(
        db,
        body.name,
        body.phone_number,
        body.address,
        body.latitude,
        body.longitude,
        body.commission_rate,
    )
    return create_success_response({"id": str(r.id)}, "Restaurante creado.", 201)


@router.patch("/{restaurant_id}")
async def update_restaurant(
    restaurant_id: UUID, body: RestaurantUpdate, user: CurrentUser, db: DbSession
) -> JSONResponse:
    await require_restaurant_ownership(restaurant_id, user, db)
    from app.models.restaurant import Restaurant

    stmt = select(Restaurant).where(Restaurant.id == restaurant_id)
    r = (await db.execute(stmt)).scalar_one_or_none()
    if r is None:
        raise AppException("RESTAURANT_NOT_FOUND", "No encontrado.", 404)
    if body.name is not None:
        r.name = body.name
    if body.phone_number is not None:
        r.phone_number = body.phone_number
    if body.address is not None:
        r.address = body.address
    if body.latitude is not None and body.longitude is not None:
        r.location = f"POINT({body.longitude} {body.latitude})"
    if body.commission_rate is not None:
        r.commission_rate = Decimal(body.commission_rate)
    if body.is_open is not None:
        r.is_open = body.is_open
    if body.is_active is not None:
        if user.role != RoleEnum.SUPER_ADMIN:
            raise AppException("FORBIDDEN_ROLE", "Solo Super Admin activa/desactiva.", 403)
        r.is_active = body.is_active
    await db.commit()
    await catalog_service.invalidate_menu(restaurant_id)
    return create_success_response({"id": str(r.id)})


# ---- Admin menu: toggle stock rapido ----
@router.patch("/products/{product_id}")
async def patch_product(
    product_id: UUID, body: ProductUpdate, user: CurrentUser, db: DbSession
) -> JSONResponse:
    stmt = select(Product).where(Product.id == product_id)
    p = (await db.execute(stmt)).scalar_one_or_none()
    if p is None:
        raise AppException("PRODUCT_NOT_FOUND", "No encontrado.", 404)
    await require_restaurant_ownership(p.restaurant_id, user, db)
    updated = await catalog_service.patch_product(db, product_id, body.model_dump())
    return create_success_response({"id": str(updated.id), "is_available": updated.is_available})
