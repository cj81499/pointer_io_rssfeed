import datetime
import logging
import logging.config
import os
import sys

import bs4
import httpx

# Consider replacing PyRSS2Gen w/ a custom RSS module. I can't find a good OSS lib.
import PyRSS2Gen  # type: ignore[import-untyped]
import trio

_BASE_URL = "https://www.pointer.io/"
_LOGGER = logging.getLogger(__name__)


def _article_tag_to_rss_item(article_tag: bs4.Tag) -> PyRSS2Gen.RSSItem:
    # TODO: fetch and include article body
    return PyRSS2Gen.RSSItem(
        title=article_tag.find("h2").text.strip(),
        link=article_tag.get("href"),
        pubDate=article_tag.find("time").text.strip(),
    )


def _is_article_tag(tag: bs4.Tag) -> bool:
    href = tag.get("href")
    if not isinstance(href, str):
        _LOGGER.warning("tag href must be a str. tag=%s href=%s", tag, href)
        return False
    return href.startswith("/archives/")


def main() -> None:
    _configure_logging()

    async def _main() -> None:
        base_url = httpx.URL(_BASE_URL)
        async with httpx.AsyncClient(base_url=base_url) as client:
            _LOGGER.info("Get archives")
            resp = (await client.get("/archives/")).raise_for_status()
            _LOGGER.info("Parse response")
            soup = bs4.BeautifulSoup(resp.content, features="html.parser")
            article_tags = [a for a in soup.find_all("a") if isinstance(a, bs4.Tag) and _is_article_tag(a)]
            _LOGGER.info("Found %s article_tags", len(article_tags))
            rss_items = list(map(_article_tag_to_rss_item, article_tags))
        _LOGGER.info("Got %s articles", len(rss_items))

        _LOGGER.info("Building RSS Feed")
        rss = PyRSS2Gen.RSS2(
            title="Pointer",
            link=_BASE_URL,
            image=PyRSS2Gen.Image(
                url="https://www.pointer.io/static/apple-touch-icon.png", title="Pointer", link=_BASE_URL
            ),
            description="EssentialEssential Reading For Engineering Leaders",
            lastBuildDate=datetime.datetime.now(tz=datetime.UTC),
            items=rss_items,
        )

        # output RSS Feed to stdout
        _LOGGER.info("Writing RSS feed")
        rss.write_xml(sys.stdout)

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
