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

# Below this share of the words, the winning list does not dominate and the
# language is unknown. Calibrated on 2026-11-14 over 231 unique We Work Remotely
# postings and the Get on Board fixture: English postings had at least 6.5% of
# their words in ENGLISH_STOPWORDS, Spanish ones 26-30% in SPANISH_STOPWORDS,
# and the one in German 2.8%: 11 of its 395 words, all of them in
# ENGLISH_STOPWORDS. Known limit: Portuguese shares "de", "que" and "para" with
# Spanish, so it comes out "es".
MIN_STOPWORD_SHARE = 0.05

_WORD = re.compile(r"\w+")


# A stopword count instead of langdetect: langdetect is not deterministic
# unless seeded, and a count is easy to test. Expects text, not HTML: every
# "<a href>" would add one "a". None when neither list clearly dominates: a
# made-up language would be a lie that later picks the language of a resume.
def detect(title: str, description: str | None) -> Language | None:
    words = _WORD.findall(f"{title} {description or ''}".lower())
    spanish = sum(word in SPANISH_STOPWORDS for word in words)
    english = sum(word in ENGLISH_STOPWORDS for word in words)
    # Includes no stopwords at all.
    if spanish == english:
        return None
    language: Language
    language, hits = ("es", spanish) if spanish > english else ("en", english)
    return language if hits >= MIN_STOPWORD_SHARE * len(words) else None
