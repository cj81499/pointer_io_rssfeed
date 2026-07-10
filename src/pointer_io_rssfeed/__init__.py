import datetime
import enum
import logging
import logging.config
import sys
import xml.etree.ElementTree as ET
import zoneinfo

import bs4
import click
import httpx
import trio

from pointer_io_rssfeed import cleanup, rss

_BASE_URL = httpx.URL("https://www.pointer.io/")
_LOGGER = logging.getLogger(__name__)
_NY_ZONE_INFO = zoneinfo.ZoneInfo("America/New_York")
_MAX_REQUEST_ATTEMPTS = 3
_HTTP_FORBIDDEN = 403
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Pointer is protected by Cloudflare.  httpx's default user agent identifies
# this scheduled fetch as an automated client, while the site is intended to
# be viewed in a browser.  These headers deliberately describe an ordinary
# desktop browser; they are not intended to solve or circumvent a challenge.
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


async def _article_tag_to_rss_item(
    *, article_tag: bs4.Tag, client: httpx.AsyncClient, cache_dir: trio.Path
) -> rss.Item:
    h2 = article_tag.find("h2")
    assert isinstance(h2, bs4.Tag)
    href = article_tag.get("href")
    assert isinstance(href, str)
    time = article_tag.find("time")
    assert isinstance(time, bs4.Tag)

    pub_date = datetime.datetime.strptime(time.text.strip(), "%B %d, %Y").replace(
        # Pointer is typically released around 9am NY time
        hour=9,
        tzinfo=_NY_ZONE_INFO,
    )

    html = await _fetch_archive_html(client=client, href=href, cache_dir=cache_dir)
    description = cleanup.html_to_description(html)

    return rss.Item(
        title=h2.text.strip(),
        link=rss.URL(str(_BASE_URL.join(href))),
        pub_date=pub_date,
        description=description,
    )


def _is_article_tag(tag: bs4.Tag) -> bool:
    href = tag.get("href")
    if not isinstance(href, str):
        _LOGGER.warning("tag href must be a str. tag=%s href=%s", tag, href)
        return False
    return href.startswith("/archives/")


def _post_id_from_href(href: str) -> str:
    return href.rstrip("/").split("/")[-1]


async def _fetch_archive_html(*, client: httpx.AsyncClient, href: str, cache_dir: trio.Path) -> str:
    post_id = _post_id_from_href(href)
    cache_path = cache_dir / f"{post_id}.html"

    if await cache_path.exists():
        _LOGGER.debug("Cache hit. post_id=%s", post_id)
        return await cache_path.read_text()

    _LOGGER.debug("Cache miss. Fetching. post_id=%s", post_id)
    resp = await _get(client=client, url=href)
    html = resp.text

    await cache_dir.mkdir(parents=True, exist_ok=True)
    await cache_path.write_text(html)

    return html


def _is_retryable_response(response: httpx.Response) -> bool:
    """Return whether a response is worth retrying from the same runner."""
    return response.status_code in _RETRYABLE_STATUS_CODES or (
        response.status_code == _HTTP_FORBIDDEN and response.headers.get("Cf-Mitigated") == "challenge"
    )


async def _get(*, client: httpx.AsyncClient, url: str) -> httpx.Response:
    """Fetch *url*, retrying transient errors and Cloudflare managed challenges."""
    for attempt in range(1, _MAX_REQUEST_ATTEMPTS + 1):
        try:
            response = await client.get(url)
        except httpx.RequestError:
            if attempt == _MAX_REQUEST_ATTEMPTS:
                raise
            _LOGGER.warning(
                "Request failed for %s (attempt %s/%s); retrying",
                url,
                attempt,
                _MAX_REQUEST_ATTEMPTS,
            )
        else:
            if response.is_success:
                return response

            if not _is_retryable_response(response) or attempt == _MAX_REQUEST_ATTEMPTS:
                response.raise_for_status()

            _LOGGER.warning(
                "Received HTTP %s for %s (Cf-Mitigated=%s, attempt %s/%s); retrying",
                response.status_code,
                url,
                response.headers.get("Cf-Mitigated"),
                attempt,
                _MAX_REQUEST_ATTEMPTS,
            )

        await trio.sleep(2 ** (attempt - 1))

    msg = "Request retry loop ended unexpectedly"
    raise RuntimeError(msg)


def _item_pub_date(item: rss.Item) -> datetime.datetime:
    assert item.pub_date is not None
    return item.pub_date


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
    _configure_logging(log_level=log_level)

    async def _main() -> None:
        try:
            async with httpx.AsyncClient(
                base_url=_BASE_URL,
                follow_redirects=True,
                headers=_BROWSER_HEADERS,
                timeout=httpx.Timeout(30),
            ) as client:
                _LOGGER.info("Get archives")
                resp = await _get(client=client, url="/archives/")
                _LOGGER.info("Parse response")
                soup = bs4.BeautifulSoup(resp.content, features="html.parser")
                article_tags = [a for a in soup.find_all("a") if isinstance(a, bs4.Tag) and _is_article_tag(a)]

                sem = trio.Semaphore(max_concurrency)
                rss_items: list[rss.Item] = []

                async def _worker(article_tag: bs4.Tag) -> None:
                    async with sem:
                        item = await _article_tag_to_rss_item(
                            article_tag=article_tag, client=client, cache_dir=cache_dir
                        )
                    rss_items.append(item)

                _LOGGER.info("Fetching %s articles", len(article_tags))
                async with trio.open_nursery() as nursery:
                    for tag in article_tags:
                        nursery.start_soon(_worker, tag)
        except httpx.HTTPStatusError as e:
            _LOGGER.exception("HTTP failure. HTTP response content: %s", e.response.content)
            raise SystemExit(1) from e

        _LOGGER.info("Got %s articles", len(rss_items))

        _LOGGER.info("Building RSS Feed")
        rss_doc = rss.Feed(
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

        # output RSS Feed to stdout
        _LOGGER.info("Writing RSS feed")
        ET.ElementTree(rss_doc.to_xml()).write(sys.stdout, encoding="unicode")

    trio.run(_main)


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
