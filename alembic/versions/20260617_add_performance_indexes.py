"""Add performance indexes for properties, bookings, and reviews tables.

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-06-17 10:55:00.000000
"""

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Properties table — most queried columns
    op.create_index("idx_properties_city", "properties", ["city"])
    op.create_index("idx_properties_type", "properties", ["property_type"])
    op.create_index("idx_properties_price", "properties", ["price_per_night"])
    op.create_index("idx_properties_available", "properties", ["is_available"])
    op.create_index("idx_properties_host", "properties", ["host_id"])

    # Bookings table — availability checks and user queries
    op.create_index("idx_bookings_property_status", "bookings", ["property_id", "status"])
    op.create_index("idx_bookings_guest", "bookings", ["guest_id"])

    # Reviews table — joined on every property detail query
    op.create_index("idx_reviews_property", "reviews", ["property_id"])


def downgrade() -> None:
    op.drop_index("idx_reviews_property", table_name="reviews")
    op.drop_index("idx_bookings_guest", table_name="bookings")
    op.drop_index("idx_bookings_property_status", table_name="bookings")
    op.drop_index("idx_properties_host", table_name="properties")
    op.drop_index("idx_properties_available", table_name="properties")
    op.drop_index("idx_properties_price", table_name="properties")
    op.drop_index("idx_properties_type", table_name="properties")
    op.drop_index("idx_properties_city", table_name="properties")
