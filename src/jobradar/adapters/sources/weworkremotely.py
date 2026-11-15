import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx2

from jobradar.domain.entities import JobData, RawJob
from jobradar.domain.html_text import to_markdown
from jobradar.domain.language import detect

_FEED_URL = "https://weworkremotely.com/categories/{feed}.rss"
_TIMEOUT_SECONDS = 10.0

# The elements of an <item> kept in the payload. Naming them is what leaves the
# rest out: media:content is the company logo, and guid repeats link.
_ELEMENTS = (
    "title",
    "region",
    "country",
    "state",
    "skills",
    "category",
    "type",
    "description",
    "pubDate",
    "expires_at",
    "link",
)

# Every posting ends with this paragraph, linking to its own page: boilerplate
# of the site that repeats the posting's url. Only that exact last paragraph:
# a body can say "To apply, submit your CV..." on its own.
_TRAILER = re.compile(
    r'\s*<p><strong>To apply:</strong>\s*<a href="([^"]+)">\1</a></p>\s*\Z'
)


class WeWorkRemotelySource:
    slug = "weworkremotely"
    # The category feeds, not remote-jobs.rss: that one lists only the latest
    # 10 postings of each category.
    DEFAULT_FEEDS = (
        "remote-full-stack-programming-jobs",
        "remote-back-end-programming-jobs",
        "remote-front-end-programming-jobs",
        "remote-devops-sysadmin-jobs",
    )

    def __init__(self, feeds: Sequence[str] = DEFAULT_FEEDS) -> None:
        self.feeds = feeds

    # A feed that fails fails the whole fetch: with one feed missing, absence
    # means nothing, and the failed sync run closes nothing.
    def fetch(self) -> list[RawJob]:
        with httpx2.Client() as client:
            raws = [
                raw
                for feed in self.feeds
                for raw in self._parse(self._fetch_feed(client, feed))
            ]
        return _first_per_guid(raws)

    def _fetch_feed(self, client: httpx2.Client, feed: str) -> bytes:
        response = client.get(_FEED_URL.format(feed=feed), timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
        # Bytes, not text, so the parser reads the encoding the XML declares.
        return response.content

    def _parse(self, feed_content: bytes) -> list[RawJob]:
        root = ET.fromstring(feed_content)
        return [_raw_job(item) for item in root.findall("./channel/item")]

    def to_job(self, raw: RawJob) -> JobData:
        payload = raw.payload
        company, title = _split_title(payload["title"])
        description_md = to_markdown(_without_trailer(payload["description"]))
        return JobData(
            company=company,
            title=title,
            url=raw.url,
            description_md=description_md,
            # Raw: "Anywhere in the World", "USA Only", even "California".
            region_hint=payload["region"] or None,
            # We Work Remotely publishes none of these four.
            remote_modality=None,
            salary_raw=None,
            seniority_hint=None,
            applications_count=None,
            # pubDate is the first publication, not the date the page shows
            # after a renewal; the prefilter reads expires_at first.
            posted_at=_date(payload["pubDate"]),
            expires_at=_date(payload["expires_at"]),
            language=detect(title, description_md),
            source_slug=self.slug,
        )


# A posting listed in two categories comes in both feeds: one RawJob per guid,
# the first feed's, or the sync would store the same sighting twice.
def _first_per_guid(raws: Iterable[RawJob]) -> list[RawJob]:
    first: dict[str, RawJob] = {}
    for raw in raws:
        first.setdefault(raw.external_id, raw)
    return list(first.values())


def _raw_job(item: ET.Element) -> RawJob:
    return RawJob(
        external_id=_required_text(item, "guid"),
        url=_required_text(item, "link"),
        payload={name: item.findtext(name) for name in _ELEMENTS},
    )


def _required_text(item: ET.Element, name: str) -> str:
    text = item.findtext(name)
    if not text:
        raise ValueError(f"weworkremotely: <item> without <{name}>")
    return text


# There is no company element: the title is "Company: Title". A title that
# does not follow it most likely means the feed changed for every posting, so
# it fails the run, which then closes nothing, instead of storing postings
# without a company.
def _split_title(raw_title: str | None) -> tuple[str, str]:
    company, colon, title = (raw_title or "").partition(":")
    company, title = company.strip(), title.strip()
    if not (colon and company and title):
        raise ValueError(
            f"weworkremotely: title is not 'Company: Title': {raw_title!r}"
        )
    return company, title


def _without_trailer(description: str | None) -> str | None:
    if description is None:
        return None
    return _TRAILER.sub("", description)


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parsedate_to_datetime(value)
    # "-0000" is UTC with no local zone known (RFC 5322 §3.3), and comes back
    # naive. Stored naive, Postgres would read it in the session's time zone.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
