import re

import html2text

_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")


# A new converter per call: HTML2Text keeps state between calls and is not
# thread-safe, and /api/sync runs in FastAPI's threadpool.
def _converter() -> html2text.HTML2Text:
    converter = html2text.HTML2Text()
    converter.ignore_images = True
    # Drops the link target, not the link text: a link written as its own URL,
    # like We Work Remotely's "To apply: https://...", keeps that URL as text.
    converter.ignore_links = True
    # No hard wrapping: one paragraph stays on one line.
    converter.body_width = 0
    converter.ul_item_mark = "-"
    return converter


# HTML from a source -> readable markdown. None when there is no text at all,
# so a posting without a description is null, never "".
def to_markdown(raw_html: str | None) -> str | None:
    if not raw_html:
        return None
    converted = _converter().handle(raw_html)
    # Trailing spaces come from <br> and &nbsp;, and leave lines that look
    # empty but are not, so blank runs could not be collapsed.
    lines = [line.rstrip() for line in converted.split("\n")]
    text = _EXTRA_BLANK_LINES.sub("\n\n", "\n".join(lines))
    # Only newlines are trimmed: html2text indents list items, and stripping the
    # first item's indent would nest every following item under it.
    return text.strip("\n") or None
