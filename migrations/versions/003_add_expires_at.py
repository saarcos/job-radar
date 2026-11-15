"""add expires_at

expires_at on both job_postings and job_posting_sources, and Remotive turned
off. The two columns are not the same thing: on a sighting it is until when
that listing runs at its source, which vetoes closing the posting by absence;
on a posting it is the first value any source declares, in priority order.
NULL means no source says.

Revision ID: 003
Revises: 002
Create Date: 2026-11-14 20:27:34.287874

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | Sequence[str] | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "job_posting_sources",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "job_postings",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Evaluated on 2026-11-14 and left out of v1 (IMPLEMENTATION.md §1): 16
    # postings, a 24-hour delay and about 4 requests a day. The row stays, so
    # leaving it out reads as a decision and not as something forgotten.
    op.execute("UPDATE sources SET enabled = false WHERE slug = 'remotive'")


def downgrade() -> None:
    """Downgrade schema."""
    # Back to what 001 seeded.
    op.execute("UPDATE sources SET enabled = true WHERE slug = 'remotive'")
    op.drop_column("job_postings", "expires_at")
    op.drop_column("job_posting_sources", "expires_at")
