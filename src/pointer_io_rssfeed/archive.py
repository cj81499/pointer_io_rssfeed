"""Parse Pointer's archive index into typed article metadata."""

from __future__ import annotations

import datetime

import attrs
import bs4


@attrs.frozen(kw_only=True)
class ArchiveEntry:
    """The metadata needed to retrieve and publish one Pointer issue."""

    title: str
    href: str
    published_at: datetime.datetime


def parse_entries(html: bytes, *, timezone: datetime.tzinfo) -> list[ArchiveEntry]:
    """Extract Pointer issue metadata from the archive index response."""
    soup = bs4.BeautifulSoup(html, features="html.parser")
    return [_entry_from_tag(tag, timezone=timezone) for tag in soup.find_all("a") if _is_article_tag(tag)]


def _entry_from_tag(tag: bs4.Tag, *, timezone: datetime.tzinfo) -> ArchiveEntry:
    h2 = tag.find("h2")
    assert isinstance(h2, bs4.Tag)
    href = tag.get("href")
    assert isinstance(href, str)
    time = tag.find("time")
    assert isinstance(time, bs4.Tag)

    published_at = datetime.datetime.strptime(time.text.strip(), "%B %d, %Y").replace(
        # Pointer is typically released around 9am New York time.
        hour=9,
        tzinfo=timezone,
    )
    return ArchiveEntry(title=h2.text.strip(), href=href, published_at=published_at)


def _is_article_tag(tag: bs4.Tag) -> bool:
    href = tag.get("href")
    return isinstance(href, str) and href.startswith("/archives/")
