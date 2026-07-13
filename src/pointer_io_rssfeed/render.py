"""Serialize RSS feeds with readable XML and HTML descriptions."""

from __future__ import annotations

import uuid
import xml.dom.minidom
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

import bs4

if TYPE_CHECKING:
    from typing import TextIO

    from pointer_io_rssfeed import rss

_HTML_BLOCK_TAGS = frozenset(
    {
        "article",
        "aside",
        "blockquote",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "ol",
        "p",
        "pre",
        "section",
        "ul",
    }
)


def write_feed(feed: rss.Feed, output: TextIO) -> None:
    """Write an RSS document that is readable in a terminal or text editor."""
    document = xml.dom.minidom.Document()
    cdata_boundary = f"__RSS_CDATA_BOUNDARY_{uuid.uuid4().hex}__"
    document.appendChild(_to_dom_element(feed.to_xml(), document, cdata_boundary))
    formatted_xml = document.toprettyxml(indent="  ", newl="\n", encoding="utf-8").decode("utf-8")
    output.write(formatted_xml.replace(cdata_boundary, "]]]]><![CDATA[>"))


def _to_dom_element(
    source: ET.Element,
    document: xml.dom.minidom.Document,
    cdata_boundary: str,
    parent_tag: str | None = None,
) -> xml.dom.minidom.Element:
    target = document.createElement(source.tag)
    for name, value in source.attrib.items():
        target.setAttribute(name, value)

    if source.text:
        if source.tag == "description" and parent_tag == "item":
            _append_cdata(target, source.text, document, cdata_boundary)
        else:
            target.appendChild(document.createTextNode(source.text))

    for child in source:
        target.appendChild(_to_dom_element(child, document, cdata_boundary, parent_tag=source.tag))
        if child.tail:
            target.appendChild(document.createTextNode(child.tail))

    return target


def _append_cdata(
    parent: xml.dom.minidom.Element, text: str, document: xml.dom.minidom.Document, cdata_boundary: str
) -> None:
    """Append a CDATA node, marking the one sequence XML forbids in CDATA."""
    pretty_html = _prettify_html(text)
    parent.appendChild(document.createCDATASection(pretty_html.replace("]]>", cdata_boundary)))


def _prettify_html(html: str) -> str:
    """Indent block-level HTML without adding whitespace inside inline content."""
    soup = bs4.BeautifulSoup(html, features="html.parser")
    lines: list[str] = []
    for child in soup.contents:
        _append_prettified_html(child, indentation=0, lines=lines)
    return "\n".join(lines)


def _append_prettified_html(node: bs4.PageElement, *, indentation: int, lines: list[str]) -> None:
    if isinstance(node, bs4.NavigableString):
        if text := node.strip():
            lines.append(f"{'  ' * indentation}{text}")
        return

    if not isinstance(node, bs4.Tag):
        return

    if not any(isinstance(child, bs4.Tag) and child.name in _HTML_BLOCK_TAGS for child in node.contents):
        lines.append(f"{'  ' * indentation}{node}")
        return

    lines.append(f"{'  ' * indentation}{_opening_html_tag(node)}")
    inline_html: list[str] = []
    for child in node.contents:
        if isinstance(child, bs4.Tag) and child.name in _HTML_BLOCK_TAGS:
            if fragment := "".join(inline_html).strip():
                lines.append(f"{'  ' * (indentation + 1)}{fragment}")
            inline_html = []
            _append_prettified_html(child, indentation=indentation + 1, lines=lines)
        else:
            inline_html.append(str(child))

    if fragment := "".join(inline_html).strip():
        lines.append(f"{'  ' * (indentation + 1)}{fragment}")
    lines.append(f"{'  ' * indentation}</{node.name}>")


def _opening_html_tag(tag: bs4.Tag) -> str:
    soup = bs4.BeautifulSoup("", features="html.parser")
    empty_tag = soup.new_tag(tag.name, attrs=tag.attrs)
    return str(empty_tag).removesuffix(f"</{tag.name}>")
