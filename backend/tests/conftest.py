import asyncio
import os
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import Base, get_db
from app.core.security import create_token_pair, hash_password
from app.main import create_app
from app.models import *  # noqa: F403,F401

# Test database URL (uses test database)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://mydeliverys:postgres@localhost:6432/mydeliverys_test",
)

# Override settings for testing
os.environ["ENVIRONMENT"] = "test"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["LOG_LEVEL"] = "DEBUG"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncSession:
    """Create a database session for a test."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with async_session() as session:
        # Begin transaction
        await session.begin()
        try:
            yield session
        finally:
            # Rollback to clean state
            await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session) -> AsyncClient:
    """Create test client with database dependency override."""
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def test_user_data():
    return {
        "phone": "+584140000001",
        "full_name": "Test User",
        "role": "CUSTOMER",
    }


@pytest.fixture
def test_restaurant_data():
    return {
        "name": "Test Restaurant",
        "phone_number": "+584140000002",
        "address": "Calle Principal, San Juan de los Morros",
        "latitude": Decimal("9.75"),
        "longitude": Decimal("-67.35"),
        "commission_rate": Decimal("15.00"),
    }


@pytest.fixture
def test_category_data(test_restaurant_data):
    return {
        "name": "Hamburguesas",
        "sort_order": 1,
    }


@pytest.fixture
def test_product_data():
    return {
        "name": "Hamburguesa Clásica",
        "description": "Carne, queso, lechuga, tomate",
        "base_price": Decimal("5.00"),
        "is_available": True,
        "track_stock": True,
        "stock": 10,
    }


@pytest.fixture
def test_modifier_group_data():
    return {
        "name": "Tipo de Queso",
        "min_selectable": 1,
        "max_selectable": 1,
    }


@pytest.fixture
def test_modifier_data():
    return [
        {"name": "Cheddar", "extra_price": Decimal("0.50")},
        {"name": "Suizo", "extra_price": Decimal("0.75")},
    ]


@pytest.fixture
def test_address_data():
    return {
        "label": "Casa",
        "address_line": "Urb. Los Rosales, Calle 5, Casa 12",
        "reference_point": "Frente al parque",
        "latitude": Decimal("9.76"),
        "longitude": Decimal("-67.34"),
    }


# =============================================================================
# Auth Helpers
# =============================================================================


def create_test_tokens(user_id: str, role: str):
    """Create test access and refresh tokens."""
    return create_token_pair(user_id, role)


def auth_headers(access_token: str):
    """Return authorization headers."""
    return {"Authorization": f"Bearer {access_token}"}


# =============================================================================
# Async Fixtures for Created Entities
# =============================================================================


@pytest_asyncio.fixture
async def test_user(db_session, test_user_data):
    from app.models.user import RoleEnum, User

    user = User(
        id=uuid4(),
        phone_number=test_user_data["phone"],
        full_name=test_user_data["full_name"],
        role=RoleEnum(test_user_data["role"]),
        password_hash=hash_password("testpassword123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_restaurant(db_session, test_restaurant_data):
    from app.models.restaurant import Restaurant

    restaurant = Restaurant(
        id=uuid4(),
        name=test_restaurant_data["name"],
        phone_number=test_restaurant_data["phone_number"],
        address=test_restaurant_data["address"],
        location=f"POINT({test_restaurant_data['longitude']} {test_restaurant_data['latitude']})",
        commission_rate=test_restaurant_data["commission_rate"],
    )
    db_session.add(restaurant)
    await db_session.commit()
    await db_session.refresh(restaurant)
    return restaurant


@pytest_asyncio.fixture
async def test_category(db_session, test_restaurant, test_category_data):
    from app.models.restaurant import Category

    category = Category(
        id=uuid4(),
        restaurant_id=test_restaurant.id,
        name=test_category_data["name"],
        sort_order=test_category_data["sort_order"],
    )
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)
    return category


@pytest_asyncio.fixture
async def test_product(db_session, test_restaurant, test_category, test_product_data):
    from app.models.restaurant import Product

    product = Product(
        id=uuid4(),
        restaurant_id=test_restaurant.id,
        category_id=test_category.id,
        **test_product_data,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest_asyncio.fixture
async def test_modifier_group(db_session, test_product, test_modifier_group_data):
    from app.models.restaurant import ModifierGroup

    group = ModifierGroup(
        id=uuid4(),
        product_id=test_product.id,
        **test_modifier_group_data,
    )
    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)
    return group


@pytest_asyncio.fixture
async def test_modifiers(db_session, test_modifier_group, test_modifier_data):
    from app.models.restaurant import Modifier

    modifiers = []
    for mod_data in test_modifier_data:
        modifier = Modifier(
            id=uuid4(),
            group_id=test_modifier_group.id,
            **mod_data,
        )
        db_session.add(modifier)
        modifiers.append(modifier)

    await db_session.commit()
    for mod in modifiers:
        await db_session.refresh(mod)
    return modifiers


@pytest_asyncio.fixture
async def test_address(db_session, test_user, test_address_data):
    from app.models.user import UserAddress

    address = UserAddress(
        id=uuid4(),
        user_id=test_user.id,
        location=f"POINT({test_address_data['longitude']} {test_address_data['latitude']})",
        **{k: v for k, v in test_address_data.items() if k not in ["latitude", "longitude"]},
    )
    db_session.add(address)
    await db_session.commit()
    await db_session.refresh(address)
    return address


@pytest_asyncio.fixture
def test_tokens(test_user):
    return create_test_tokens(str(test_user.id), test_user.role.value)
