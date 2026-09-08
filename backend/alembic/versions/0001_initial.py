"""Initial migration - Create all tables for mydeliverys_app

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-07

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # =========================================================================
    # users table
    # =========================================================================
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(120), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("totp_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("totp_recovery_hashes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "role",
            sa.Enum("CUSTOMER", "DRIVER", "RESTAURANT_ADMIN", "SUPER_ADMIN", name="role_enum"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_number", name="uq_users_phone_number"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_phone_number", "users", ["phone_number"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index("ix_users_role", "users", ["role"], unique=False)

    # =========================================================================
    # user_addresses table
    # =========================================================================
    op.create_table(
        "user_addresses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(50), nullable=False),
        sa.Column("address_line", sa.Text(), nullable=False),
        sa.Column("reference_point", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=False),  # WKT Point
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_addresses_user_id", "user_addresses", ["user_id"], unique=False)
    op.create_index(
        "ix_user_addresses_user_id_is_default",
        "user_addresses",
        ["user_id", "is_default"],
        unique=False,
    )

    # =========================================================================
    # user_sessions table
    # =========================================================================
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_token_hash", sa.String(255), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(30), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"], unique=False)
    op.create_index(
        "ix_user_sessions_user_id_revoked", "user_sessions", ["user_id", "revoked_at"], unique=False
    )

    # =========================================================================
    # restaurants table
    # =========================================================================
    op.create_table(
        "restaurants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),  # WKT Point
        sa.Column("commission_rate", sa.Numeric(5, 2), nullable=False, server_default="15.00"),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_restaurants_name", "restaurants", ["name"], unique=False)
    op.create_index("ix_restaurants_is_open", "restaurants", ["is_open"], unique=False)
    op.create_index("ix_restaurants_is_active", "restaurants", ["is_active"], unique=False)

    # =========================================================================
    # restaurant_staff table
    # =========================================================================
    op.create_table(
        "restaurant_staff",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_restaurant_staff_user_id"),
    )
    op.create_index(
        "ix_restaurant_staff_restaurant_id", "restaurant_staff", ["restaurant_id"], unique=False
    )

    # =========================================================================
    # categories table
    # =========================================================================
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_categories_restaurant_id", "categories", ["restaurant_id"], unique=False)
    op.create_index(
        "ix_categories_restaurant_id_sort_order",
        "categories",
        ["restaurant_id", "sort_order"],
        unique=False,
    )

    # =========================================================================
    # products table
    # =========================================================================
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("track_stock", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("stock", sa.Integer(), nullable=True),  # NULL = unlimited
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_restaurant_id", "products", ["restaurant_id"], unique=False)
    op.create_index("ix_products_category_id", "products", ["category_id"], unique=False)
    op.create_index(
        "ix_products_restaurant_id_is_available",
        "products",
        ["restaurant_id", "is_available"],
        unique=False,
    )

    # =========================================================================
    # modifier_groups table
    # =========================================================================
    op.create_table(
        "modifier_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("min_selectable", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_selectable", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_modifier_groups_product_id", "modifier_groups", ["product_id"], unique=False
    )

    # =========================================================================
    # modifiers table
    # =========================================================================
    op.create_table(
        "modifiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("extra_price", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("track_stock", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("stock", sa.Integer(), nullable=True),  # NULL = unlimited
        sa.ForeignKeyConstraint(["group_id"], ["modifier_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_modifiers_group_id", "modifiers", ["group_id"], unique=False)

    # =========================================================================
    # orders table
    # =========================================================================
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_number", sa.String(20), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("delivery_address_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PAYMENT_1_PENDING",
                "PAYMENT_1_VERIFYING",
                "PREPARING",
                "READY_FOR_PICKUP",
                "ON_THE_WAY",
                "ARRIVED_AT_CUSTOMER",
                "PAYMENT_2_VERIFYING",
                "DELIVERED",
                "CANCELLED",
                "REJECTED",
                "CANCELLED_WITH_REFUND",
                "DELIVERY_FAILED",
                name="order_status_enum",
            ),
            nullable=False,
            server_default="PAYMENT_1_PENDING",
        ),
        sa.Column("subtotal_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("delivery_fee", sa.Numeric(10, 2), nullable=False),
        sa.Column("platform_fee", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("first_half_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("second_half_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_ves_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("first_half_ves_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("second_half_ves_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("delivery_distance_m", sa.Numeric(10, 2), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(14, 6), nullable=False),
        sa.Column(
            "exchange_rate_source", sa.String(30), nullable=False, server_default="dolarapi_oficial"
        ),
        sa.Column("exchange_rate_effective_date", sa.String(10), nullable=False),
        sa.Column("exchange_rate_queried_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quote_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quote_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("arrived_at_restaurant_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("arrived_at_customer_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["driver_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["delivery_address_id"], ["user_addresses.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_number", name="uq_orders_order_number"),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"], unique=False)
    op.create_index("ix_orders_restaurant_id", "orders", ["restaurant_id"], unique=False)
    op.create_index("ix_orders_driver_id", "orders", ["driver_id"], unique=False)
    op.create_index("ix_orders_status", "orders", ["status"], unique=False)
    op.create_index("ix_orders_created_at", "orders", ["created_at"], unique=False)
    op.create_index(
        "ix_orders_customer_id_status", "orders", ["customer_id", "status"], unique=False
    )
    op.create_index(
        "ix_orders_restaurant_id_status", "orders", ["restaurant_id", "status"], unique=False
    )
    op.create_index("ix_orders_driver_id_status", "orders", ["driver_id", "status"], unique=False)
    op.create_index("ix_orders_status_created_at", "orders", ["status", "created_at"], unique=False)
    op.execute(
        "CREATE UNIQUE INDEX uq_orders_driver_active ON orders (driver_id) "
        "WHERE driver_id IS NOT NULL AND status IN "
        "('READY_FOR_PICKUP','ON_THE_WAY','ARRIVED_AT_CUSTOMER','PAYMENT_2_VERIFYING');"
    )

    # =========================================================================
    # order_items table
    # =========================================================================
    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("product_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"], unique=False)

    # =========================================================================
    # order_modifiers table
    # =========================================================================
    op.create_table(
        "order_modifiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("modifier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("modifier_name", sa.String(100), nullable=False),
        sa.Column("extra_price", sa.Numeric(10, 2), nullable=False),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["modifier_id"], ["modifiers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_order_modifiers_order_item_id", "order_modifiers", ["order_item_id"], unique=False
    )

    # =========================================================================
    # order_reservations table
    # =========================================================================
    op.create_table(
        "order_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "reserved_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", name="uq_order_reservations_order_id"),
    )
    op.create_index(
        "ix_order_reservations_expires_at", "order_reservations", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_order_reservations_status_expires_at",
        "order_reservations",
        ["status", "expires_at"],
        unique=False,
    )

    # =========================================================================
    # payments table
    # =========================================================================
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "phase", sa.Enum("FIRST_HALF", "SECOND_HALF", name="payment_phase_enum"), nullable=False
        ),
        sa.Column(
            "method",
            sa.Enum(
                "PAGO_MOVIL",
                "BANK_TRANSFER",
                "CASH_USD",
                "CASH_VES",
                name="payment_method_enum",
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("ves_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("exchange_rate_used", sa.Numeric(14, 6), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "VERIFIED", "REJECTED", name="payment_status_enum"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("reference_number", sa.String(50), nullable=True),
        sa.Column("origin_bank", sa.String(50), nullable=True),
        sa.Column("proof_image_url", sa.Text(), nullable=True),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reconciliation_status",
            sa.Enum(
                "PENDING",
                "MATCHED",
                "DISCREPANCY",
                "REFUNDED",
                "ADJUSTED",
                name="reconciliation_status_enum",
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("discrepancy_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("idempotency_scope", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_order_id", "payments", ["order_id"], unique=False)
    op.create_index("ix_payments_order_id_phase", "payments", ["order_id", "phase"], unique=False)
    op.create_index("ix_payments_status", "payments", ["status"], unique=False)
    op.create_index("ix_payments_status_phase", "payments", ["status", "phase"], unique=False)
    op.create_index(
        "ix_payments_idempotency",
        "payments",
        ["idempotency_key", "idempotency_scope"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_payment_order_phase_idempotency", "payments", ["order_id", "phase", "idempotency_key"]
    )

    # =========================================================================
    # idempotency_keys table
    # =========================================================================
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(50), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", "scope"),
    )
    op.create_index(
        "ix_idempotency_keys_expires_at", "idempotency_keys", ["expires_at"], unique=False
    )

    # =========================================================================
    # delivery_tracking table
    # =========================================================================
    op.create_table(
        "delivery_tracking",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),  # WKT Point
        sa.Column("battery_level", sa.Integer(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("is_historical", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["driver_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_delivery_tracking_order_id", "delivery_tracking", ["order_id"], unique=False
    )
    op.create_index(
        "ix_delivery_tracking_driver_id", "delivery_tracking", ["driver_id"], unique=False
    )
    op.create_index(
        "ix_delivery_tracking_order_id_recorded_at",
        "delivery_tracking",
        ["order_id", "recorded_at"],
        unique=False,
    )

    # =========================================================================
    # geofence_events table
    # =========================================================================
    op.create_table(
        "geofence_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("triggered_by", sa.String(20), nullable=False),
        sa.Column("distance_m", sa.Numeric(10, 2), nullable=True),
        sa.Column("accuracy_m", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["driver_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_geofence_events_order_id", "geofence_events", ["order_id"], unique=False)
    op.create_index(
        "ix_geofence_events_order_id_created_at",
        "geofence_events",
        ["order_id", "created_at"],
        unique=False,
    )

    # =========================================================================
    # exchange_rates table
    # =========================================================================
    op.create_table(
        "exchange_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rate", sa.Numeric(14, 6), nullable=False),
        sa.Column("source", sa.String(30), nullable=False, server_default="dolarapi_oficial"),
        sa.Column("reported_date", sa.Date(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column(
            "queried_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("validation_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exchange_rates_reported_date", "exchange_rates", ["reported_date"], unique=False
    )
    op.create_index(
        "ix_exchange_rates_effective_date", "exchange_rates", ["effective_date"], unique=False
    )
    op.create_index("ix_exchange_rates_queried_at", "exchange_rates", ["queried_at"], unique=False)
    op.create_index("ix_exchange_rates_is_valid", "exchange_rates", ["is_valid"], unique=False)
    op.create_index(
        "ix_exchange_rates_valid_effective",
        "exchange_rates",
        ["is_valid", "effective_date"],
        unique=False,
    )

    # =========================================================================
    # delivery_fee_tiers table
    # =========================================================================
    op.create_table(
        "delivery_fee_tiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("min_distance_m", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("max_distance_m", sa.Numeric(10, 2), nullable=False),
        sa.Column("fee_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_delivery_fee_tier_name"),
    )
    op.create_index(
        "ix_delivery_fee_tiers_is_active", "delivery_fee_tiers", ["is_active"], unique=False
    )

    # =========================================================================
    # platform_fee_config table
    # =========================================================================
    op.create_table(
        "platform_fee_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fee_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Partial unique index for only one active config
    op.execute(
        "CREATE UNIQUE INDEX ix_platform_fee_config_active ON platform_fee_config (is_active) WHERE is_active = true;"
    )

    # =========================================================================
    # settlements table
    # =========================================================================
    op.create_table(
        "settlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "entity_type",
            sa.Enum("RESTAURANT", "DRIVER", name="settlement_entity_type_enum"),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("commission_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("delivery_fees_collected", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("platform_fees_collected", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("adjustments", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "CONFIRMED", "PAID", "CANCELLED", name="settlement_status_enum"),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("proof_image_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("confirmed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            "period_start",
            "period_end",
            "currency",
            name="uq_settlement_entity_period_currency",
        ),
    )
    op.create_index(
        "ix_settlements_entity_type_id_period",
        "settlements",
        ["entity_type", "entity_id", "period_start", "period_end"],
        unique=False,
    )
    op.create_index("ix_settlements_status", "settlements", ["status"], unique=False)

    # =========================================================================
    # refunds table
    # =========================================================================
    op.create_table(
        "refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "type",
            sa.Enum("FULL", "PARTIAL", "ADJUSTMENT", name="refund_type_enum"),
            nullable=False,
        ),
        sa.Column("amount_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("amount_ves", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "reason",
            sa.Enum(
                "CANCELLED_PREPARING",
                "CANCELLED_ON_THE_WAY",
                "CUSTOMER_ABSENT",
                "DISPUTE",
                "ADMIN_ADJUSTMENT",
                name="refund_reason_enum",
            ),
            nullable=False,
        ),
        sa.Column("reference_number", sa.String(50), nullable=True),
        sa.Column("proof_image_url", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "EXECUTED", "REJECTED", name="refund_status_enum"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refunds_order_id", "refunds", ["order_id"], unique=False)
    op.create_index("ix_refunds_status", "refunds", ["status"], unique=False)

    # =========================================================================
    # audit_logs table
    # =========================================================================
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity_name", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_admin_user_id", "audit_logs", ["admin_user_id"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index(
        "ix_audit_logs_entity_name_entity_id",
        "audit_logs",
        ["entity_name", "entity_id"],
        unique=False,
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)

    op.create_table(
        "order_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_events_order_id", "order_events", ["order_id"], unique=False)
    op.create_index("ix_order_events_event_type", "order_events", ["event_type"], unique=False)
    op.create_index("ix_order_events_created_at", "order_events", ["created_at"], unique=False)
    op.create_index(
        "ix_order_events_pending", "order_events", ["published_at", "created_at"], unique=False
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("order_events")
    op.drop_table("audit_logs")
    op.drop_table("refunds")
    op.drop_table("settlements")
    op.drop_table("platform_fee_config")
    op.drop_table("delivery_fee_tiers")
    op.drop_table("exchange_rates")
    op.drop_table("geofence_events")
    op.drop_table("delivery_tracking")
    op.drop_table("idempotency_keys")
    op.drop_table("payments")
    op.drop_table("order_reservations")
    op.drop_table("order_modifiers")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("modifiers")
    op.drop_table("modifier_groups")
    op.drop_table("products")
    op.drop_table("categories")
    op.drop_table("restaurant_staff")
    op.drop_table("restaurants")
    op.drop_table("user_sessions")
    op.drop_table("user_addresses")
    op.drop_table("users")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS role_enum;")
    op.execute("DROP TYPE IF EXISTS order_status_enum;")
    op.execute("DROP TYPE IF EXISTS payment_phase_enum;")
    op.execute("DROP TYPE IF EXISTS payment_method_enum;")
    op.execute("DROP TYPE IF EXISTS payment_status_enum;")
    op.execute("DROP TYPE IF EXISTS reconciliation_status_enum;")
    op.execute("DROP TYPE IF EXISTS settlement_entity_type_enum;")
    op.execute("DROP TYPE IF EXISTS settlement_status_enum;")
    op.execute("DROP TYPE IF EXISTS refund_type_enum;")
    op.execute("DROP TYPE IF EXISTS refund_reason_enum;")
    op.execute("DROP TYPE IF EXISTS refund_status_enum;")
