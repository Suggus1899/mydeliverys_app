from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Standard Response Wrapper
# =============================================================================


class StandardResponse(BaseModel):
    """Standardized API response format."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool
    error_code: str | None = None
    message: str
    data: Any | None = None


def success_response(
    data: Any = None, message: str = "Operación completada con éxito."
) -> StandardResponse:
    return StandardResponse(success=True, error_code=None, message=message, data=data)


def error_response(error_code: str, message: str, data: Any = None) -> StandardResponse:
    return StandardResponse(success=False, error_code=error_code, message=message, data=data)


# =============================================================================
# Pagination
# =============================================================================


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    limit: int
    total_pages: int


# =============================================================================
# Auth Schemas
# =============================================================================


class PhoneRequest(BaseModel):
    phone: str = Field(..., description="Phone number in E.164 format (+58414...)")


class OTPRequest(BaseModel):
    phone: str = Field(..., description="Phone number in E.164 format")
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class OTPResponse(BaseModel):
    message: str = "OTP enviado"
    expires_in_seconds: int = 180


class LoginRequest(BaseModel):
    phone: str = Field(..., description="Phone number in E.164 format")
    password: str = Field(..., min_length=8)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access token lifetime in seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


class TOTPSetupResponse(BaseModel):
    secret: str
    qr_code_url: str
    recovery_codes: list[str]


class TOTPVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class RecoveryCodeRequest(BaseModel):
    code: str = Field(..., min_length=10, max_length=16)


# =============================================================================
# User Schemas
# =============================================================================


class UserAddressBase(BaseModel):
    label: str = Field(..., max_length=50)
    address_line: str
    reference_point: str | None = None
    latitude: Decimal = Field(..., ge=-90, le=90)
    longitude: Decimal = Field(..., ge=-180, le=180)
    is_default: bool = False


class UserAddressCreate(UserAddressBase):
    pass


class UserAddressUpdate(BaseModel):
    label: str | None = Field(None, max_length=50)
    address_line: str | None = None
    reference_point: str | None = None
    latitude: Decimal | None = Field(None, ge=-90, le=90)
    longitude: Decimal | None = Field(None, ge=-180, le=180)
    is_default: bool | None = None


class UserAddressResponse(UserAddressBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponse(BaseModel):
    id: UUID
    phone_number: str
    full_name: str
    email: str | None
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    full_name: str | None = Field(None, max_length=120)
    email: str | None = Field(None, max_length=120)


# =============================================================================
# Restaurant & Catalog Schemas
# =============================================================================


class RestaurantSummary(BaseModel):
    id: UUID
    name: str
    phone_number: str
    address: str
    latitude: Decimal
    longitude: Decimal
    commission_rate: Decimal
    is_open: bool
    is_active: bool
    distance_km: Decimal | None = None
    estimated_time_min: int | None = None

    model_config = ConfigDict(from_attributes=True)


class RestaurantCreate(BaseModel):
    name: str = Field(..., max_length=120)
    phone_number: str = Field(..., max_length=20)
    address: str
    latitude: Decimal = Field(..., ge=-90, le=90)
    longitude: Decimal = Field(..., ge=-180, le=180)
    commission_rate: Decimal = Field(default=Decimal("15.00"), ge=0, le=100)


class RestaurantUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    phone_number: str | None = Field(None, max_length=20)
    address: str | None = None
    latitude: Decimal | None = Field(None, ge=-90, le=90)
    longitude: Decimal | None = Field(None, ge=-180, le=180)
    commission_rate: Decimal | None = Field(None, ge=0, le=100)
    is_open: bool | None = None
    is_active: bool | None = None


class RestaurantDetail(RestaurantSummary):
    created_at: datetime
    updated_at: datetime


class CategoryBase(BaseModel):
    name: str = Field(..., max_length=100)
    sort_order: int = 0
    is_active: bool = True


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryResponse(CategoryBase):
    id: UUID
    restaurant_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModifierBase(BaseModel):
    name: str = Field(..., max_length=100)
    extra_price: Decimal = Field(default=Decimal("0.00"), ge=0)
    is_available: bool = True
    track_stock: bool = False
    stock: int | None = Field(None, ge=0)


class ModifierCreate(ModifierBase):
    pass


class ModifierUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    extra_price: Decimal | None = Field(None, ge=0)
    is_available: bool | None = None
    track_stock: bool | None = None
    stock: int | None = Field(None, ge=0)


class ModifierResponse(ModifierBase):
    id: UUID
    group_id: UUID

    model_config = ConfigDict(from_attributes=True)


class ModifierGroupBase(BaseModel):
    name: str = Field(..., max_length=100)
    min_selectable: int = Field(default=0, ge=0)
    max_selectable: int = Field(default=1, ge=1)
    is_required: bool = False


class ModifierGroupCreate(ModifierGroupBase):
    modifiers: list[ModifierCreate] = []


class ModifierGroupUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    min_selectable: int | None = Field(None, ge=0)
    max_selectable: int | None = Field(None, ge=1)
    is_required: bool | None = None


class ModifierGroupResponse(ModifierGroupBase):
    id: UUID
    product_id: UUID
    modifiers: list[ModifierResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str = Field(..., max_length=120)
    description: str | None = None
    base_price: Decimal = Field(..., ge=0)
    image_url: str | None = None
    is_available: bool = True
    track_stock: bool = False
    stock: int | None = Field(None, ge=0)


class ProductCreate(ProductBase):
    category_id: UUID
    modifier_groups: list[ModifierGroupCreate] = []


class ProductUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    description: str | None = None
    base_price: Decimal | None = Field(None, ge=0)
    image_url: str | None = None
    is_available: bool | None = None
    track_stock: bool | None = None
    stock: int | None = Field(None, ge=0)
    category_id: UUID | None = None


class ProductResponse(ProductBase):
    id: UUID
    restaurant_id: UUID
    category_id: UUID
    category_name: str | None = None
    modifier_groups: list[ModifierGroupResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MenuResponse(BaseModel):
    restaurant_id: UUID
    restaurant_name: str
    categories: list[CategoryResponse] = []
    products: list[ProductResponse] = []


# =============================================================================
# Cart / Order Draft Schemas
# =============================================================================


class CartItemModifier(BaseModel):
    modifier_id: UUID
    quantity: int = Field(default=1, ge=1)


class CartItem(BaseModel):
    product_id: UUID
    quantity: int = Field(..., ge=1, le=99)
    modifiers: list[CartItemModifier] = []


class OrderDraftRequest(BaseModel):
    items: list[CartItem] = Field(..., min_length=1)
    address_id: UUID


class PaymentBreakdown(BaseModel):
    total: str  # Decimal as string
    first_half: str
    second_half: str
    first_half_ves: str | None = None
    second_half_ves: str | None = None
    exchange_rate: str | None = None


class OrderDraftResponse(BaseModel):
    order_id: UUID
    order_number: str
    status: str
    subtotal_amount: str
    delivery_fee: str
    platform_fee: str
    total_amount: str
    payment_breakdown: PaymentBreakdown
    delivery_distance_m: str
    quote_expires_at: datetime
    quote_snapshot: dict
