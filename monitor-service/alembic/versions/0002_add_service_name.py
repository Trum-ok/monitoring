from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_service_name"
down_revision: str | Sequence[str] | None = "0001_create_errors_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "errors",
        sa.Column("service_name", sa.String(length=255), nullable=False, server_default="unknown"),
    )
    op.create_index("idx_service_name", "errors", ["service_name"])


def downgrade() -> None:
    op.drop_index("idx_service_name", table_name="errors")
    op.drop_column("errors", "service_name")
