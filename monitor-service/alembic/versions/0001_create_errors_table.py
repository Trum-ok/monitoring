"""create errors table

Revision ID: 0001_create_errors_table
Revises: 
Create Date: 2026-05-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_create_errors_table"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "errors",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("signature_hash", sa.String(length=255), nullable=False),
        sa.Column("exc_type", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("traceback_preview", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_notified_at", sa.DateTime(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("signature_hash", name="uq_errors_signature_hash"),
    )
    op.create_index("idx_signature_hash", "errors", ["signature_hash"])
    op.create_index("idx_exc_type", "errors", ["exc_type"])


def downgrade() -> None:
    op.drop_index("idx_exc_type", table_name="errors")
    op.drop_index("idx_signature_hash", table_name="errors")
    op.drop_table("errors")
