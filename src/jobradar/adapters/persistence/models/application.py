from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Identity, func
from sqlalchemy.orm import Mapped, mapped_column

from jobradar.adapters.persistence.models.base import Base


class ApplicationRow(Base):
    """The user's application to one posting.

    A posting with an application cannot be deleted; postings are never
    deleted anyway, they are closed.

    Attributes:
        id: Surrogate key.
        job_posting_id: The posting applied to; at most one application per
            posting.
        resume_version_id: The resume that was sent, a row of resume_versions;
            None if none was recorded.
        status: 'applied', 'screening', 'interview', 'rejected', 'offer' or
            'ghosted'.
        applied_at: When the user applied.
        notes: The user's notes.
    """

    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('applied', 'screening', 'interview', 'rejected',"
            " 'offer', 'ghosted')",
            name="status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    job_posting_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("job_postings.id"), unique=True
    )
    # No foreign key yet: resume_versions is created in B11. That block adds
    # ForeignKey("resume_versions.id") here and the constraint in its
    # migration, together, or alembic check reports the difference.
    resume_version_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str]
    applied_at: Mapped[datetime] = mapped_column(server_default=func.now())
    notes: Mapped[str | None]
