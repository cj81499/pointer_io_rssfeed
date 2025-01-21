import datetime
import email.utils
import xml.etree.ElementTree as ET
from typing import NewType, Protocol

import attrs

URL = NewType("URL", str)

_DEFAULT_DOCS_URL = URL("http://blogs.law.harvard.edu/tech/rss")


class _SupportsToXml(Protocol):
    def to_xml(self) -> ET.Element: ...


@attrs.frozen(kw_only=True)
class Image(_SupportsToXml):
    url: URL
    title: str
    link: URL
    # width: int | None = None  # noqa: ERA001
    # height: int | None = None  # noqa: ERA001
    # description: str | None = None  # noqa: ERA001

    def to_xml(self) -> ET.Element:
        image = ET.Element("image")
        ET.SubElement(image, "url").text = self.url
        ET.SubElement(image, "title").text = self.title
        ET.SubElement(image, "link").text = self.link
        return image


@attrs.frozen(kw_only=True)
class Item(_SupportsToXml):
    title: str | None = None
    link: URL | None = None
    description: str | None = None
    # author
    # category
    # comments
    # enclosure
    # guid
    pub_date: datetime.datetime | None = None
    # source

    def __attrs_post_init__(self) -> None:
        if self.title is None and self.description is None:
            msg = "At least one of title or description must be set."
            raise ValueError(msg)

    def to_xml(self) -> ET.Element:
        item = ET.Element("item")
        if self.title:
            ET.SubElement(item, "title").text = self.title
        if self.link:
            ET.SubElement(item, "link").text = self.link
        if self.description:
            ET.SubElement(item, "description").text = self.description
        if self.pub_date:
            ET.SubElement(item, "pubDate").text = email.utils.format_datetime(self.pub_date)
        return item


@attrs.frozen(kw_only=True)
class Feed(_SupportsToXml):
    title: str
    link: URL
    description: str
    items: list[Item]
    # language
    # copyright
    # managingEditor
    # webMaster
    pub_date: datetime.datetime | None = None
    last_build_date: datetime.datetime | None = None
    # category
    # generator
    docs: URL | None = _DEFAULT_DOCS_URL
    # cloud
    # ttl
    image: Image | None = None
    # rating
    # textInput
    # skipHours
    # skipDays

    def to_xml(self) -> ET.Element:
        rss = ET.Element("rss", {"version": "2.0"})
        channel = ET.SubElement(rss, "channel")

        # required channel elements
        ET.SubElement(channel, "title").text = self.title
        ET.SubElement(channel, "link").text = self.link
        ET.SubElement(channel, "description").text = self.description

        # optional channel elements
        if self.pub_date:
            ET.SubElement(channel, "pubDate").text = email.utils.format_datetime(self.pub_date)
        if self.last_build_date:
            ET.SubElement(channel, "lastBuildDate").text = email.utils.format_datetime(self.last_build_date)
        if self.docs:
            ET.SubElement(channel, "docs").text = self.docs
        if self.image:
            channel.append(self.image.to_xml())

        # items
        channel.extend(it.to_xml() for it in self.items)

        return rss
