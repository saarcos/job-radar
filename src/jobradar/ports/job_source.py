from typing import Protocol

from jobradar.domain.entities import JobData, RawJob


class JobSource(Protocol):
    """Where job postings come from.

    Only what the sync pipeline calls. How a response is parsed is up to each
    adapter: Get on Board returns JSON, We Work Remotely an RSS feed.

    Attributes:
        slug: The source's slug, as in the sources table.
    """

    slug: str

    def fetch(self) -> list[RawJob]: ...

    def to_job(self, raw: RawJob) -> JobData: ...
