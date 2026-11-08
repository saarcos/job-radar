import pytest

from jobradar.domain import normalize


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Lemon.io", "lemon"),
        ("Vetclaims.ai", "vetclaims"),
        ("Credit Wellness, LLC", "credit wellness"),
        ("Acme S.A.S.", "acme"),
        ("Acme Cía Ltda", "acme"),
        ("Acme Inc.", "acme"),
        ("ACME", "acme"),
        ("TELUS Digital", "telus digital"),
        # Compound endings are checked before ".co": no "empresacom" leftover.
        ("Empresa.com.co", "empresa"),
        ("Empresa.com.ar", "empresa"),
        ("Empresa.cl", "empresa"),
        # A suffix that is the whole name is kept, or it would become "".
        ("Co", "co"),
        # A non-Latin name is kept as written instead of folding to "".
        ("株式会社テスト", "株式会社テスト"),
    ],
)
def test_company(raw, expected):
    assert normalize.company(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Sr. Backend Engineer (Remote) 🚀", "senior backend engineer"),
        ("Backend Engineer f/m/d", "backend engineer"),
        ("Backend Engineer m/w/d", "backend engineer"),
        ("Backend Engineer (m/w/d)", "backend engineer"),
        ("Software Engineer (Remote, LATAM)", "software engineer"),
        ("Desarrollador(a) Backend", "desarrollador backend"),
        # Bracketed text that is not decoration is kept, without the brackets.
        ("Software Engineer (Full Stack)", "software engineer full stack"),
        ("Engineer (Remote", "engineer remote"),
        ("Tech Lead Full-Stack Rails Engineer", "tech lead full stack rails engineer"),
        ("content reviewer - english us", "content reviewer english us"),
        # The f/m/d pattern must not eat a slash between words.
        (
            "senior independent ai engineer / architect",
            "senior independent ai engineer / architect",
        ),
    ],
)
def test_title(raw, expected):
    assert normalize.title(raw) == expected


def test_canonical_key_shape():
    assert (
        normalize.canonical_key("Lemon.io", "Sr. Golang Developer")
        == "lemon::senior golang developer"
    )


# The behavior the key exists for: two sources writing the same opening
# differently end up with one key.
def test_canonical_key_matches_across_sources():
    a = normalize.canonical_key("Lemon.io", "Senior Golang Developer")
    b = normalize.canonical_key("Lemon", "Sr. Golang Developer (Remote)")
    assert a == b


def test_canonical_key_keeps_seniority_apart():
    a = normalize.canonical_key("Acme", "Senior Backend Engineer")
    b = normalize.canonical_key("Acme", "Junior Backend Engineer")
    assert a != b


# Two real, different openings listed together on We Work Remotely.
def test_canonical_key_keeps_bracketed_specialties_apart():
    a = normalize.canonical_key(
        "Jumio", "Machine Learning Engineer - IV (Computer Vision)"
    )
    b = normalize.canonical_key("Jumio", "Machine Learning Engineer - IV (Biometrics)")
    assert a != b


@pytest.mark.xfail(
    strict=True,
    reason="decoration is only removed inside brackets; '- Remote' stays in the title",
)
def test_title_decoration_outside_brackets():
    assert normalize.title("Senior Backend Engineer - Remote") == normalize.title(
        "Senior Backend Engineer (Remote)"
    )
