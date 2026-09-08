from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    driver,
    orders,
    payments,
    restaurant_ops,
    restaurants,
    tracking,
    users,
)

api_router = APIRouter()

# Authentication
api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación"])

# Users / Profile
api_router.include_router(users.router, prefix="/users", tags=["Usuarios y Perfil"])

# Restaurants & Catalog
api_router.include_router(
    restaurants.router, prefix="/restaurants", tags=["Restaurantes y Catálogo"]
)

# Orders
api_router.include_router(orders.router, prefix="/orders", tags=["Pedidos"])

# Payments
api_router.include_router(payments.router, prefix="/payments", tags=["Pagos"])

# Driver
api_router.include_router(driver.router, prefix="/driver", tags=["Repartidor"])

# Admin
api_router.include_router(admin.router, prefix="/admin", tags=["Administración"])

# Tracking / WebSocket
api_router.include_router(tracking.router, prefix="/tracking", tags=["Seguimiento"])

# Cocina / Restaurante operativo
api_router.include_router(restaurant_ops.router, prefix="/restaurant", tags=["Cocina"])
