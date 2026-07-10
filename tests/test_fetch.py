import httpx
import pytest

from pointer_io_rssfeed import _is_retryable_response


@pytest.mark.parametrize(
    ("status_code", "headers", "expected"),
    [
        (200, {}, False),
        (403, {}, False),
        (403, {"Cf-Mitigated": "challenge"}, True),
        (429, {}, True),
        (503, {}, True),
    ],
)
def test_is_retryable_response(*, status_code: int, headers: dict[str, str], expected: bool) -> None:
    response = httpx.Response(status_code, headers=headers, request=httpx.Request("GET", "https://example.com"))

    assert _is_retryable_response(response) is expected
