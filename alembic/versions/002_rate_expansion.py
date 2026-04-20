"""Rate expansion — utility registry, zipcode mapping, URDB rates, ingestion audit log.

Adds utility_name/eia_id/rate_avg/tier columns to users table.
Creates utility, zipcode_utility, urdb_rate, rate_ingestion_run tables.

Revision ID: 002
Create Date: 2026-04-19
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    existing_tables = insp.get_table_names()
    existing_user_cols = {c["name"] for c in insp.get_columns("users")}

    # New columns on users
    if "utility_name" not in existing_user_cols:
        op.add_column("users", sa.Column("utility_name", sa.String(length=256), nullable=True))
    if "utility_eia_id" not in existing_user_cols:
        op.add_column("users", sa.Column("utility_eia_id", sa.Integer(), nullable=True))
    if "utility_rate_avg" not in existing_user_cols:
        op.add_column("users", sa.Column("utility_rate_avg", sa.Float(), nullable=True))
    if "utility_tier" not in existing_user_cols:
        op.add_column("users", sa.Column("utility_tier", sa.Integer(), nullable=True))

    if "utility" not in existing_tables:
        op.create_table(
            "utility",
            sa.Column("eia_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=256), nullable=False),
            sa.Column("state", sa.String(length=2), nullable=True),
            sa.Column("ownership_type", sa.String(length=64), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("eia_id"),
        )

    if "zipcode_utility" not in existing_tables:
        op.create_table(
            "zipcode_utility",
            sa.Column("zipcode", sa.String(length=10), nullable=False),
            sa.Column("eia_id", sa.Integer(), nullable=False),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("residential_rate_avg", sa.Float(), nullable=True),
            sa.Column("source_year", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["eia_id"], ["utility.eia_id"]),
            sa.PrimaryKeyConstraint("zipcode", "eia_id"),
        )
        op.create_index("ix_zipcode_utility_zipcode", "zipcode_utility", ["zipcode"])

    if "zip_centroid" not in existing_tables:
        op.create_table(
            "zip_centroid",
            sa.Column("zipcode", sa.String(length=10), nullable=False),
            sa.Column("lat", sa.Float(), nullable=False),
            sa.Column("lng", sa.Float(), nullable=False),
            sa.PrimaryKeyConstraint("zipcode"),
        )

    if "urdb_rate" not in existing_tables:
        op.create_table(
            "urdb_rate",
            sa.Column("urdb_label", sa.String(length=64), nullable=False),
            sa.Column("eia_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(length=256), nullable=True),
            sa.Column("sector", sa.String(length=64), nullable=True),
            sa.Column("effective_date", sa.String(length=32), nullable=True),
            sa.Column("end_date", sa.String(length=32), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("raw_json", sa.JSON(), nullable=True),
            sa.Column("urdb_last_modified", sa.DateTime(), nullable=True),
            sa.Column(
                "ingested_at",
                sa.DateTime(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["eia_id"], ["utility.eia_id"]),
            sa.PrimaryKeyConstraint("urdb_label"),
        )

    if "rate_ingestion_run" not in existing_tables:
        op.create_table(
            "rate_ingestion_run",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(length=64), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column(
                "records_processed", sa.Integer(), nullable=False, server_default=sa.text("0")
            ),
            sa.Column(
                "records_inserted", sa.Integer(), nullable=False, server_default=sa.text("0")
            ),
            sa.Column(
                "records_updated", sa.Integer(), nullable=False, server_default=sa.text("0")
            ),
            sa.Column(
                "records_failed", sa.Integer(), nullable=False, server_default=sa.text("0")
            ),
            sa.Column("source_version", sa.String(length=128), nullable=True),
            sa.Column("error_log", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    op.drop_table("rate_ingestion_run")
    op.drop_table("urdb_rate")
    op.drop_index("ix_zipcode_utility_zipcode", table_name="zipcode_utility")
    op.drop_table("zipcode_utility")
    op.drop_table("zip_centroid")
    op.drop_table("utility")
    op.drop_column("users", "utility_tier")
    op.drop_column("users", "utility_rate_avg")
    op.drop_column("users", "utility_eia_id")
    op.drop_column("users", "utility_name")
