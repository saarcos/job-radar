from sqlalchemy import Identity, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from jobradar.adapters.persistence.models.base import Base


class SearchProfileRow(Base):
    """A saved set of filters for the posting list.

    The filters run when postings are read, and nothing they decide is
    stored, so editing a profile takes effect on the next query.

    Attributes:
        id: Surrogate key.
        name: Display name.
        include_keywords: A posting must mention at least one of them in its
            title or description.
        exclude_keywords: A posting that mentions any of them in its title or
            description is left out.
        exclude_seniority: A posting whose title mentions any of them is left
            out.
        languages: Accepted posting languages ('es', 'en'); None accepts any.
        max_age_days: Postings published longer ago than this are left out.
        source_slugs: Only postings from these sources, by sources.slug; None
            means every source. Plain text: an array cannot have a foreign key.
        is_default: Whether this is the profile used when none is chosen.
    """

    __tablename__ = "search_profiles"
    __table_args__ = (
        # At most one default profile. Partial: rows with is_default = false
        # are not in the index, so any number of them can exist.
        Index(None, "is_default", unique=True, postgresql_where=text("is_default")),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str]
    include_keywords: Mapped[list[str]]
    exclude_keywords: Mapped[list[str]]
    exclude_seniority: Mapped[list[str]]
    languages: Mapped[list[str] | None]
    max_age_days: Mapped[int] = mapped_column(server_default=text("30"))
    source_slugs: Mapped[list[str] | None]
    is_default: Mapped[bool] = mapped_column(server_default=text("false"))
