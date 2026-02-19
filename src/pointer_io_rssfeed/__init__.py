import datetime
import logging
import logging.config
import os
import sys
import xml.etree.ElementTree as ET
import zoneinfo

import bs4
import click
import httpx
import trio

from pointer_io_rssfeed import rss

_BASE_URL = httpx.URL("https://www.pointer.io/")
_LOGGER = logging.getLogger(__name__)
_NY_ZONE_INFO = zoneinfo.ZoneInfo("America/New_York")


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
    description = _html_to_description(html)

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
    resp = (await client.get(href)).raise_for_status()
    html = resp.text

    await cache_dir.mkdir(parents=True, exist_ok=True)
    await cache_path.write_text(html)

    return html


def _html_to_description(html: str) -> str:
    soup = bs4.BeautifulSoup(html, features="html.parser")

    # TODO: remove stuff after "Notable links"
    # TODO: remove ads
    # TODO: remove header eg: "Friday 5th December issue is presented by Augment Code"
    return str(soup.find("tr", id="content-blocks"))


@click.command()
@click.option(
    "--max-concurrency",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    envvar="POINTER_MAX_CONCURRENCY",
)
@click.option(
    "--cache-dir",
    type=click.Path(path_type=trio.Path),
    default=trio.Path(".cache/pointer"),
    show_default=True,
    envvar="POINTER_CACHE_DIR",
)
def main(*, max_concurrency: int, cache_dir: trio.Path) -> None:
    _configure_logging()

    async def _main() -> None:
        async with httpx.AsyncClient(
            base_url=_BASE_URL,
            follow_redirects=True,
            timeout=httpx.Timeout(30),
        ) as client:
            _LOGGER.info("Get archives")
            resp = (await client.get("/archives/")).raise_for_status()
            _LOGGER.info("Parse response")
            soup = bs4.BeautifulSoup(resp.content, features="html.parser")
            article_tags = [a for a in soup.find_all("a") if isinstance(a, bs4.Tag) and _is_article_tag(a)]

            sem = trio.Semaphore(max_concurrency)
            rss_items: list[rss.Item] = []

            async def _worker(article_tag: bs4.Tag) -> None:
                async with sem:
                    item = await _article_tag_to_rss_item(article_tag=article_tag, client=client, cache_dir=cache_dir)
                rss_items.append(item)

            _LOGGER.info("Fetching %s articles", len(article_tags))
            async with trio.open_nursery() as nursery:
                for tag in article_tags:
                    nursery.start_soon(_worker, tag)

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
            items=rss_items,
        )

        # output RSS Feed to stdout
        _LOGGER.info("Writing RSS feed")
        ET.ElementTree(rss_doc.to_xml()).write(sys.stdout, encoding="unicode")

    trio.run(_main)


def _configure_logging() -> None:
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
                "level": os.getenv("LOG_LEVEL") or "INFO",
                "handlers": ["stderr"],
            },
            "loggers": {},
        }
    )


if __name__ == "__main__":
    main()
