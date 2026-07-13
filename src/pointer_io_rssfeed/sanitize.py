"""Simplify retained article HTML for RSS readers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

if TYPE_CHECKING:
    import bs4

_TRACKING_PARAMETERS = frozenset({"_bhlid", "aid"})
_LAYOUT_TAGS = frozenset({"table", "tbody", "thead", "tfoot", "tr", "td", "th"})
_PRESENTATIONAL_TAGS = frozenset({"font", "span", "u"})


def simplify_markup(soup: bs4.BeautifulSoup) -> None:
    """Drop email-only markup and leave the small HTML subset RSS readers need."""
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    for tag in soup.find_all(_LAYOUT_TAGS):
        tag.unwrap()
    for tag in soup.find_all(_PRESENTATIONAL_TAGS):
        tag.unwrap()

    for tag in soup.find_all(name=True):
        if tag.name == "a":
            href = tag.get("href")
            tag.attrs = {"href": without_tracking_parameters(href)} if href else {}
        elif tag.name == "img":
            tag.attrs = {attribute: tag[attribute] for attribute in ("alt", "src") if tag.get(attribute)}
        else:
            tag.attrs = {}

    _remove_empty_anchors(soup)

    for tag in soup.find_all(["p", "div"]):
        if not tag.get_text(" ", strip=True) and not tag.find("br"):
            tag.decompose()


def without_tracking_parameters(href: str) -> str:
    parts = urlsplit(href)
    query = _without_tracking_parameters_from_query(parts.query)
    fragment = _without_tracking_parameters_from_fragment(parts.fragment)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, fragment))


def _remove_empty_anchors(soup: bs4.BeautifulSoup) -> None:
    for tag in soup.find_all("a"):
        if not tag.get_text(strip=True) and tag.find("img") is None:
            tag.decompose()


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
