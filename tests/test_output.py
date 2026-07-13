from __future__ import annotations

import io

from pointer_io_rssfeed import rss
from pointer_io_rssfeed.render import write_feed


def test_write_feed_pretty_prints_cdata_descriptions() -> None:
    output = io.StringIO()
    feed = rss.Feed(
        title="Pointer",
        link=rss.URL("https://www.pointer.io/"),
        description="Essential reading",
        items=[
            rss.Item(
                title="Issue #1",
                description="<div><p><b>tl;dr</b>: Clean]]>HTML</p><ul><li>One</li></ul></div>",
            )
        ],
    )

    write_feed(feed, output)

    xml = output.getvalue()
    assert xml.startswith('<?xml version="1.0" encoding="utf-8"?>\n')
    assert "\n  <channel>\n" in xml
    assert "\n    <item>\n" in xml
    assert "<description><![CDATA[<div>\n  <p><b>tl;dr</b>: Clean]]&gt;HTML</p>\n  <ul>\n" in xml
    assert "    <li>One</li>\n  </ul>\n</div>]]></description>" in xml
    assert xml.endswith("\n")
