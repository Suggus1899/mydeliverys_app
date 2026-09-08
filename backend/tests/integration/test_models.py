from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.models.order import Order, OrderItem, OrderStatusEnum
from app.models.payment import Payment, PaymentMethodEnum, PaymentPhaseEnum, PaymentStatusEnum
from app.models.restaurant import Category, Product, Restaurant
from app.models.user import RoleEnum, User


class TestUserModel:
    @pytest.mark.asyncio
    async def test_create_user(self, db_session):
        user = User(
            id=uuid4(),
            phone_number="+584140000001",
            full_name="Test User",
            role=RoleEnum.CUSTOMER,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.id is not None
        assert user.phone_number == "+584140000001"
        assert user.full_name == "Test User"
        assert user.role == RoleEnum.CUSTOMER
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_user_with_password(self, db_session):
        user = User(
            id=uuid4(),
            phone_number="+584140000002",
            full_name="Driver User",
            role=RoleEnum.DRIVER,
            password_hash=hash_password("securepassword123"),
        )
        db_session.add(user)
        await db_session.commit()

        assert user.password_hash is not None
        assert user.password_hash != "securepassword123"


class TestRestaurantModel:
    @pytest.mark.asyncio
    async def test_create_restaurant(self, db_session):
        restaurant = Restaurant(
            id=uuid4(),
            name="Test Restaurant",
            phone_number="+584140000003",
            address="Calle Principal, San Juan de los Morros",
            location="POINT(-67.35 9.75)",
            commission_rate=Decimal("15.00"),
        )
        db_session.add(restaurant)
        await db_session.commit()
        await db_session.refresh(restaurant)

        assert restaurant.id is not None
        assert restaurant.is_open is True
        assert restaurant.is_active is True

    @pytest.mark.asyncio
    async def test_restaurant_with_category_and_product(self, db_session):
        restaurant = Restaurant(
            id=uuid4(),
            name="Test Restaurant",
            phone_number="+584140000004",
            address="Calle Principal",
            location="POINT(-67.35 9.75)",
        )
        db_session.add(restaurant)

        category = Category(
            id=uuid4(),
            restaurant_id=restaurant.id,
            name="Hamburguesas",
            sort_order=1,
        )
        db_session.add(category)

        product = Product(
            id=uuid4(),
            restaurant_id=restaurant.id,
            category_id=category.id,
            name="Hamburguesa Clásica",
            base_price=Decimal("5.00"),
            is_available=True,
            track_stock=True,
            stock=10,
        )
        db_session.add(product)

        await db_session.commit()

        assert product.restaurant_id == restaurant.id
        assert product.category_id == category.id


class TestOrderModel:
    @pytest.mark.asyncio
    async def test_create_order_with_items(
        self, db_session, test_user, test_restaurant, test_product, test_address
    ):
        order = Order(
            id=uuid4(),
            order_number="SJM-2026-0001",
            customer_id=test_user.id,
            restaurant_id=test_restaurant.id,
            delivery_address_id=test_address.id,
            status=OrderStatusEnum.PAYMENT_1_PENDING,
            subtotal_amount=Decimal("10.00"),
            delivery_fee=Decimal("2.00"),
            platform_fee=Decimal("1.00"),
            total_amount=Decimal("13.00"),
            first_half_amount=Decimal("6.50"),
            second_half_amount=Decimal("6.50"),
            delivery_distance_m=Decimal("5000.00"),
            exchange_rate=Decimal("36.50"),
            exchange_rate_source="dolarapi_oficial",
            exchange_rate_effective_date="2026-09-07",
            exchange_rate_queried_at="2026-09-07T12:00:00+00:00",
            quote_snapshot={"items": []},
        )
        db_session.add(order)

        item = OrderItem(
            id=uuid4(),
            order_id=order.id,
            product_id=test_product.id,
            quantity=2,
            unit_price=Decimal("5.00"),
            total_price=Decimal("10.00"),
            product_snapshot={"name": "Hamburguesa Clásica", "base_price": "5.00"},
        )
        db_session.add(item)

        await db_session.commit()

        assert order.id is not None
        assert len(order.items) == 1


class TestPaymentModel:
    @pytest.mark.asyncio
    async def test_create_payment(self, db_session, test_user, test_restaurant, test_address):
        order = Order(
            id=uuid4(),
            order_number="SJM-2026-0002",
            customer_id=test_user.id,
            restaurant_id=test_restaurant.id,
            delivery_address_id=test_address.id,
            status=OrderStatusEnum.PAYMENT_1_PENDING,
            subtotal_amount=Decimal("10.00"),
            delivery_fee=Decimal("2.00"),
            platform_fee=Decimal("1.00"),
            total_amount=Decimal("13.00"),
            first_half_amount=Decimal("6.50"),
            second_half_amount=Decimal("6.50"),
            delivery_distance_m=Decimal("5000.00"),
            exchange_rate=Decimal("36.50"),
            exchange_rate_source="dolarapi_oficial",
            exchange_rate_effective_date="2026-09-07",
            exchange_rate_queried_at="2026-09-07T12:00:00+00:00",
            quote_snapshot={"items": []},
        )
        db_session.add(order)
        await db_session.flush()

        payment = Payment(
            id=uuid4(),
            order_id=order.id,
            phase=PaymentPhaseEnum.FIRST_HALF,
            method=PaymentMethodEnum.PAGO_MOVIL,
            amount=Decimal("6.50"),
            status=PaymentStatusEnum.PENDING,
            reference_number="REF123456",
            origin_bank="BDV",
        )
        db_session.add(payment)
        await db_session.commit()

        assert payment.id is not None
        assert payment.phase == PaymentPhaseEnum.FIRST_HALF
        assert payment.status == PaymentStatusEnum.PENDING
