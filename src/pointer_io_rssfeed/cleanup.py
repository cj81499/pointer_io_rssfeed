"""Turn Pointer's email-oriented archive markup into RSS-friendly HTML."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import bs4

if TYPE_CHECKING:
    from collections.abc import Iterable

_UNWANTED_TEXT = re.compile(
    r"(?:"
    r"\bpresented by\b|\bpromoted by\b|\bsponsored by\b|"
    r"how did you like this issue|click the below and shoot me an email|"
    r"\brate (?:or )?rank (?:this )?issue\b|\b(?:un)?subscribe\b"
    r")",
    re.IGNORECASE,
)
_TRACKING_PARAMETERS = frozenset({"_bhlid", "aid"})
_LAYOUT_TAGS = frozenset({"table", "tbody", "thead", "tfoot", "tr", "td", "th"})
_PRESENTATIONAL_TAGS = frozenset({"font", "span", "u"})


def html_to_description(html: str) -> str:
    """Return the editorial content of an archive page as compact HTML.

    Pointer publishes a newsletter email inside each archive page.  The email
    markup contains layout tables, inline CSS, sponsored content, and reader
    feedback controls which are useful in an inbox but not in an RSS reader.
    """
    soup = bs4.BeautifulSoup(html, features="html.parser")
    content = bs4.BeautifulSoup("", features="html.parser")

    for block in _editorial_blocks(soup):
        if not _UNWANTED_TEXT.search(block.get_text(" ", strip=True)):
            content.append(block.extract())

    _simplify_markup(content)
    return str(content)


def _editorial_blocks(soup: bs4.BeautifulSoup) -> Iterable[bs4.Tag]:
    """Yield individual newsletter blocks for the archive template in use."""
    content_blocks = soup.find("tr", id="content-blocks")
    if isinstance(content_blocks, bs4.Tag):
        yield from _beehiiv_blocks(content_blocks)
        return

    # Pointer has used two Mailchimp templates.  In both, each text-content
    # cell is an independently removable editorial block.
    mailchimp_blocks = soup.select(".mceText, .mcnTextContent")
    if mailchimp_blocks:
        yield from mailchimp_blocks
        return

    # Keep the feed useful if Pointer changes templates again, while still
    # applying the sanitizer below.
    if isinstance(soup.body, bs4.Tag):
        yield soup.body


def _beehiiv_blocks(content_blocks: bs4.Tag) -> Iterable[bs4.Tag]:
    """Group Beehiiv rows separated by its visual spacer rows."""
    table = content_blocks.find("table")
    if not isinstance(table, bs4.Tag):
        yield content_blocks
        return

    tbody = table.find("tbody", recursive=False)
    rows_parent = tbody if isinstance(tbody, bs4.Tag) else table
    rows = rows_parent.find_all("tr", recursive=False)
    if not rows:
        yield content_blocks
        return

    group: list[bs4.Tag] = []
    for row in rows:
        group.append(row)
        if _is_spacer_row(row):
            yield _join_blocks(group)
            group = []

    if group:
        yield _join_blocks(group)


def _is_spacer_row(row: bs4.Tag) -> bool:
    # Empty paragraphs and sponsor logos have no text, but belong to their
    # surrounding editorial block. Beehiiv's actual dividers contain only a
    # layout table.
    return (
        not row.get_text(" ", strip=True)
        and row.find("img") is None
        and row.find(["p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "blockquote"]) is None
    )


def _join_blocks(blocks: list[bs4.Tag]) -> bs4.Tag:
    soup = bs4.BeautifulSoup("", features="html.parser")
    for block in blocks:
        soup.append(block.extract())
    return soup


def _simplify_markup(soup: bs4.BeautifulSoup) -> None:
    """Drop email-only markup and leave the small HTML subset RSS readers need."""
    for tag in soup.find_all(["script", "style", "img"]):
        tag.decompose()

    for tag in soup.find_all(_LAYOUT_TAGS):
        tag.unwrap()
    for tag in soup.find_all(_PRESENTATIONAL_TAGS):
        tag.unwrap()

    for tag in soup.find_all(name=True):
        if tag.name == "a":
            href = tag.get("href")
            tag.attrs = {"href": _without_tracking_parameters(href)} if href else {}
        else:
            tag.attrs = {}

    for tag in soup.find_all(["p", "div"]):
        if not tag.get_text(" ", strip=True) and not tag.find("br"):
            tag.decompose()


def _without_tracking_parameters(href: str) -> str:
    parts = urlsplit(href)
    query = _without_tracking_parameters_from_query(parts.query)
    fragment = _without_tracking_parameters_from_fragment(parts.fragment)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, fragment))


def _without_tracking_parameters_from_query(query: str) -> str:
    return urlencode(
        [(key, value) for key, value in parse_qsl(query, keep_blank_values=True) if key not in _TRACKING_PARAMETERS],
        doseq=True,
    )


def _without_tracking_parameters_from_fragment(fragment: str) -> str:
    """Clean tracking parameters placed after a fragment by malformed links."""
    fragment_id, separator, fragment_query = fragment.partition("?")
    if not separator:
        return fragment

    clean_query = _without_tracking_parameters_from_query(fragment_query)
    return f"{fragment_id}?{clean_query}" if clean_query else fragment_id
