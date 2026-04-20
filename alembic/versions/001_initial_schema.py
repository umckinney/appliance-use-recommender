"""Initial schema — users and appliances tables.

Revision ID: 001
Create Date: 2026-04-19
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = inspect(op.get_bind()).get_table_names()

    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("api_key", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=True),
            sa.Column("email", sa.String(length=256), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column("address", sa.Text(), nullable=True),
            sa.Column("lat", sa.Float(), nullable=True),
            sa.Column("lon", sa.Float(), nullable=True),
            sa.Column("timezone", sa.String(length=64), nullable=True),
            sa.Column("utility_id", sa.String(length=64), nullable=True),
            sa.Column("rate_plan", sa.String(length=64), nullable=True),
            sa.Column("net_metering", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("has_solar", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("solar_capacity_kw", sa.Float(), nullable=True),
            sa.Column("solar_tilt_deg", sa.Float(), nullable=True),
            sa.Column("solar_azimuth_deg", sa.Float(), nullable=True),
            sa.Column("solaredge_site_id", sa.String(length=64), nullable=True),
            sa.Column("solaredge_api_key", sa.String(length=128), nullable=True),
            sa.Column(
                "optimization_weight",
                sa.Float(),
                nullable=False,
                server_default=sa.text("0.5"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("api_key"),
            sa.UniqueConstraint("email"),
        )
        op.create_index("ix_users_api_key", "users", ["api_key"], unique=True)

    if "appliances" not in existing:
        op.create_table(
            "appliances",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("slug", sa.String(length=64), nullable=False),
            sa.Column("cycle_kwh", sa.Float(), nullable=False),
            sa.Column("cycle_minutes", sa.Integer(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    op.drop_table("appliances")
    op.drop_index("ix_users_api_key", table_name="users")
    op.drop_table("users")
