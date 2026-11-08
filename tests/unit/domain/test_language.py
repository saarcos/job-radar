import pytest

from jobradar.domain.html_text import to_markdown
from jobradar.domain.language import detect


# Get on Board splits a posting across several HTML fields; `description` alone
# is enough to tell the language.
@pytest.mark.parametrize(
    ("posting_id", "expected"),
    [
        ("desarrollador-a-full-stack-financia-capital-santiago", "es"),
        ("especialista-integracion-pleno-bci-santiago-f68d", "es"),
        # Get on Board also lists postings written in English.
        ("senior-software-engineer-vetclaims-ai-remote", "en"),
    ],
)
def test_getonboard_posting(posting_id, expected, load_fixture):
    jobs = load_fixture("getonboard_sample.json")["data"]
    posting = next(job["attributes"] for job in jobs if job["id"] == posting_id)

    assert detect(posting["title"], to_markdown(posting["description"])) == expected


def test_wwr_posting_is_english(wwr_item):
    title, description = wwr_item

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
