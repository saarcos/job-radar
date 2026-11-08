from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from jobradar.adapters.persistence.models.base import Base


class SyncRunRow(Base):
    """One attempt to fetch the postings of one source.

    Closing postings depends on these rows: a sighting is stale when it was
    last seen before the start of its source's latest successful run. A run
    that failed, or is still running, makes nothing stale.

    Attributes:
        id: Surrogate key.
        source_id: The source that was fetched.
        started_at: When the run started. Once the run is 'ok', sightings of
            its source last seen before this time are stale.
        finished_at: When the run ended; None while it is running.
        status: 'running', 'ok' or 'failed'.
        postings_seen: How many postings the source returned.
        error: Why the run failed; None for runs that did not fail.
    """

    __tablename__ = "sync_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'ok', 'failed')", name="status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None]
    status: Mapped[str]
    postings_seen: Mapped[int] = mapped_column(server_default=text("0"))
    error: Mapped[str | None]


# For the latest successful run of a source, looked up on every sync:
# WHERE source_id = ? AND status = 'ok' ORDER BY started_at DESC LIMIT 1.
# Declared after the class so started_at.desc() is built from the column:
# the naming convention leaves text("started_at DESC") out of the name.
Index(None, SyncRunRow.source_id, SyncRunRow.status, SyncRunRow.started_at.desc())
