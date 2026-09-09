"""Regression test: trafilatura "discarding data: None" warning suppression.

Our WebScraperAdapter calls trafilatura.extract() without a url parameter.
When extraction fails, trafilatura logs "discarding data: None". We want this
log to show the actual URL instead of "None" — or be suppressed entirely.
"""

import io
import logging


class TestTrafilaturaDiscardingDataWarning:
    """Verifies that trafilatura's warning log includes a meaningful URL."""

    def test_discard_warning_shows_url_not_none(self):
        """When extraction fails with a URL passed, the warning should show the URL."""
        # Capture trafilatura's log output
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.WARNING)
        trafilatura_logger = logging.getLogger("trafilatura")
        trafilatura_logger.addHandler(handler)
        trafilatura_logger.setLevel(logging.WARNING)

        try:
            # Extract with valid URL but empty content (triggers discard warning)
            import trafilatura

            trafilatura.extract(
                "",
                url="https://example.com/test-page",
                output_format="markdown",
                include_links=True,
                include_formatting=True,
            )
        finally:
            trafilatura_logger.removeHandler(handler)

        output = log_capture.getvalue()
        # The warning should contain the URL, not "None"
        assert "discarding data: None" not in output, (
            f"Warning should not show 'None': got '{output.strip()}'"
        )
        assert (
            "discarding data: https://example.com/test-page" in output or not output
        ), f"Warning should show meaningful URL if emitted, got: {output.strip()}"

    def test_empty_content_no_url_produces_none_warning(self):
        """Baseline: without URL, the warning shows 'None' (this is the bug pattern)."""
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.WARNING)
        trafilatura_logger = logging.getLogger("trafilatura")
        trafilatura_logger.addHandler(handler)
        trafilatura_logger.setLevel(logging.WARNING)

        try:
            import trafilatura

            trafilatura.extract(
                "",
                output_format="markdown",
                include_links=True,
                include_formatting=True,
            )
        finally:
            trafilatura_logger.removeHandler(handler)

        output = log_capture.getvalue()
        # Without URL, the warning shows "None"
        assert "discarding data: None" in output, (
            f"Expected 'discarding data: None' in output but got: {output.strip()}"
        )
