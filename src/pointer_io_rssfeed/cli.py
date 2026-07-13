"""Command-line entrypoint for generating the Pointer RSS feed."""

from __future__ import annotations

import datetime
import enum
import logging
import logging.config
import sys
import zoneinfo

import click
import httpx
import trio

from pointer_io_rssfeed import archive, cleanup, fetch, render, rss

_BASE_URL = httpx.URL("https://www.pointer.io/")
_LOGGER = logging.getLogger(__name__)
_NY_ZONE_INFO = zoneinfo.ZoneInfo("America/New_York")

# Browser-style headers avoid Pointer's Cloudflare managed challenge on GitHub Actions.
_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
}


class _LogLevel(enum.StrEnum):
    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@click.command(
    context_settings={
        "help_option_names": ["-h", "--help"],
        "max_content_width": 120,
    }
)
@click.option(
    "--max-concurrency",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    envvar="MAX_CONCURRENCY",
    show_envvar=True,
)
@click.option(
    "--cache-dir",
    type=click.Path(path_type=trio.Path),
    default=trio.Path(".cache/pointer"),
    show_default=True,
    envvar="CACHE_DIR",
    show_envvar=True,
)
@click.option(
    "--log-level",
    type=click.Choice(_LogLevel, case_sensitive=False),
    default="INFO",
    show_default=True,
    envvar="LOG_LEVEL",
    show_envvar=True,
)
@click.version_option()
def main(
    *,
    max_concurrency: int,
    cache_dir: trio.Path,
    log_level: _LogLevel,
) -> None:
    """Fetch Pointer's archive and write a cleaned RSS 2.0 feed to stdout."""
    _configure_logging(log_level=log_level)
    trio.run(_generate_feed, max_concurrency, cache_dir)


async def _generate_feed(max_concurrency: int, cache_dir: trio.Path) -> None:
    try:
        async with httpx.AsyncClient(
            base_url=_BASE_URL,
            follow_redirects=True,
            headers=_BROWSER_HEADERS,
            timeout=httpx.Timeout(30),
        ) as client:
            _LOGGER.info("Get archives")
            response = (await client.get("/archives/")).raise_for_status()
            _LOGGER.info("Parse response")
            entries = archive.parse_entries(response.content, timezone=_NY_ZONE_INFO)

            semaphore = trio.Semaphore(max_concurrency)
            rss_items: list[rss.Item] = []

            async def worker(entry: archive.ArchiveEntry) -> None:
                async with semaphore:
                    item = await _entry_to_rss_item(entry=entry, client=client, cache_dir=cache_dir)
                rss_items.append(item)

            _LOGGER.info("Fetching %s articles", len(entries))
            async with trio.open_nursery() as nursery:
                for entry in entries:
                    nursery.start_soon(worker, entry)
    except httpx.HTTPStatusError as error:
        _LOGGER.exception("HTTP failure. HTTP response content: %s", error.response.content)
        raise SystemExit(1) from error

    _LOGGER.info("Got %s articles", len(rss_items))
    _LOGGER.info("Building RSS Feed")
    feed = rss.Feed(
        title="Pointer",
        link=rss.URL(str(_BASE_URL)),
        image=rss.Image(
            url=rss.URL("https://www.pointer.io/static/apple-touch-icon.png"),
            title="Pointer",
            link=rss.URL(str(_BASE_URL)),
        ),
        description="Essential Reading For Engineering Leaders",
        last_build_date=datetime.datetime.now(tz=datetime.UTC),
        items=sorted(rss_items, key=_item_pub_date),
    )

    _LOGGER.info("Writing RSS feed")
    render.write_feed(feed, sys.stdout)


async def _entry_to_rss_item(
    *, entry: archive.ArchiveEntry, client: httpx.AsyncClient, cache_dir: trio.Path
) -> rss.Item:
    html = await fetch.fetch_archive_html(client=client, href=entry.href, cache_dir=cache_dir)
    return rss.Item(
        title=entry.title,
        link=rss.URL(str(_BASE_URL.join(entry.href))),
        pub_date=entry.published_at,
        description=cleanup.html_to_description(html),
    )


def _item_pub_date(item: rss.Item) -> datetime.datetime:
    assert item.pub_date is not None
    return item.pub_date


def _configure_logging(*, log_level: _LogLevel) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "simple": {
                    "format": "[%(levelname)s|%(name)s|%(module)s|L%(lineno)d] %(asctime)s: %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                }
            },
            "handlers": {
                "stderr": {
                    "class": "logging.StreamHandler",
                    "formatter": "simple",
                    "stream": "ext://sys.stderr",
                }
            },
            "root": {
                "level": log_level,
                "handlers": ["stderr"],
            },
            "loggers": {},
        }
    )


if __name__ == "__main__":
    main()
