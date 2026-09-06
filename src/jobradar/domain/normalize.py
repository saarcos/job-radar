import re
import unicodedata

COMPANY_SUFFIXES = ("inc", "llc", "ltd", "gmbh", "co", "corp", "sa", "srl")
COMPANY_DOMAINS = (".com", ".io", ".ai", ".net", ".org", ".co")
SENIORITY_ALIASES = {"sr": "senior", "jr": "junior", "snr": "senior"}


def _basic(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode()
    return text.lower().strip()


def company(raw: str) -> str:
    text = _basic(raw)
    for domain in COMPANY_DOMAINS:
        if text.endswith(domain):
            text = text.removesuffix(domain)
            break
    text = re.sub(r"[.,]", "", text)

    words = text.split()

    while words and words[-1] in COMPANY_SUFFIXES:
        words.pop()

    return " ".join(words)


def title(raw: str) -> str:
    text = _basic(raw)
    # Remove gender/diversity markers such as:
    # (f/m/d), f/m/d, m/f/x
    text = re.sub(
        r"(?<!\w)[fmxd](?:\s*/\s*[fmxd])+(?!\w)",
        "",
        text,
    )
    # Remove brackets
    text = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", text)
    # Remove dots and commas
    text = re.sub(r"[.,]", "", text)
    # Replace '-' for ' '
    text = re.sub(r"[-–—]", " ", text)
    words = [SENIORITY_ALIASES.get(w, w) for w in text.split()]
    return " ".join(words)
