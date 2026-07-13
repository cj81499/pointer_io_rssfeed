"""Fetch Pointer archive pages with a filesystem-backed cache."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx
    import trio


async def fetch_archive_html(*, client: httpx.AsyncClient, href: str, cache_dir: trio.Path) -> str:
    """Read an archive page from cache, downloading and caching it when absent."""
    cache_path = cache_dir / f"{post_id_from_href(href)}.html"

    if await cache_path.exists():
        return await cache_path.read_text()

    html = (await client.get(href)).raise_for_status().text
    await cache_dir.mkdir(parents=True, exist_ok=True)
    await cache_path.write_text(html)
    return html


def post_id_from_href(href: str) -> str:
    """Return the cache key encoded in a Pointer archive URL."""
    return href.rstrip("/").split("/")[-1]
