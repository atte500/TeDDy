from teddy_executor.core.domain.models.exceptions import (
    TeddyError,
    WebContentCacheError,
)


def test_web_content_cache_error_inherits_from_teddy_error():
    assert issubclass(WebContentCacheError, TeddyError)


def test_web_content_cache_error_carries_the_session_root():
    error = WebContentCacheError(
        "cannot persist cache", session_root=".teddy/sessions/demo"
    )

    assert str(error) == "cannot persist cache"
    assert error.session_root == ".teddy/sessions/demo"
