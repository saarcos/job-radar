import re
from typing import Literal

Language = Literal["es", "en"]

# Frequent words of each language that the other one does not use. English has
# "you" where "a" would be expected: "a" is also a Spanish preposition.
SPANISH_STOPWORDS = frozenset(
    {"de", "la", "que", "el", "en", "y", "para", "con", "los", "una"}
)
ENGLISH_STOPWORDS = frozenset(
    {"the", "and", "of", "to", "with", "for", "in", "you", "is", "on"}
)

_WORD = re.compile(r"\w+")


# A stopword count instead of langdetect: langdetect is not deterministic
# unless seeded, and a count is easy to test. Expects text, not HTML: every
# "<a href>" would add one "a".
def detect(title: str, description: str | None) -> Language:
    words = _WORD.findall(f"{title} {description or ''}".lower())
    spanish = sum(word in SPANISH_STOPWORDS for word in words)
    english = sum(word in ENGLISH_STOPWORDS for word in words)
    # A tie, which includes no stopwords at all, falls back to English.
    return "es" if spanish > english else "en"
