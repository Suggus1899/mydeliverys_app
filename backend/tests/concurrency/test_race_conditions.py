import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.order import Order, OrderStatusEnum
from app.models.restaurant import Restaurant
from app.models.user import RoleEnum, User


class TestDoubleAssignment:
    """Test: 50 drivers try to accept the same order simultaneously."""

    @pytest.mark.asyncio
    async def test_double_assignment_prevented(self, db_session):
        # Create test data
        customer = User(
            id=uuid4(),
            phone_number="+584140000001",
            full_name="Customer",
            role=RoleEnum.CUSTOMER,
        )
        db_session.add(customer)

        restaurant = Restaurant(
            id=uuid4(),
            name="Test Restaurant",
            phone_number="+584140000002",
            address="Calle Principal",
            location="POINT(-67.35 9.75)",
        )
        db_session.add(restaurant)

        address = User(
            id=uuid4(),
            phone_number="+584140000003",
            full_name="Address Owner",
            role=RoleEnum.CUSTOMER,
        )
        db_session.add(address)

        # Create order in READY_FOR_PICKUP
        order = Order(
            id=uuid4(),
            order_number="SJM-2026-TEST001",
            customer_id=customer.id,
            restaurant_id=restaurant.id,
            driver_id=None,  # No driver assigned yet
            delivery_address_id=address.id,
            status=OrderStatusEnum.READY_FOR_PICKUP,
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
        await db_session.commit()

        # Simulate 50 drivers trying to accept simultaneously
        async def try_accept(driver_id: uuid4):
            # This simulates the atomic update:
            # Aceptar asigna al conductor sin simular la recogida.
            # WHERE id = :order_id AND driver_id IS NULL AND status = 'READY_FOR_PICKUP'
            from sqlalchemy import update

            stmt = (
                update(Order)
                .where(
                    Order.id == order.id,
                    Order.driver_id.is_(None),
                    Order.status == OrderStatusEnum.READY_FOR_PICKUP,
                )
                .values(driver_id=driver_id)
                .returning(Order.id)
            )
            result = await db_session.execute(stmt)
            return result.scalar_one_or_none() is not None

        # Create 50 driver IDs
        driver_ids = [uuid4() for _ in range(50)]

        # Run all attempts concurrently
        tasks = [try_accept(did) for did in driver_ids]
        results = await asyncio.gather(*tasks)

        # Exactly 1 should succeed
        success_count = sum(1 for r in results if r)
        assert success_count == 1, f"Expected 1 success, got {success_count}"

        # Verify final state
        await db_session.refresh(order)
        assert order.driver_id is not None
        assert order.status == OrderStatusEnum.READY_FOR_PICKUP


class TestInventoryRaceCondition:
    """Test: 20 customers try to buy 3 units of a product."""

    @pytest.mark.asyncio
    async def test_stock_not_oversold(self, db_session, test_restaurant, test_category):
        from app.models.restaurant import Product

        # Create product with 3 units in stock
        product = Product(
            id=uuid4(),
            restaurant_id=test_restaurant.id,
            category_id=test_category.id,
            name="Limited Product",
            base_price=Decimal("10.00"),
            is_available=True,
            track_stock=True,
            stock=3,
        )
        db_session.add(product)
        await db_session.commit()

        async def try_buy():
            from sqlalchemy import update

            stmt = (
                update(Product)
                .where(
                    Product.id == product.id,
                    Product.track_stock.is_(True),
                    Product.stock >= 1,
                )
                .values(stock=Product.stock - 1)
                .returning(Product.stock)
            )
            result = await db_session.execute(stmt)
            new_stock = result.scalar_one_or_none()
            return new_stock is not None and new_stock >= 0

        # 20 concurrent buyers
        tasks = [try_buy() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # Exactly 3 should succeed
        success_count = sum(1 for r in results if r)
        assert success_count == 3, f"Expected 3 successes, got {success_count}"

        # Verify final stock is 0
        await db_session.refresh(product)
        assert product.stock == 0


class TestIdempotency:
    """Test: 10 requests with same idempotency key."""

    @pytest.mark.asyncio
    async def test_idempotent_payment_report(
        self, db_session, test_user, test_restaurant, test_address
    ):
        from app.models.order import Order, OrderStatusEnum
        from app.models.payment import (
            Payment,
            PaymentMethodEnum,
            PaymentPhaseEnum,
            PaymentStatusEnum,
        )

        order = Order(
            id=uuid4(),
            order_number="SJM-2026-IDEMPOTENT",
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
        await db_session.commit()

        idempotency_key = "REDACTED"
        scope = "customer:payment_report"

        async def try_report():
            # Simulate idempotency check + insert
            from sqlalchemy import select

            from app.models.payment import IdempotencyKey

            # Check if already processed
            stmt = select(IdempotencyKey).where(
                IdempotencyKey.key == idempotency_key,
                IdempotencyKey.scope == scope,
            )
            existing = await db_session.execute(stmt)
            if existing.scalar_one_or_none():
                return "duplicate"

            # Insert payment
            payment = Payment(
                id=uuid4(),
                order_id=order.id,
                phase=PaymentPhaseEnum.FIRST_HALF,
                method=PaymentMethodEnum.PAGO_MOVIL,
                amount=Decimal("6.50"),
                status=PaymentStatusEnum.PENDING,
                reference_number="REF123",
                origin_bank="BDV",
                idempotency_key=idempotency_key,
                idempotency_scope=scope,
            )
            db_session.add(payment)

            # Store idempotency key
            idempotency = IdempotencyKey(
                key=idempotency_key,
                scope=scope,
                request_hash="abc123",
                response_status=200,
                response_body={"success": True},
            )
            db_session.add(idempotency)

            await db_session.commit()
            return "success"

        # 10 concurrent requests with same key
        tasks = [try_report() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Only 1 should succeed, rest should be "duplicate" or handle gracefully
        success_count = sum(1 for r in results if r == "success")
        duplicate_count = sum(1 for r in results if r == "duplicate")

        assert success_count == 1, f"Expected 1 success, got {success_count}"
        assert duplicate_count == 9, f"Expected 9 duplicates, got {duplicate_count}"

        # Verify only 1 payment created
        from sqlalchemy import select

        stmt = select(Payment).where(Payment.order_id == order.id)
        payments = await db_session.execute(stmt)
        assert len(payments.scalars().all()) == 1
