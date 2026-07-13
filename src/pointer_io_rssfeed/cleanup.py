"""Turn Pointer's email-oriented archive markup into RSS-friendly HTML."""

from __future__ import annotations

import bs4

from pointer_io_rssfeed.blocks import editorial_blocks, non_editorial_indexes, remove_rating_prompt
from pointer_io_rssfeed.rules import clean_after_rating_prompt, clean_before_rating_prompt, is_unwanted_block
from pointer_io_rssfeed.sanitize import simplify_markup, without_tracking_parameters

# Kept as a compatibility seam for tests and any callers that used the former
# private helper while the implementation now lives with the other sanitizers.
_without_tracking_parameters = without_tracking_parameters


def html_to_description(html: str) -> str:
    """Return the editorial content of an archive page as compact HTML."""
    soup = bs4.BeautifulSoup(html, features="html.parser")
    content = bs4.BeautifulSoup("", features="html.parser")

    blocks = list(editorial_blocks(soup))
    non_editorial = non_editorial_indexes(blocks)
    for index, block in enumerate(blocks):
        clean_before_rating_prompt(block)
        remove_rating_prompt(block)
        clean_after_rating_prompt(block)
        if index not in non_editorial and not is_unwanted_block(block):
            content.append(block.extract())

    simplify_markup(content)
    return str(content) if content.get_text(strip=True) or content.find(["br", "img"]) else ""
