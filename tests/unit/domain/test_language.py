import pytest

from jobradar.domain.html_text import to_markdown
from jobradar.domain.language import detect


# Get on Board splits a posting across several HTML fields; `description` alone
# is enough to tell the language.
@pytest.mark.parametrize(
    ("posting_id", "expected"),
    [
        (
            "semi-senior-full-stack-java-developer-qa-ai-bilingue-23people-santiago",
            "es",
        ),
        ("junior-integrations-developer-inversiones-vertice-limitada-santiago", "es"),
        # Get on Board also lists postings written in English.
        ("senior-full-stack-engineer-improving-remote", "en"),
    ],
)
def test_getonboard_posting(posting_id, expected, load_fixture):
    jobs = load_fixture("getonboard_sample.json")["data"]
    posting = next(job["attributes"] for job in jobs if job["id"] == posting_id)

    assert detect(posting["title"], to_markdown(posting["description"])) == expected


# Every posting of the WWR fixture, by company: a posting added to the fixture
# without a case here fails with a KeyError.
WWR_LANGUAGE = {
    "Terac": "en",
    "Testlio": "en",  # Spanish title, English text
    "Secure Privacy": "en",
    "WelcomeHome Software": "en",
    "BDF EXPERTS": None,  # German
}


def test_wwr_posting_language(wwr_item):
    title, description = wwr_item
    company = title.partition(":")[0]

    assert detect(title, to_markdown(description)) == WWR_LANGUAGE[company]


def test_empty_text_is_none():
    assert detect("", None) is None


def test_tie_is_none():
    assert detect("Backend de Python", "Remote, the best") is None


def test_stopwords_at_exactly_the_minimum_share_decide():
    # 1 stopword in 20 words: 5%.
    assert detect("the", " ".join(["lorem"] * 19)) == "en"


def test_stopwords_below_the_minimum_share_are_none():
    # 1 stopword in 21 words: under 5%. A language outside the lists still
    # shares a few of their words: German writes "in" too.
    assert detect("the", " ".join(["lorem"] * 20)) is None


def test_ignores_case():
    assert detect("DESARROLLADOR DE SOFTWARE", None) == "es"


# With "a" as an English stopword this would be 4 to 1 for English.
def test_spanish_a_does_not_count_as_english():
    assert (
        detect("Ingeniero/a", "Trabajo a distancia, a tiempo completo y a demanda")
        == "es"
    )


# No stopwords at all: the honest answer is "unknown", not a guess.
def test_spanish_title_without_stopwords_is_none():
    assert detect("Desarrollador/a Full-Stack", None) is None
