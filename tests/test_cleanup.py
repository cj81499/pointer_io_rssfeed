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


@pytest.mark.parametrize(
    "fixture_path",
    sorted(_FIXTURE_DIR.glob("*.html")),
    ids=lambda p: p.name,
)
def test_html_to_description_removes_email_only_markup(fixture_path: pathlib.Path) -> None:
    description = cleanup.html_to_description(fixture_path.read_text())

    assert "style=" not in description
    assert "<table" not in description
    assert "<img" not in description
    assert "_bhlid=" not in description
    assert "&aid=" not in description
    assert "sponsored_ad" not in description
    assert "presented by" not in description.lower()
    assert "promoted by" not in description.lower()
    assert "how did you like this issue" not in description.lower()


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        ("https://example.com/article?aid=abc&keep=yes", "https://example.com/article?keep=yes"),
        ("https://example.com/article#section?&aid=abc", "https://example.com/article#section"),
        (
            "https://example.com/article#section?keep=yes&aid=abc",
            "https://example.com/article#section?keep=yes",
        ),
    ],
)
def test_tracking_parameters_are_removed_from_query_and_fragment(href: str, expected: str) -> None:
    assert cleanup._without_tracking_parameters(href) == expected  # noqa: SLF001


def test_html_to_description_removes_tracking_parameters_from_fragment_urls() -> None:
    description = cleanup.html_to_description(
        """
        <tr id="content-blocks"><td><table><tr><td>
          <p><a href="https://example.com/article#section?keep=yes&amp;aid=abc&amp;_bhlid=def">Article</a></p>
        </td></tr></table></td></tr>
        """
    )

    assert 'href="https://example.com/article#section?keep=yes"' in description
    assert "aid=" not in description
    assert "_bhlid=" not in description


def test_html_to_description_keeps_editorial_subscribe_calls_to_action() -> None:
    description = cleanup.html_to_description(
        "<html><body><p>Subscribe for a weekly roundup of engineering articles.</p></body></html>"
    )

    assert "Subscribe for a weekly roundup of engineering articles." in description


def test_html_to_description_removes_unsubscribe_controls() -> None:
    description = cleanup.html_to_description("<html><body><p>Unsubscribe from this list.</p></body></html>")

    assert description == ""


@pytest.mark.parametrize(
    "text",
    [
        "This issue is presented by Example Corp.",
        "This article is promoted by Example Corp.",
        "This article is sponsored by Example Corp.",
        "Find a job with Example Corp. #Sponsored",
    ],
)
def test_html_to_description_removes_advertisement_labels(text: str) -> None:
    description = cleanup.html_to_description(f"<html><body><p>{text}</p></body></html>")

    assert description == ""
