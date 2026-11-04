import re
import unicodedata

# Legal-form words dropped from the end of a company name: "Acme S.A.S." -> "acme".
COMPANY_SUFFIXES = frozenset(
    {
        "inc", "llc", "ltd", "limited", "gmbh", "co", "corp", "sa", "srl",
        "sas", "ltda", "cia", "spa", "bv", "ag", "oy", "ab",
    }
)  # fmt: skip

# Domain endings dropped from a name written as a website: "Lemon.io" -> "lemon".
# Only the first match is removed, so compound endings must come first:
# ".com.co" would otherwise match ".co" and leave "empresacom".
COMPANY_DOMAINS = (
    ".com.ar", ".com.br", ".com.co", ".com.mx", ".co.uk",
    ".com", ".io", ".ai", ".net", ".org", ".co",
    ".cl", ".es", ".mx", ".ar", ".pe", ".uy",
)  # fmt: skip

# Seniority is normalized, never removed: a senior and a junior opening at the
# same company must keep different keys.
SENIORITY_ALIASES = {"sr": "senior", "jr": "junior", "snr": "senior"}

# Words that only decorate a title. Bracketed text is removed when every word
# in it is one of these ("(Remote, LATAM)"), and kept otherwise
# ("(Computer Vision)"): dropping real content would merge two openings.
TITLE_DECORATION = frozenset(
    {
        "remote", "remoto", "fully", "100%", "anywhere", "worldwide", "global",
        "latam", "emea", "apac", "americas", "europe", "eu", "us", "usa", "uk",
        "only", "contract", "contractor", "freelance", "full", "part", "time",
        "fulltime", "hybrid", "hibrido",
        # Spanish gender markers: "Desarrollador(a)".
        "a", "o",
    }
)  # fmt: skip

# Gender/diversity markers such as "f/m/d", "m/w/d" or "m/f/x", with or without
# brackets. The lookarounds keep "engineer / architect" intact.
_GENDER_MARKER = re.compile(r"(?<!\w)[fmwxd](?:\s*/\s*[fmwxd])+(?!\w)")
_BRACKETED = re.compile(r"[(\[{](.*?)[)\]}]")
_BRACKET_CHAR = re.compile(r"[()\[\]{}]")
_BRACKET_WORD = re.compile(r"[a-z0-9%]+")
_DOT_OR_COMMA = re.compile(r"[.,]")
_DASH = re.compile(r"[-–—]")


# Accents removed, lowercased, trimmed. A name in a non-Latin script folds to
# "", and every such name would then share one key, so it is kept as written.
def _basic(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    folded = folded.lower().strip()
    return folded or unicodedata.normalize("NFKC", text).casefold().strip()


def _drop_decoration(match: re.Match[str]) -> str:
    content = match.group(1)
    words = _BRACKET_WORD.findall(content)
    # An empty pair, e.g. what "(m/w/d)" leaves behind, counts as decoration.
    if all(word in TITLE_DECORATION for word in words):
        return " "
    return f" {content} "


def company(raw: str) -> str:
    text = _basic(raw)
    for domain in COMPANY_DOMAINS:
        if text.endswith(domain):
            text = text.removesuffix(domain)
            break
    text = _DOT_OR_COMMA.sub("", text)

    words = text.split()
    # A suffix that is the whole name is kept: company("Co") is "co", not "".
    while len(words) > 1 and words[-1] in COMPANY_SUFFIXES:
        words.pop()

    return " ".join(words)


def title(raw: str) -> str:
    text = _basic(raw)
    text = _GENDER_MARKER.sub("", text)
    text = _BRACKETED.sub(_drop_decoration, text)
    # Unbalanced leftovers, as in "Engineer (Remote".
    text = _BRACKET_CHAR.sub(" ", text)
    text = _DOT_OR_COMMA.sub("", text)
    text = _DASH.sub(" ", text)
    words = [SENIORITY_ALIASES.get(word, word) for word in text.split()]
    return " ".join(words)


# "::" separates the two parts because it does not occur in posting text, unlike "-".
def canonical_key(company_raw: str, title_raw: str) -> str:
    return f"{company(company_raw)}::{title(title_raw)}"
