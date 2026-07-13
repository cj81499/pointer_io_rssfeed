"""Fetch Pointer archive pages with a filesystem-backed cache."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import trio

BASE_URL = httpx.URL("https://www.pointer.io/")

# Browser-style headers avoid Pointer's Cloudflare managed challenge on GitHub Actions.
_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
}


@asynccontextmanager
async def pointer_client() -> AsyncIterator[httpx.AsyncClient]:
    """Yield an HTTP client configured for Pointer's archive endpoints."""
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        follow_redirects=True,
        headers=_BROWSER_HEADERS,
        timeout=httpx.Timeout(30),
    ) as client:
        yield client


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
