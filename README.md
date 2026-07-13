# Pointer.io RSS Feed

Previously, Pointer had a RSS feed available at <https://www.pointer.io/rss/>.
It stopped working at some point (May 2024 I think?).

It was last captured by the internet archive in Dec 2023
(<https://web.archive.org/web/20231202210100/https://www.pointer.io/rss/>).

This project scrapes <https://www.pointer.io/archives/> (1x daily) and outputs
a RSS feed.

Each RSS item includes:

- the issue title (e.g. "Issue #691")
- a link to the archive page
- the publication date
- a clean, RSS-reader-friendly `<description>` containing the editorial HTML
  from the archive page (without email CSS, layout tables, ads, or feedback
  controls)

The generator fetches archive pages concurrently (bounded by `--max-concurrency`) and caches
fetched HTML in a local directory so subsequent runs avoid re-downloading the same pages.

## Usage

```bash
uv run pointer-io-rssfeed > feed.xml
```

### Options

```bash
uv run pointer-io-rssfeed --help
```

Options can also be set via environment variables:

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for contributor and testing docs.
