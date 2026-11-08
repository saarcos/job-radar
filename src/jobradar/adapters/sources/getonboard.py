import html
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx2

from jobradar.domain.entities import JobData, RawJob
from jobradar.domain.html_text import to_markdown
from jobradar.domain.language import detect

logger = logging.getLogger(__name__)

_API = "https://www.getonbrd.com/api/v0"
# A JSON array in the query string. Without it, company and seniority are only
# references by id.
_EXPAND = '["company","seniority"]'
_PER_PAGE = 50
_MAX_PAGES = 10
_TIMEOUT_SECONDS = 10.0

# In reading order. All but projects come with a "<section>_headline".
_SECTIONS = ("projects", "functions", "description", "desirable", "benefits")

# The rest of the embedded company is 2-4 KB of text repeated in every posting
# of that company.
_COMPANY_FIELDS_KEPT = frozenset({"name", "web", "country", "logo"})


class GetOnBoardSource:
    slug = "getonboard"
    DEFAULT_CATEGORIES = ("programming", "sysadmin-devops-qa", "machine-learning-ai")

    def __init__(self, categories: Sequence[str] = DEFAULT_CATEGORIES) -> None:
        self.categories = categories

    def fetch(self) -> list[RawJob]:
        with httpx2.Client() as client:
            return [
                raw
                for category in self.categories
                for raw in self._fetch_category(client, category)
            ]

    def _fetch_category(self, client: httpx2.Client, category: str) -> list[RawJob]:
        raws: list[RawJob] = []
        for page in range(1, _MAX_PAGES + 1):
            response = client.get(
                f"{_API}/categories/{category}/jobs",
                params={"expand": _EXPAND, "per_page": _PER_PAGE, "page": page},
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            body = response.json()
            raws.extend(self._parse(body))
            if page >= body["meta"]["total_pages"]:
                break
        else:
            # Not an error, but the sync would read every posting left out as
            # no longer listed, and close it.
            logger.warning(
                "getonboard: %s has more than %d pages; the rest was not fetched",
                category,
                _MAX_PAGES,
            )
        return raws

    def _parse(self, payload: dict[str, Any]) -> list[RawJob]:
        return [
            RawJob(
                external_id=str(item["id"]),
                url=item["links"]["public_url"],
                payload=_without_repeated_company_text(item),
            )
            for item in payload["data"]
        ]

    def to_job(self, raw: RawJob) -> JobData:
        attributes = raw.payload["attributes"]
        # Indexed on purpose: a posting without these means the API changed,
        # and the KeyError fails the sync run, which then closes nothing. The
        # company comes from expand, never from the slug in the URL.
        company = attributes["company"]["data"]["attributes"]["name"]
        title = attributes["title"]
        description_md = _description_md(attributes)
        return JobData(
            company=company,
            title=title,
            url=raw.url,
            description_md=description_md,
            region_hint=_region_hint(attributes),
            remote_modality=attributes.get("remote_modality"),
            salary_raw=_salary_raw(attributes),
            posted_at=_posted_at(attributes),
            # Never the source's `lang`: on 2026-11-08, 27 of the 95 postings
            # declaring "en" were written in Spanish.
            language=detect(title, description_md),
            seniority_hint=_seniority_hint(attributes),
            applications_count=attributes.get("applications_count"),
            source_slug=self.slug,
        )


# A new dict at every level: the caller's response stays as it was.
def _without_repeated_company_text(item: dict[str, Any]) -> dict[str, Any]:
    attributes = item["attributes"]
    company = attributes["company"]["data"]
    kept = {
        field: value
        for field, value in company["attributes"].items()
        if field in _COMPANY_FIELDS_KEPT
    }
    return {
        **item,
        "attributes": {
            **attributes,
            "company": {"data": {**company, "attributes": kept}},
        },
    }


# Only from the posting's own fields. company.attributes.projects has the same
# name as a section, but it is the text of the company's latest posting.
def _description_md(attributes: dict[str, Any]) -> str | None:
    parts: list[str] = []
    for section in _SECTIONS:
        body = attributes.get(section) or ""
        # The text decides, not the headline: a headline can come without text,
        # and text without a headline.
        if to_markdown(body) is None:
            continue
        headline = (attributes.get(f"{section}_headline") or "").strip()
        if headline:
            parts.append(f"<h2>{html.escape(headline)}</h2>")
        parts.append(body)
    return to_markdown("".join(parts))


# Only from the posting's own fields: company.attributes.country is where the
# company is, not where it hires.
def _region_hint(attributes: dict[str, Any]) -> str | None:
    parts = list(attributes.get("countries") or [])
    zone = attributes.get("remote_zone")
    # Null in every response seen so far, so its type is unverified.
    if isinstance(zone, str) and zone:
        parts.append(zone)
    return ", ".join(parts) or None


# No currency: the API does not state one. A posting worth 2800 here says
# "$2.800.000 CLP" in its text, which fits both USD and thousands of pesos.
def _salary_raw(attributes: dict[str, Any]) -> str | None:
    bounds = (attributes.get("min_salary"), attributes.get("max_salary"))
    return "-".join(str(bound) for bound in bounds if bound is not None) or None


def _posted_at(attributes: dict[str, Any]) -> datetime | None:
    published_at = attributes.get("published_at")
    if published_at is None:
        return None
    return datetime.fromtimestamp(published_at, tz=UTC)


def _seniority_hint(attributes: dict[str, Any]) -> str | None:
    data = (attributes.get("seniority") or {}).get("data") or {}
    return (data.get("attributes") or {}).get("locale_key")
