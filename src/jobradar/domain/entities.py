from dataclasses import dataclass
from datetime import datetime
from typing import Any

from jobradar.domain import normalize
from jobradar.domain.language import Language


@dataclass(frozen=True)
class RawJob:
    """A posting as its source returned it, before any mapping.

    Attributes:
        external_id: The source's own id, as text even if the source sends a
            number.
        url: Link to the posting on the source.
        payload: The posting itself; only JSON-serializable values, because it
            is stored as is.
    """

    external_id: str
    url: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class JobData:
    """A posting mapped to the shape every source shares.

    A field the source does not give is None, never a made-up default: an
    honest None is information, and an invented "worldwide" is a lie the LLM
    later believes.

    Attributes:
        company: Company name as the source wrote it.
        title: Title as the source wrote it.
        url: Link to the posting on the source.
        description_md: Description as markdown.
        region_hint: Where applicants may be, in the source's words.
        remote_modality: Remote policy as the source's own value.
        salary_raw: Salary as text, not parsed; no currency unless the source
            states one.
        posted_at: When the source published it, timezone-aware.
        language: Language of the posting.
        seniority_hint: Seniority as the source's own value.
        applications_count: Applicants so far; None means unknown, not zero.
        source_slug: The slug of the source, as in the sources table.
    """

    company: str
    title: str
    url: str
    description_md: str | None
    region_hint: str | None
    remote_modality: str | None
    salary_raw: str | None
    posted_at: datetime | None
    language: Language | None
    seniority_hint: str | None
    applications_count: int | None
    source_slug: str

    # Here and not in the adapters: one place computes it, so the key that
    # deduplicates postings cannot differ from one source to another.
    @property
    def canonical_key(self) -> str:
        return normalize.canonical_key(self.company, self.title)
