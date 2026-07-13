from __future__ import annotations

import datetime
import zoneinfo

from pointer_io_rssfeed import archive


def test_parse_entries_extracts_only_archive_articles() -> None:
    entries = archive.parse_entries(
        b"""
        <a href="/about/"><h2>About</h2></a>
        <a href="/archives/abc123"><h2>Issue #1</h2><time>May 05, 2026</time></a>
        <a href="/archives/def456/"><h2>Issue #2</h2><time>May 08, 2026</time></a>
        """,
        timezone=zoneinfo.ZoneInfo("America/New_York"),
    )

    assert entries == [
        archive.ArchiveEntry(
            title="Issue #1",
            href="/archives/abc123",
            published_at=datetime.datetime(2026, 5, 5, 9, tzinfo=zoneinfo.ZoneInfo("America/New_York")),
        ),
        archive.ArchiveEntry(
            title="Issue #2",
            href="/archives/def456/",
            published_at=datetime.datetime(2026, 5, 8, 9, tzinfo=zoneinfo.ZoneInfo("America/New_York")),
        ),
    ]
