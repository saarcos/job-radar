import pytest

from domain import normalize


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Acme Inc.", "acme"),
        ("ACME", "acme"),
        ("Credit Wellness, LLC", "credit wellness"),
        ("lemon.io", "lemon"),
        ("TELUS Digital", "telus digital"),
    ],
)
def test_company(raw, expected):
    assert normalize.company(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Sr. Backend Engineer (Remote) 🚀", "senior backend engineer"),
        ("Backend Engineer f/m/d", "backend engineer"),
        ("Tech Lead Full-Stack Rails Engineer", "tech lead full stack rails engineer"),
        ("content reviewer - english us", "content reviewer english us"),
        (
            "senior independent ai engineer / architect",
            "senior independent ai engineer / architect",
        ),
    ],
)
def test_title(raw, expected):
    assert normalize.title(raw) == expected


@pytest.mark.xfail(reason="a.team loses the dot and remains as 'ateam'")
def test_company_dot_in_name():
    assert normalize.company("a.team") == "a team"
