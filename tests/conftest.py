import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

# (title, description) of each posting in a real We Work Remotely RSS response.
# Read here, not inside a fixture, because params are needed at collection time.
_WWR_ITEMS = [
    (item.findtext("title", ""), item.findtext("description", ""))
    for item in ET.parse(FIXTURES / "wwr_sample.xml").getroot().iter("item")
]


@pytest.fixture
def load_fixture():
    def _load(name: str):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    return _load


# Bytes, not text: an XML feed declares its own encoding, and the parser must
# read it from the file instead of the system default (cp1252 on Windows turns
# "Düsseldorf" into "DÃ¼sseldorf").
@pytest.fixture
def fixture_bytes():
    def _read(name: str) -> bytes:
        return (FIXTURES / name).read_bytes()

    return _read


# A test that asks for this fixture runs once per posting in the feed.
@pytest.fixture(params=_WWR_ITEMS, ids=[title for title, _ in _WWR_ITEMS])
def wwr_item(request) -> tuple[str, str]:
    return request.param
