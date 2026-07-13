# Development

Contributor documentation for the Pointer.io RSS feed generator.

## Setup

Install runtime and dev dependencies:

```bash
uv sync --all-groups
```

## Running locally

```bash
uv run pointer-io-rssfeed > feed.xml
uv run pointer-io-rssfeed --help    # see all options
```

Fetched archive HTML is cached under `.cache/pointer/`, so repeat runs avoid
re-downloading the same pages.

## Project layout

- `src/pointer_io_rssfeed/cli.py` — CLI entrypoint and concurrent feed
  orchestration.
- `src/pointer_io_rssfeed/archive.py` — archive-index parsing into typed issue
  metadata.
- `src/pointer_io_rssfeed/fetch.py` — read-through filesystem cache for archive
  pages.
- `src/pointer_io_rssfeed/cleanup.py` — `html_to_description(html)`, where the
  article-HTML cleanup rules live and grow (stripping ads, the presenter
  header, the "Notable links" tail, etc.).
- `src/pointer_io_rssfeed/render.py` — readable XML serialization, CDATA, and
  HTML formatting for feed descriptions.
- `src/pointer_io_rssfeed/rss.py` — `attrs` data classes that model RSS 2.0.

## Testing

Run the test suite:

```bash
uv run pytest
```

### What's tested

The tests exercise `cleanup.html_to_description` against real archive pages
committed under `tests/fixtures/*.html`. Each fixture is auto-discovered by a
parametrized test in `tests/test_cleanup.py`, so coverage grows simply by adding
files.

### How snapshotting works

We use [syrupy](https://github.com/syrupy-project/syrupy) for snapshot testing.
For each fixture, the test:

1. Runs `cleanup.html_to_description(html)` on the raw page.
2. Pretty-prints the returned HTML (test-only — production output stays compact)
   so snapshots are readable and diffs are reviewable line-by-line.
3. Compares the result to the committed snapshot in
   `tests/__snapshots__/test_cleanup.ambr`.

The first time a test runs — or any time you intentionally change the cleanup
output — record the new snapshot:

```bash
uv run pytest --snapshot-update
```

On subsequent runs, `uv run pytest` fails if the output drifts from the recorded
snapshot. Review the diff: if the change is intended, re-run with
`--snapshot-update` to accept it; if not, you've caught a regression.

### Iteration loop

```bash
uv run pytest                      # validate against current snapshots
# tweak a rule in cleanup.py
uv run pytest                      # review the diff
uv run pytest --snapshot-update    # accept the new snapshots once happy
```

### Adding a fixture

1. Run the generator once so the page is cached, then copy a file from
   `.cache/pointer/` into `tests/fixtures/`.
2. The parametrized test picks it up automatically.
3. Record its snapshot with `uv run pytest --snapshot-update`.

A full `uv run pytest --snapshot-update` run also reports and removes orphaned
snapshots (e.g. after deleting a fixture).

## Linting & type checking

```bash
uv run ruff check          # lint
uv run ruff format         # auto-format (CI runs `--check` instead)
uv run mypy .              # type check (strict)
```

## CI

`.github/workflows/ci.yaml` runs `ruff check`, `ruff format --check`, `mypy .`,
and `pytest` on pushes to `main` and on pull requests. Run those four commands
locally before pushing to catch failures early.
