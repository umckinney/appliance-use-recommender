"""OAuth accounts, magic link tokens, and user sessions.

Revision ID: 003
Create Date: 2026-04-20
"""

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


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
    def _user_session():
        op.create_table(
            "user_session",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("user_agent", sa.String(length=256), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_user_session_user_id", "user_session", ["user_id"])
    _try("tbl_user_session", _user_session)

    def _oauth_account():
        op.create_table(
            "oauth_account",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("provider_user_id", sa.String(length=256), nullable=False),
            sa.Column("provider_email", sa.String(length=256), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_uid"),
        )
    _try("tbl_oauth_account", _oauth_account)

    def _magic_link_token():
        op.create_table(
            "magic_link_token",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )
        op.create_index(
            "ix_magic_link_token_hash", "magic_link_token", ["token_hash"], unique=True
        )
    _try("tbl_magic_link_token", _magic_link_token)


def downgrade() -> None:
    op.drop_index("ix_magic_link_token_hash", table_name="magic_link_token")
    op.drop_table("magic_link_token")
    op.drop_table("oauth_account")
    op.drop_index("ix_user_session_user_id", table_name="user_session")
    op.drop_table("user_session")
