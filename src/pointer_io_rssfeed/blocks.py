"""Locate editorial blocks across Pointer's archive templates."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import bs4

from pointer_io_rssfeed.rules import is_sponsor_call_to_action, is_unwanted_block

if TYPE_CHECKING:
    from collections.abc import Iterable

_UNSUBSCRIBE_TEXT = re.compile(
    r"unsubscribe[ ]from[ ]this[ ]list|update[ ]your[ ]email[ ]preferences[ ]or[ ]unsubscribe",
    re.IGNORECASE,
)
_MAXIMUM_SPONSOR_CTA_LENGTH = 160
_SPONSOR_CARD_HEADER = re.compile(r"\bissue\s+is\s+presented\s+by\b", re.IGNORECASE)
_SPLIT_TRAILING_BLOCK_HEADER = re.compile(
    r"(?:most\s+popular\s+from\s+last\s+issue|notable\s+event|developer\s+insights\s+needed)",
    re.IGNORECASE,
)
_ORPHANABLE_SECTION_HEADER = re.compile(r"(?:jobs|recommended\s+reading)", re.IGNORECASE)
_LEGACY_JOB_BOARD_HEADER = re.compile(
    r"the\s+best\s+startups?\s+engineering\s+jobs\s+in\s+ny(?:\.{3}|…)?",
    re.IGNORECASE,
)
_LEGACY_JOB_BOARD_INTRO = re.compile(r"best\s+startups?\s+engineering\s+jobs\s+in\s+ny", re.IGNORECASE)
_RATING_PROMPT_TEXT = re.compile(r"click\s+the\s+below\s+and\s+shoot\s+me\s+an\s+email", re.IGNORECASE)


def editorial_blocks(soup: bs4.BeautifulSoup) -> Iterable[bs4.Tag]:
    """Yield individual newsletter blocks for the archive template in use."""
    content_blocks = soup.find("tr", id="content-blocks")
    if isinstance(content_blocks, bs4.Tag):
        yield from _beehiiv_blocks(content_blocks)
        return

    # Pointer has used two Mailchimp templates. In both, each text-content
    # cell is an independently removable editorial block.
    mailchimp_blocks = soup.select(".mceText, .mcnTextContent")
    if mailchimp_blocks:
        yield from mailchimp_blocks
        return

    foundation_email_blocks = soup.select(".row.collapse.mail-text")
    if foundation_email_blocks:
        yield from foundation_email_blocks
        return

    # Keep the feed useful if Pointer changes templates again, while still
    # applying the sanitizer below.
    if isinstance(soup.body, bs4.Tag):
        _remove_fallback_unsubscribe_controls(soup.body)
        yield soup.body


def _remove_fallback_unsubscribe_controls(body: bs4.Tag) -> None:
    """Remove footer controls before treating an unknown template as one block."""
    for tag in body.find_all(["p", "a"]):
        if tag.parent is not None and _UNSUBSCRIBE_TEXT.search(tag.get_text(" ", strip=True)):
            tag.decompose()


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
        if is_spacer_row(row):
            yield _join_blocks(group)
            group = []

    if group:
        yield _join_blocks(group)


def is_spacer_row(row: bs4.Tag) -> bool:
    # Empty paragraphs and sponsor logos have no text, but belong to their
    # surrounding editorial block. Beehiiv's actual dividers contain only a
    # layout table.
    return (
        not row.get_text(" ", strip=True)
        and row.find("img") is None
        and row.find(["p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "blockquote"]) is None
    )


def remove_rating_prompt(block: bs4.Tag) -> None:
    """Remove a trailing email-rating prompt without discarding its block."""
    marker = block.find(string=_RATING_PROMPT_TEXT)
    row = marker.find_parent("tr") if marker is not None else None
    if not isinstance(row, bs4.Tag):
        if marker is not None:
            block.clear()
        return
    if block not in row.parents:
        block.clear()
        return

    for sibling in [row, *row.find_next_siblings("tr")]:
        if not isinstance(sibling, bs4.Tag):
            continue
        spacer = is_spacer_row(sibling)
        sibling.extract()
        if spacer:
            break


def non_editorial_indexes(blocks: list[bs4.Tag]) -> set[int]:
    """Return adjacent blocks that form one non-editorial section."""
    return (
        _sponsor_card_indexes(blocks)
        | _split_trailing_section_indexes(blocks)
        | _orphaned_header_indexes(blocks)
        | _legacy_job_board_indexes(blocks)
    )


def _sponsor_card_indexes(blocks: list[bs4.Tag]) -> set[int]:
    unwanted: set[int] = set()
    for index, block in enumerate(blocks):
        if "mceText" not in block.get("class", []) or not _SPONSOR_CARD_HEADER.search(block.get_text(" ", strip=True)):
            continue

        unwanted.update(range(index, min(index + 2, len(blocks))))
        cta_index = index + 2
        if cta_index < len(blocks):
            cta_text = blocks[cta_index].get_text(" ", strip=True)
            if len(cta_text) <= _MAXIMUM_SPONSOR_CTA_LENGTH and is_sponsor_call_to_action(cta_text):
                unwanted.add(cta_index)

        sponsor_hosts = _hosts_in(blocks[index + 1 : index + 3])
        for later_index, later_block in enumerate(blocks[index + 3 :], start=index + 3):
            if _hosts_in([later_block]) & sponsor_hosts:
                unwanted.add(later_index)
    return unwanted


def _hosts_in(blocks: list[bs4.Tag]) -> set[str]:
    return {
        urlsplit(str(anchor["href"])).netloc.casefold().removeprefix("www.")
        for block in blocks
        for anchor in block.find_all("a", href=True)
    }


def _split_trailing_section_indexes(blocks: list[bs4.Tag]) -> set[int]:
    unwanted: set[int] = set()
    for index, block in enumerate(blocks):
        if "mceText" in block.get("class", []) and _SPLIT_TRAILING_BLOCK_HEADER.fullmatch(
            block.get_text(" ", strip=True)
        ):
            unwanted.update(range(index, min(index + 2, len(blocks))))
    return unwanted


def _orphaned_header_indexes(blocks: list[bs4.Tag]) -> set[int]:
    return {
        index
        for index, block in enumerate(blocks[:-1])
        if "mceText" in block.get("class", [])
        and _ORPHANABLE_SECTION_HEADER.fullmatch(block.get_text(" ", strip=True))
        and is_unwanted_block(blocks[index + 1])
    }


def _legacy_job_board_indexes(blocks: list[bs4.Tag]) -> set[int]:
    unwanted: set[int] = set()
    for index, block in enumerate(blocks):
        if "mcnTextContent" not in block.get("class", []):
            continue
        text = block.get_text(" ", strip=True)
        if _LEGACY_JOB_BOARD_HEADER.match(text):
            unwanted.update(range(index, len(blocks)))
        elif _LEGACY_JOB_BOARD_INTRO.search(text):
            unwanted.update(range(index + 2, len(blocks)))
    return unwanted


def _join_blocks(blocks: list[bs4.Tag]) -> bs4.Tag:
    soup = bs4.BeautifulSoup("", features="html.parser")
    for block in blocks:
        soup.append(block.extract())
    return soup
