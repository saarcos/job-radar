import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from jobradar.domain.html_text import to_markdown

FIXTURES = Path(__file__).parent.parent / "fixtures"

# (title, description) of each posting in a real We Work Remotely RSS response.
WWR_ITEMS = [
    (item.findtext("title", ""), item.findtext("description", ""))
    for item in ET.parse(FIXTURES / "wwr_sample.xml").getroot().iter("item")
]
wwr_descriptions = pytest.mark.parametrize(
    "description",
    [description for _, description in WWR_ITEMS],
    ids=[title for title, _ in WWR_ITEMS],
)


@wwr_descriptions
def test_wwr_description_has_no_html(description):
    assert "<" in description  # the fixture really is HTML

    markdown = to_markdown(description)

    assert markdown is not None
    for leftover in ("<", ">", "&nbsp;"):
        assert leftover not in markdown


@wwr_descriptions
def test_wwr_description_drops_images_and_link_targets(description):
    assert "<a " in description

    markdown = to_markdown(description)

    assert markdown is not None
    assert "![" not in markdown
    assert "](" not in markdown


@wwr_descriptions
def test_wwr_description_keeps_lists(description):
    assert "<li>" in description

    markdown = to_markdown(description)

    assert markdown is not None
    assert any(line.lstrip().startswith("- ") for line in markdown.split("\n"))


@pytest.mark.parametrize("raw_html", [None, "", "   ", "<p></p>", "<p>&nbsp;</p>"])
def test_no_text_is_none(raw_html):
    assert to_markdown(raw_html) is None


def test_collapses_blank_lines_and_trailing_spaces():
    raw_html = "<p>London<br>Remote</p><p>&nbsp;</p><p>&nbsp;</p><p>Apply</p>"

    assert to_markdown(raw_html) == "London\nRemote\n\nApply"


def test_list_items_keep_one_level():
    assert to_markdown("<ul><li>Python</li><li>Go</li></ul>") == "  - Python\n  - Go"


def test_drops_images():
    raw_html = '<img src="https://cdn.example.com/logo.gif" /><p>Hello</p>'

    assert to_markdown(raw_html) == "Hello"


def test_keeps_link_text_and_drops_target():
    raw_html = '<p>See <a href="https://example.com/python-jobs">our site</a></p>'

    assert to_markdown(raw_html) == "See our site"


# Known and accepted: a link whose text is its own URL keeps the URL as text.
def test_link_written_as_url_keeps_url():
    raw_html = (
        '<p>To apply: <a href="https://example.com/job">https://example.com/job</a></p>'
    )

    assert to_markdown(raw_html) == "To apply: https://example.com/job"
