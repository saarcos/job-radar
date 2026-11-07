from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, Identity, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from jobradar.adapters.persistence.models.base import Base
from jobradar.domain.language import Language


class JobPostingRow(Base):
    """One real job opening, however many sources list it.

    Sources that list the same opening share this row through canonical_key;
    each of their listings is a JobPostingSourceRow. Postings are never
    deleted: one that no source lists anymore is closed instead.

    Attributes:
        id: Surrogate key.
        canonical_key: normalize.canonical_key(company, title), one per
            opening.
        company: Company name as the source wrote it.
        title: Title as the source wrote it.
        url: Link from the source with the best priority.
        description_md: Description as markdown; None if the source gives
            none.
        region_hint: Where applicants may be, in the source's words ('Anywhere
            in the World', 'US only'); None if the source does not say.
        salary_raw: Salary as the source wrote it, not parsed; None if the
            source does not say.
        language: 'es' or 'en', detected from the title and description; None
            if it was not detected.
        posted_at: When the source published it; None if the source does not
            say.
        status: 'new', 'seen' or 'dismissed', set by the user.
        is_open: False once no source lists it anymore.
        closed_at: When it was closed; None while it is open.
        first_seen_at: When a source listed it for the first time.
        last_seen_at: When any source listed it last, shown in the UI. Closing
            never reads it: any source refreshes it, so it says nothing about
            each source. Closing reads JobPostingSourceRow.last_seen_at.
    """

    __tablename__ = "job_postings"
    __table_args__ = (
        CheckConstraint("status IN ('new', 'seen', 'dismissed')", name="status"),
        # The values of domain.language.Language. NULL passes: a CHECK only
        # rejects a row when its condition is false, and NULL IN (...) is NULL.
        CheckConstraint("language IN ('es', 'en')", name="language"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    canonical_key: Mapped[str] = mapped_column(unique=True)
    company: Mapped[str]
    title: Mapped[str]
    url: Mapped[str]
    description_md: Mapped[str | None]
    region_hint: Mapped[str | None]
    salary_raw: Mapped[str | None]
    # Language for mypy, text for Postgres: without the explicit Text, a
    # Literal annotation becomes a non-native Enum column, varchar(2).
    # mypy checks reads and attribute assignments, but not constructor
    # keywords nor the dicts given to insert().values(); there, only the
    # CHECK constraint stops a value outside Language.
    language: Mapped[Language | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(server_default="new")
    is_open: Mapped[bool] = mapped_column(server_default=text("true"))
    closed_at: Mapped[datetime | None]
    first_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())


# For the posting list: open postings, most recently published first.
# Declared after the class so posted_at.desc() is built from the column, and
# the naming convention includes posted_at in the index name.
Index(None, JobPostingRow.is_open, JobPostingRow.posted_at.desc())
