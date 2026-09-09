from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_error_events_and_status"
down_revision: str | Sequence[str] | None = "0002_add_service_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("errors", sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    op.add_column(
        "errors",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
    )
    op.add_column("errors", sa.Column("status_changed_at", sa.DateTime(), nullable=True))

    op.execute(
        "UPDATE errors SET last_seen_at = COALESCE(last_notified_at, first_seen_at) "
        "WHERE last_seen_at IS NULL"
    )

    op.create_index("idx_status", "errors", ["status"])
    op.create_index("idx_last_seen_at", "errors", ["last_seen_at"])

    op.create_table(
        "error_events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("signature_hash", sa.String(length=255), nullable=False),
        sa.Column("service_name", sa.String(length=255), nullable=False),
        sa.Column("exc_type", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("traceback_preview", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "idx_error_events_signature_occurred",
        "error_events",
        ["signature_hash", "occurred_at"],
    )
    op.create_index("idx_error_events_occurred_at", "error_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("idx_error_events_occurred_at", table_name="error_events")
    op.drop_index("idx_error_events_signature_occurred", table_name="error_events")
    op.drop_table("error_events")

    op.drop_index("idx_last_seen_at", table_name="errors")
    op.drop_index("idx_status", table_name="errors")
    op.drop_column("errors", "status_changed_at")
    op.drop_column("errors", "status")
    op.drop_column("errors", "last_seen_at")
