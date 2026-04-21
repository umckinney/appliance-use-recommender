"""Email send log table for daily/monthly volume tracking.

Revision ID: 004
Create Date: 2026-04-20
"""

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision = "004"
down_revision = "003"
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
    def _email_send_log():
        op.create_table(
            "email_send_log",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "sent_at",
                sa.DateTime(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column("recipient_email", sa.String(length=256), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_email_send_log_sent_at", "email_send_log", ["sent_at"])

    _try("tbl_email_send_log", _email_send_log)


def downgrade() -> None:
    op.drop_index("ix_email_send_log_sent_at", table_name="email_send_log")
    op.drop_table("email_send_log")
