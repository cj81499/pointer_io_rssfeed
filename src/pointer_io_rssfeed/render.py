"""Serialize RSS feeds as readable XML."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import TextIO

    from pointer_io_rssfeed import rss


def write_feed(feed: rss.Feed, output: TextIO) -> None:
    """Write an RSS document that is readable in a terminal or text editor."""
    document = feed.to_xml()
    ET.indent(document, space="  ")
    ET.ElementTree(document).write(output, encoding="unicode", xml_declaration=True)
    output.write("\n")
