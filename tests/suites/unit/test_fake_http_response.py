"""Unit tests for the FakeHTTPResponse test helper."""

import json

from tests.harness.setup.fake_http_response import FakeHTTPResponse

PYPI_PAYLOAD = {"info": {"version": "1.0.0"}}


def test_fake_http_response_returns_json_with_status():
    """FakeHTTPResponse should simulate a urllib.response response with JSON body and status code."""
    response = FakeHTTPResponse(
        data=json.dumps(PYPI_PAYLOAD),
        status_code=200,
    )
    body = json.loads(response.read().decode("utf-8"))
    assert body == PYPI_PAYLOAD
    assert response.getcode() == 200
    assert response.headers is not None


def test_fake_http_response_supports_context_manager():
    """FakeHTTPResponse should be usable as a context manager (like urllib.request.urlopen)."""
    with FakeHTTPResponse(
        data=json.dumps(PYPI_PAYLOAD),
        status_code=200,
    ) as response:
        body = json.loads(response.read().decode("utf-8"))
        assert body == PYPI_PAYLOAD
