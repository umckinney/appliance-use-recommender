"""Rate expansion — utility registry, zipcode mapping, URDB rates, ingestion audit log.

Adds utility_name/eia_id/rate_avg/tier columns to users table.
Creates utility, zipcode_utility, urdb_rate, rate_ingestion_run tables.

Revision ID: 002
Create Date: 2026-04-19
"""

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

_SP = "sp_002"  # savepoint name reused for each idempotent block


def _try(label: str, fn):
    """Run fn(); on any error rollback to savepoint and continue."""
    bind = op.get_bind()
    bind.execute(text(f"SAVEPOINT {label}"))
    try:
        fn()
        bind.execute(text(f"RELEASE SAVEPOINT {label}"))
    except Exception:
        bind.execute(text(f"ROLLBACK TO SAVEPOINT {label}"))


def upgrade() -> None:
    _try("col_utility_name", lambda: op.add_column(
        "users", sa.Column("utility_name", sa.String(length=256), nullable=True)
    ))
    _try("col_utility_eia_id", lambda: op.add_column(
        "users", sa.Column("utility_eia_id", sa.Integer(), nullable=True)
    ))
    _try("col_utility_rate_avg", lambda: op.add_column(
        "users", sa.Column("utility_rate_avg", sa.Float(), nullable=True)
    ))
    _try("col_utility_tier", lambda: op.add_column(
        "users", sa.Column("utility_tier", sa.Integer(), nullable=True)
    ))

    def _utility():
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
    _try("tbl_utility", _utility)

    def _zipcode_utility():
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
    _try("tbl_zipcode_utility", _zipcode_utility)

    def _zip_centroid():
        op.create_table(
            "zip_centroid",
            sa.Column("zipcode", sa.String(length=10), nullable=False),
            sa.Column("lat", sa.Float(), nullable=False),
            sa.Column("lng", sa.Float(), nullable=False),
            sa.PrimaryKeyConstraint("zipcode"),
        )
    _try("tbl_zip_centroid", _zip_centroid)

    def _urdb_rate():
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
    _try("tbl_urdb_rate", _urdb_rate)

    def _rate_ingestion_run():
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
    _try("tbl_rate_ingestion_run", _rate_ingestion_run)


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
