from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import bs4
import pytest

from pointer_io_rssfeed import cleanup

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion

_FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "fixture_path",
    sorted(_FIXTURE_DIR.glob("*.html")),
    ids=lambda p: p.name,
)
def test_html_to_description(fixture_path: pathlib.Path, snapshot: SnapshotAssertion) -> None:
    html = fixture_path.read_text()
    description = cleanup.html_to_description(html)
    pretty = bs4.BeautifulSoup(description, features="html.parser").prettify()
    assert pretty == snapshot
