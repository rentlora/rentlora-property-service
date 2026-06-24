"""create properties and reviews

Revision ID: 001_create_properties_reviews
Revises:
Create Date: 2026-05-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_create_properties_reviews"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "properties",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=300), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("country", sa.String(length=100), server_default="India"),
        sa.Column("price_per_night", sa.Numeric(10, 2), nullable=False),
        sa.Column("max_guests", sa.Integer(), nullable=False),
        sa.Column("bedrooms", sa.Integer(), server_default="1"),
        sa.Column("bathrooms", sa.Integer(), server_default="1"),
        sa.Column("property_type", sa.String(length=50), nullable=True),
        sa.Column("amenities", postgresql.JSONB(astext_type=sa.Text()), server_default="[]"),
        sa.Column("images", postgresql.JSONB(astext_type=sa.Text()), server_default="[]"),
        sa.Column("is_available", sa.Boolean(), server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()")),
        sa.CheckConstraint("property_type IN ('apartment','house','villa','studio')", name="properties_type_check"),
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), unique=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id")),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()")),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="reviews_rating_check"),
    )


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_table("properties")
