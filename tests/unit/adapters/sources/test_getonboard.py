import copy
import json
import re
from dataclasses import replace
from datetime import datetime
from typing import Any

import pytest

from jobradar.adapters.sources.getonboard import GetOnBoardSource
from jobradar.domain.entities import RawJob
from jobradar.domain.html_text import to_markdown

# Each posting of the fixture, named by its company.
TWENTY_THREE = "23people"  # hybrid, no declared language, with salary
IMPROVING = "Improving"  # English, remote, no salary
# Declares lang "en", but the posting is written in Spanish.
MISLABELED = "Inversiones Vertice Limitada"
ALL_COMPANIES = [TWENTY_THREE, IMPROVING, MISLABELED]

SECTIONS = ("projects", "functions", "description", "desirable", "benefits")
HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")


@pytest.fixture
def source():
    return GetOnBoardSource()


@pytest.fixture
def response(load_fixture):
    return load_fixture("getonboard_sample.json")


# The posting of a company, exactly as the API returned it.
@pytest.fixture
def item(response):
    by_company = {
        posting["attributes"]["company"]["data"]["attributes"]["name"]: posting
        for posting in response["data"]
    }
    return by_company.__getitem__


@pytest.fixture
def raw(source, response, item):
    raws = {parsed.external_id: parsed for parsed in source._parse(response)}
    return lambda company: raws[item(company)["id"]]


@pytest.fixture
def job(source, raw):
    return lambda company: source.to_job(raw(company))


def lines(raw_html: str) -> list[str]:
    """The non-blank lines of some HTML, once it is markdown."""
    markdown = to_markdown(raw_html) or ""
    return [line.strip() for line in markdown.split("\n") if line.strip()]


def with_attributes(original: RawJob, **changes: Any) -> RawJob:
    attributes = {**original.payload["attributes"], **changes}
    return replace(original, payload={**original.payload, "attributes": attributes})


def without_attributes(original: RawJob, *names: str) -> RawJob:
    attributes = {
        name: value
        for name, value in original.payload["attributes"].items()
        if name not in names
    }
    return replace(original, payload={**original.payload, "attributes": attributes})


def test_parse_returns_one_raw_job_per_posting(source, response):
    assert len(response["data"]) == 3

    assert len(source._parse(response)) == 3


def test_external_id_is_the_slug_as_text(source, response):
    raws = source._parse(response)

    assert [parsed.external_id for parsed in raws] == [
        posting["id"] for posting in response["data"]
    ]
    assert all(isinstance(parsed.external_id, str) for parsed in raws)


@pytest.mark.parametrize("company", ALL_COMPANIES)
def test_url_comes_from_links(company, item, raw):
    url = raw(company).url

    assert url == item(company)["links"]["public_url"]
    assert url.startswith("https://")


@pytest.mark.parametrize("company", ALL_COMPANIES)
def test_payload_drops_the_company_text_repeated_in_every_posting(company, item, raw):
    original = item(company)["attributes"]["company"]["data"]["attributes"]
    assert "long_description" in original  # the fixture really has it

    kept = raw(company).payload["attributes"]["company"]["data"]["attributes"]

    assert set(kept) == {"name", "web", "country", "logo"}
    assert kept["name"] == original["name"]


def test_parse_leaves_the_response_as_it_was(source, response):
    before = copy.deepcopy(response)

    source._parse(response)

    assert response == before


@pytest.mark.parametrize("company", ALL_COMPANIES)
def test_payload_can_be_stored_as_json(company, raw):
    assert json.loads(json.dumps(raw(company).payload)) == raw(company).payload


def test_language_is_detected_when_the_source_does_not_say(item, job):
    assert item(TWENTY_THREE)["attributes"]["lang"] == "lang_not_specified"

    assert job(TWENTY_THREE).language == "es"


def test_language_of_a_posting_written_in_english(item, job):
    assert item(IMPROVING)["attributes"]["lang"] == "en"

    assert job(IMPROVING).language == "en"


def test_language_ignores_what_the_source_declares(item, job):
    assert item(MISLABELED)["attributes"]["lang"] == "en"

    assert job(MISLABELED).language == "es"


def test_company_is_the_readable_name(job):
    assert job(TWENTY_THREE).company == "23people"


def test_identity_fields(item, job):
    posting = job(TWENTY_THREE)

    assert posting.title == item(TWENTY_THREE)["attributes"]["title"]
    assert posting.url == item(TWENTY_THREE)["links"]["public_url"]
    assert posting.source_slug == "getonboard"
    assert posting.canonical_key == (
        "23people::semi senior full stack java developer qa & ai bilingue"
    )


@pytest.mark.parametrize("company", ALL_COMPANIES)
def test_description_has_no_html(company, job):
    assert not HTML_TAG.search(job(company).description_md)


@pytest.mark.parametrize("company", ALL_COMPANIES)
def test_description_has_the_text_of_all_five_sections(company, item, job):
    attributes = item(company)["attributes"]
    assert all(attributes[section] for section in SECTIONS)

    description = job(company).description_md

    for section in SECTIONS:
        for line in lines(attributes[section]):
            assert line in description


def test_sections_keep_their_reading_order(item, job):
    attributes = item(TWENTY_THREE)["attributes"]
    description = job(TWENTY_THREE).description_md

    positions = [description.index(lines(attributes[s])[0]) for s in SECTIONS]

    assert positions == sorted(positions)


def test_headlines_become_markdown_headings(item, job):
    attributes = item(TWENTY_THREE)["attributes"]
    description = job(TWENTY_THREE).description_md

    for section in SECTIONS[1:]:
        assert f"## {attributes[f'{section}_headline']}" in description


def test_projects_has_no_heading_because_the_source_gives_none(item, job):
    first_line = lines(item(TWENTY_THREE)["attributes"]["projects"])[0]

    assert job(TWENTY_THREE).description_md.startswith(first_line)


def test_headline_is_escaped_before_becoming_html(source, raw):
    changed = with_attributes(raw(IMPROVING), benefits_headline="R&D <team>")

    assert "## R&D <team>" in source.to_job(changed).description_md


# On 2026-11-08, 54 sections of 464 postings came like this.
def test_headline_without_text_leaves_no_orphan_heading(source, item, raw):
    headline = item(IMPROVING)["attributes"]["benefits_headline"]
    assert headline

    changed = with_attributes(raw(IMPROVING), benefits="")

    assert f"## {headline}" not in source.to_job(changed).description_md


def test_text_without_headline_is_kept(source, item, raw):
    benefits = item(IMPROVING)["attributes"]["benefits"]

    changed = with_attributes(raw(IMPROVING), benefits_headline="")

    assert lines(benefits)[0] in source.to_job(changed).description_md


# Not 23people: for the latest posting of a company the two texts are the same.
@pytest.mark.parametrize("company", [IMPROVING, MISLABELED])
def test_description_leaves_out_the_projects_of_the_company(company, item, job):
    attributes = item(company)["attributes"]
    company_projects = attributes["company"]["data"]["attributes"]["projects"]
    assert company_projects
    assert company_projects != attributes["projects"]

    assert lines(company_projects)[0] not in job(company).description_md


@pytest.mark.parametrize("company", ALL_COMPANIES)
def test_posted_at_is_a_timezone_aware_datetime(company, item, job):
    posted_at = job(company).posted_at

    assert isinstance(posted_at, datetime)
    assert posted_at.tzinfo is not None
    assert posted_at.timestamp() == item(company)["attributes"]["published_at"]


def test_salary_is_none_without_a_salary(item, job):
    assert item(IMPROVING)["attributes"]["min_salary"] is None

    assert job(IMPROVING).salary_raw is None


def test_salary_declares_no_currency(job):
    assert job(TWENTY_THREE).salary_raw == "2800-3000"


def test_salary_with_only_one_bound(source, raw):
    changed = with_attributes(raw(IMPROVING), min_salary=None, max_salary=3000)

    assert source.to_job(changed).salary_raw == "3000"


@pytest.mark.parametrize(
    ("company", "expected"),
    [(TWENTY_THREE, "semi_senior"), (IMPROVING, "senior"), (MISLABELED, "junior")],
)
def test_seniority_hint(company, expected, job):
    assert job(company).seniority_hint == expected


@pytest.mark.parametrize(
    ("company", "expected"),
    [(TWENTY_THREE, "hybrid"), (IMPROVING, "remote_local"), (MISLABELED, "no_remote")],
)
def test_remote_modality(company, expected, job):
    assert job(company).remote_modality == expected


@pytest.mark.parametrize("company", ALL_COMPANIES)
def test_applications_count(company, item, job):
    expected = item(company)["attributes"]["applications_count"]

    assert job(company).applications_count == expected


# The company is in the US and in Spain; these say where the postings hire.
@pytest.mark.parametrize(
    ("company", "expected"), [(IMPROVING, "Remote"), (MISLABELED, "Chile")]
)
def test_region_comes_from_the_posting_not_the_company(company, expected, job):
    assert job(company).region_hint == expected


@pytest.mark.parametrize(
    ("countries", "remote_zone", "expected"),
    [
        (["Chile", "Peru"], None, "Chile, Peru"),
        (["Remote"], "LATAM", "Remote, LATAM"),
        ([], None, None),
    ],
)
def test_region_joins_countries_and_zone(source, raw, countries, remote_zone, expected):
    changed = with_attributes(
        raw(IMPROVING), countries=countries, remote_zone=remote_zone
    )

    assert source.to_job(changed).region_hint == expected


def test_fields_the_source_does_not_give_are_none(source, raw):
    changed = without_attributes(
        raw(TWENTY_THREE),
        "countries",
        "remote_zone",
        "remote_modality",
        "min_salary",
        "max_salary",
        "published_at",
        "seniority",
        "applications_count",
    )

    posting = source.to_job(changed)

    assert posting.region_hint is None
    assert posting.remote_modality is None
    assert posting.salary_raw is None
    assert posting.posted_at is None
    assert posting.seniority_hint is None
    assert posting.applications_count is None


@pytest.mark.parametrize("field", ["title", "company"])
def test_missing_identity_field_fails_instead_of_inventing_one(source, raw, field):
    with pytest.raises(KeyError):
        source.to_job(without_attributes(raw(TWENTY_THREE), field))
