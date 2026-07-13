from __future__ import annotations

from click.testing import CliRunner

from pointer_io_rssfeed.cli import main


def test_help_shows_option_defaults_and_environment_variables() -> None:
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "[env var: MAX_CONCURRENCY; default: 5; x>=1]" in result.output
    assert "[env var: CACHE_DIR; default: .cache/pointer]" in result.output
    assert "[env var: LOG_LEVEL; default: INFO]" in result.output
