import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from jobradar.domain.html_text import to_markdown
from jobradar.domain.language import detect

FIXTURES = Path(__file__).parent.parent / "fixtures"

# Get on Board splits a posting across several HTML fields; `description` alone
# is enough to tell the language.
GOB_POSTINGS = {
    job["id"]: job["attributes"]
    for job in json.loads(
        (FIXTURES / "getonboard_sample.json").read_text(encoding="utf-8")
    )["data"]
}
WWR_ITEMS = [
    (item.findtext("title", ""), item.findtext("description", ""))
    for item in ET.parse(FIXTURES / "wwr_sample.xml").getroot().iter("item")
]


@pytest.mark.parametrize(
    ("posting_id", "expected"),
    [
        ("desarrollador-a-full-stack-financia-capital-santiago", "es"),
        ("especialista-integracion-pleno-bci-santiago-f68d", "es"),
        # Get on Board also lists postings written in English.
        ("senior-software-engineer-vetclaims-ai-remote", "en"),
    ],
)
def test_getonboard_posting(posting_id, expected):
    posting = GOB_POSTINGS[posting_id]

    assert detect(posting["title"], to_markdown(posting["description"])) == expected


@pytest.mark.parametrize(
    ("title", "description"), WWR_ITEMS, ids=[title for title, _ in WWR_ITEMS]
)
def test_wwr_posting_is_english(title, description):
    assert detect(title, to_markdown(description)) == "en"


def test_empty_text_is_english():
    assert detect("", None) == "en"


def test_tie_is_english():
    assert detect("Backend de Python", "Remote, the best") == "en"


def test_ignores_case():
    assert detect("DESARROLLADOR DE SOFTWARE", None) == "es"


# With "a" as an English stopword this would be 4 to 1 for English.
def test_spanish_a_does_not_count_as_english():
    assert (
        detect("Ingeniero/a", "Trabajo a distancia, a tiempo completo y a demanda")
        == "es"
    )


@pytest.mark.xfail(
    strict=True,
    reason="a Spanish title alone has no stopwords, and the tie falls back to 'en'",
)
def test_spanish_title_without_description():
    assert detect("Desarrollador/a Full-Stack", None) == "es"
