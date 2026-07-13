from __future__ import annotations

import io

from pointer_io_rssfeed import rss
from pointer_io_rssfeed.render import write_feed


def test_write_feed_pretty_prints_xml_without_formatting_html_descriptions() -> None:
    output = io.StringIO()
    feed = rss.Feed(
        title="Pointer",
        link=rss.URL("https://www.pointer.io/"),
        description="Essential reading",
        items=[rss.Item(title="Issue #1", description="<p><b>tl;dr</b>: Clean HTML</p>")],
    )

    write_feed(feed, output)

    xml = output.getvalue()
    assert xml.startswith("<?xml version='1.0' encoding='utf-8'?>\n")
    assert "\n  <channel>\n" in xml
    assert "\n    <item>\n" in xml
    assert "<description>&lt;p&gt;&lt;b&gt;tl;dr&lt;/b&gt;: Clean HTML&lt;/p&gt;</description>" in xml
    assert xml.endswith("\n")
