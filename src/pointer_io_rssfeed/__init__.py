import datetime
import logging
import logging.config
import os
import sys
import xml.etree.ElementTree as ET
import zoneinfo

import bs4
import httpx
import trio

from pointer_io_rssfeed import rss

_BASE_URL = httpx.URL("https://www.pointer.io/")
_LOGGER = logging.getLogger(__name__)
_NY_ZONE_INFO = zoneinfo.ZoneInfo("America/New_York")


def _article_tag_to_rss_item(article_tag: bs4.Tag) -> rss.Item:
    h2 = article_tag.find("h2")
    assert isinstance(h2, bs4.Tag)
    href = article_tag.get("href")
    assert isinstance(href, str)
    time = article_tag.find("time")
    assert isinstance(time, bs4.Tag)

    # consider fetching and including article body

    pub_date = datetime.datetime.strptime(time.text.strip(), "%B %d, %Y").replace(
        # Pointer is typically released around 9am NY time
        hour=9,
        tzinfo=_NY_ZONE_INFO,
    )

    return rss.Item(
        title=h2.text.strip(),
        link=rss.URL(str(_BASE_URL.join(href))),
        pub_date=pub_date,
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
        async with httpx.AsyncClient(base_url=_BASE_URL) as client:
            _LOGGER.info("Get archives")
            resp = (await client.get("/archives/")).raise_for_status()
            _LOGGER.info("Parse response")
            soup = bs4.BeautifulSoup(resp.content, features="html.parser")
            article_tags = [a for a in soup.find_all("a") if isinstance(a, bs4.Tag) and _is_article_tag(a)]
            _LOGGER.info("Found %s article_tags", len(article_tags))
            rss_items = list(map(_article_tag_to_rss_item, article_tags))
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
            description="EssentialEssential Reading For Engineering Leaders",
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
