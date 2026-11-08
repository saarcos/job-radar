from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Identity,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from jobradar.adapters.persistence.models.base import Base


class JobPostingSourceRow(Base):
    """One source listing one posting: a sighting.

    Each sighting keeps its own external id, link and raw payload, so it is
    known where else a posting was seen and what each source said, and
    job_postings can be rebuilt without calling any source again.

    Attributes:
        id: Surrogate key.
        job_posting_id: The posting this is a listing of. Deleting the posting
            deletes its sightings.
        source_id: The source that lists it.
        external_id: The posting's id at the source. Text for every source,
            including those that send integers.
        url: Link to the posting at this source.
        payload_json: What the source returned for this posting, not
            interpreted.
        content_hash: Hash of the payload, to notice when the source changes
            the posting.
        first_seen_at: When this source listed it for the first time.
        last_seen_at: When this source listed it last. Closing postings reads
            this column, never JobPostingRow.last_seen_at: a sighting is stale
            when its source ran successfully afterwards and did not list it.
    """

    __tablename__ = "job_posting_sources"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id"),
        # For closing: the NOT EXISTS over the sightings of a posting, and the
        # ON DELETE CASCADE. Postgres does not index foreign keys by itself.
        Index(None, "job_posting_id"),
        # For closing: the sightings of one source last seen before a cutoff.
        Index(None, "source_id", "last_seen_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    # BigInteger is explicit: the type comes from the annotation (int ->
    # integer), not from the referenced column, which is a bigint.
    job_posting_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("job_postings.id", ondelete="CASCADE")
    )
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    external_id: Mapped[str]
    url: Mapped[str]
    payload_json: Mapped[dict[str, Any]]
    content_hash: Mapped[str]
    first_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
