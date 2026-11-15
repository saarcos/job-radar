import json
import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from jobradar.adapters.sources.weworkremotely import (
    WeWorkRemotelySource,
    _first_per_guid,
)
from jobradar.domain.entities import RawJob

# Each posting of the fixture, named by the company in its title.
TERAC = "Terac"  # USA Only, two colons in the title
TESTLIO = "Testlio"  # Latin America Only, Spanish title, English text
SECURE_PRIVACY = "Secure Privacy"  # has media:content; its body says "To apply,"
WELCOMEHOME = "WelcomeHome Software"  # Anywhere in the World, but country says USA
BDF = "BDF EXPERTS"  # German, non-ASCII text, no skills
ALL_COMPANIES = [TERAC, TESTLIO, SECURE_PRIVACY, WELCOMEHOME, BDF]

PAYLOAD_KEYS = {
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
}
MEDIA_CONTENT = "{http://search.yahoo.com/mrss}content"
HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
LINK = "https://weworkremotely.com/remote-jobs/acme-backend-engineer"


@pytest.fixture
def source():
    return WeWorkRemotelySource()


@pytest.fixture
def feed(fixture_bytes):
    return fixture_bytes("wwr_sample.xml")


# The <item> of a company, exactly as the feed has it.
@pytest.fixture
def item(feed):
    by_company = {
        element.findtext("title", "").partition(":")[0]: element
        for element in ET.fromstring(feed).findall("./channel/item")
    }
    return by_company.__getitem__


@pytest.fixture
def raw(source, feed, item):
    raws = {parsed.external_id: parsed for parsed in source._parse(feed)}
    return lambda company: raws[item(company).findtext("guid")]


@pytest.fixture
def job(source, raw):
    return lambda company: source.to_job(raw(company))


def with_payload(original: RawJob, **changes: Any) -> RawJob:
    return replace(original, payload={**original.payload, **changes})


def feed_with_item(**elements: str) -> bytes:
    children = "".join(f"<{tag}>{text}</{tag}>" for tag, text in elements.items())
    return f"<rss><channel><item>{children}</item></channel></rss>".encode()


def test_parse_returns_one_raw_job_per_item(source, feed):
    assert len(ET.fromstring(feed).findall("./channel/item")) == 5

    assert len(source._parse(feed)) == 5


@pytest.mark.parametrize("company", ALL_COMPANIES)
def test_external_id_is_the_guid_as_text(company, item, raw):
    external_id = raw(company).external_id

    assert isinstance(external_id, str)
    assert external_id == item(company).findtext("guid")
    assert external_id.startswith("https://weworkremotely.com/remote-jobs/")


@pytest.mark.parametrize("company", ALL_COMPANIES)
def test_url_is_the_link(company, item, raw, job):
    assert raw(company).url == item(company).findtext("link")
    assert job(company).url == raw(company).url


@pytest.mark.parametrize("company", ALL_COMPANIES)
def test_payload_has_exactly_the_named_elements(company, item, raw):
    assert item(SECURE_PRIVACY).find(MEDIA_CONTENT) is not None

    payload = raw(company).payload

    assert set(payload) == PAYLOAD_KEYS
    assert "media:content" not in payload


@pytest.mark.parametrize("company", ALL_COMPANIES)
def test_payload_can_be_stored_as_json(company, raw):
    assert json.loads(json.dumps(raw(company).payload)) == raw(company).payload


@pytest.mark.parametrize(
    "elements",
    [
        {"title": "Acme: Backend Engineer", "link": LINK},
        {"title": "Acme: Backend Engineer", "guid": "", "link": LINK},
        {"title": "Acme: Backend Engineer", "guid": LINK},
        {"title": "Acme: Backend Engineer", "guid": LINK, "link": ""},
    ],
    ids=["no guid", "empty guid", "no link", "empty link"],
)
def test_item_without_guid_or_link_fails(source, elements):
    with pytest.raises(ValueError):
        source._parse(feed_with_item(**elements))


def test_first_per_guid_drops_repeated_postings(source, feed):
    parsed = source._parse(feed)

    assert _first_per_guid(parsed + parsed) == parsed


# A posting listed in two categories comes in both feeds.
def test_first_per_guid_keeps_the_copy_of_the_first_feed(source, feed):
    first = source._parse(feed)[0]
    second = with_payload(first, category="Back-End Programming")

    assert _first_per_guid([first, second]) == [first]


def test_company_and_title_split(job):
    posting = job(BDF)

    assert posting.company == "BDF EXPERTS"
    assert posting.title == "SAP Berater FI/CO (M/W/D)"


def test_title_with_two_colons_splits_on_the_first(job):
    posting = job(TERAC)

    assert posting.company == "Terac"
    assert posting.title == (
        "Offensive Cybersecurity Engineers: Build RL Environments for AI Evaluation"
    )


@pytest.mark.parametrize(
    "raw_title",
    ["Senior Backend Engineer", ": Senior Backend Engineer", "Acme:", "", None],
)
def test_title_without_company_fails(source, raw, raw_title):
    with pytest.raises(ValueError, match="Company: Title"):
        source.to_job(with_payload(raw(TERAC), title=raw_title))


def test_title_error_shows_the_title(source, raw):
    with pytest.raises(ValueError, match="Senior Backend Engineer"):
        source.to_job(with_payload(raw(TERAC), title="Senior Backend Engineer"))


@pytest.mark.parametrize("company", ALL_COMPANIES)
def test_description_has_no_html(company, job):
    description_md = job(company).description_md

    assert description_md is not None
    assert not HTML_TAG.search(description_md)


@pytest.mark.parametrize("company", ALL_COMPANIES)
def test_description_drops_the_trailer(company, item, raw, job):
    assert "To apply:" in item(company).findtext("description", "")

    description_md = job(company).description_md

    assert description_md is not None
    assert "To apply:" not in description_md
    assert raw(company).url not in description_md


def test_body_instructions_to_apply_survive(job):
    assert "To apply, submit your CV" in (job(SECURE_PRIVACY).description_md or "")


def test_description_without_trailer_is_kept(source, raw):
    changed = with_payload(raw(TERAC), description="<p>Hello</p>")

    assert source.to_job(changed).description_md == "Hello"


@pytest.mark.parametrize("description", ["", None])
def test_missing_description_is_none(source, raw, description):
    changed = with_payload(raw(TERAC), description=description)

    assert source.to_job(changed).description_md is None


def test_non_ascii_survives(raw, job):
    description_md = job(BDF).description_md or ""

    assert "Düsseldorf" in description_md
    assert "Ã" not in description_md
    assert "Perú" in job(TESTLIO).title
    assert "🇺🇸" in raw(WELCOMEHOME).payload["country"]


# Raw on purpose: mapping WWR's vocabulary onto common regions is B8's job.
@pytest.mark.parametrize(
    ("company", "expected"),
    [
        (TERAC, "USA Only"),
        (TESTLIO, "Latin America Only"),
        # Its country says USA; region_hint is region alone.
        (WELCOMEHOME, "Anywhere in the World"),
    ],
)
def test_region_hint_is_raw(company, expected, job):
    assert job(company).region_hint == expected


@pytest.mark.parametrize("region", ["", None])
def test_empty_region_is_none(source, raw, region):
    changed = with_payload(raw(TERAC), region=region)

    assert source.to_job(changed).region_hint is None


def test_expires_at_is_timezone_aware(job):
    expires_at = job(BDF).expires_at

    assert isinstance(expires_at, datetime)
    assert expires_at.tzinfo is not None
    assert expires_at == datetime(2026, 11, 18, 10, 1, 21, tzinfo=UTC)


# pubDate as is, never expires_at minus 30 days: that would be a derived value
# stored as if the source said it (IMPLEMENTATION.md §0.20).
def test_posted_at_is_the_pub_date_as_is(item, job):
    assert item(BDF).findtext("pubDate") == "Mon, 19 Oct 2026 10:01:21 +0000"

    assert job(BDF).posted_at == datetime(2026, 10, 19, 10, 1, 21, tzinfo=UTC)


# "-0000" is UTC with no local zone known (RFC 5322 §3.3), and
# parsedate_to_datetime returns it without tzinfo.
def test_date_without_timezone_is_utc(source, raw):
    changed = with_payload(raw(BDF), pubDate="Mon, 19 Oct 2026 10:01:21 -0000")

    posted_at = source.to_job(changed).posted_at

    assert posted_at == datetime(2026, 10, 19, 10, 1, 21, tzinfo=UTC)
    assert posted_at is not None and posted_at.tzinfo == UTC


@pytest.mark.parametrize(
    ("element", "field"), [("pubDate", "posted_at"), ("expires_at", "expires_at")]
)
@pytest.mark.parametrize("value", ["", None])
def test_missing_dates_are_none(source, raw, element, field, value):
    changed = with_payload(raw(BDF), **{element: value})

    assert getattr(source.to_job(changed), field) is None


@pytest.mark.parametrize("element", ["pubDate", "expires_at"])
def test_malformed_date_fails(source, raw, element):
    with pytest.raises(ValueError):
        source.to_job(with_payload(raw(BDF), **{element: "yesterday"}))


@pytest.mark.parametrize(("company", "expected"), [(BDF, None), (TERAC, "en")])
def test_language(company, expected, job):
    assert job(company).language == expected


@pytest.mark.parametrize("company", ALL_COMPANIES)
def test_fields_the_source_does_not_give_are_none(company, job):
    posting = job(company)

    assert posting.salary_raw is None
    assert posting.remote_modality is None
    assert posting.seniority_hint is None
    assert posting.applications_count is None


def test_source_slug(source, job):
    assert source.slug == "weworkremotely"
    assert job(TERAC).source_slug == "weworkremotely"
