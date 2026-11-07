from sqlalchemy import Identity, text
from sqlalchemy.orm import Mapped, mapped_column

from jobradar.adapters.persistence.models.base import Base


class SourceRow(Base):
    """A job board that the sync fetches postings from.

    The migration seeds the three of them; the application needs these rows
    to work, so they are not optional data.

    Attributes:
        id: Surrogate key.
        slug: Stable identifier used by the code and by search profiles:
            'getonboard', 'weworkremotely' or 'remotive'.
        name: Display name.
        enabled: Whether the sync fetches from this source.
        priority: Merge order when several sources list the same posting in
            one sync: the lowest wins, and its data fills the new posting.
            Unique, so the winner never depends on the order of a list.
    """

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    slug: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    enabled: Mapped[bool] = mapped_column(server_default=text("true"))
    priority: Mapped[int] = mapped_column(unique=True)
