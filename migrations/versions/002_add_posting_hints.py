"""add posting hints

Three nullable columns on job_postings with what only some sources publish:
remote_modality, seniority_hint and applications_count. NULL means the source
does not say, so a posting seen only on a source without them stays NULL.

Revision ID: 002
Revises: 001
Create Date: 2026-11-08 14:19:32.581192

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | Sequence[str] | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "job_postings", sa.Column("remote_modality", sa.Text(), nullable=True)
    )
    op.add_column("job_postings", sa.Column("seniority_hint", sa.Text(), nullable=True))
    op.add_column(
        "job_postings", sa.Column("applications_count", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("job_postings", "applications_count")
    op.drop_column("job_postings", "seniority_hint")
    op.drop_column("job_postings", "remote_modality")
