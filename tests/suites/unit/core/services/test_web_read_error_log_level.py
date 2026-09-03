"""Regression test: WebReadAction error log level must be DEBUG.

When a URL fetch fails, the diagnostic message from WebReadAction
should be logged at DEBUG level so it does not appear on the user's
terminal at the default INFO log level.
"""

import logging

from teddy_executor.core.domain.models.action_ports import ActionPorts
from teddy_executor.core.services.action_factory import ActionFactory


class _MockFailingScraper:
    """Scraper that always raises an exception."""

    def get_content(self, url: str) -> str:
        raise Exception("404 Client Error: Not Found for url: " + url)


class _CapturingHandler(logging.Handler):
    """Logging handler that captures log records in memory."""

    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_web_read_error_log_level_is_debug_not_warning():
    """Regression test: the WebReadAction error log should be DEBUG level.

    When a URL fetch fails, the diagnostic message must be logged at DEBUG
    so that it is suppressed at the default INFO log level and does not
    appear on the user's terminal.
    """
    # Arrange
    ports = ActionPorts(
        shell_executor=None,
        file_system_manager=None,
        user_interactor=None,
        web_scraper=_MockFailingScraper(),
        web_searcher=None,
        config_service=None,
    )
    factory = ActionFactory(ports=ports)
    read_action = factory._create_read_action({"path": "https://example.com/fail"})

    # Use a mock logger to capture the log call
    logger = logging.getLogger("teddy_executor.core.services.action_factory")
    original_level = logger.level
    original_handlers = logger.handlers[:]
    try:
        # Set logger to DEBUG so we can capture calls
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        handler = _CapturingHandler()
        logger.addHandler(handler)

        # Act
        result = read_action.execute(path="https://example.com/fail")

        # Assert
        # The error string should still be returned
        assert "Error: Failed to fetch URL" in result

        # The log record should be at DEBUG level, not WARNING
        assert len(handler.records) == 1
        record = handler.records[0]
        assert record.levelno == logging.DEBUG, (
            f"Expected DEBUG level, got {logging.getLevelName(record.levelno)}. "
            "WARNING level would leak to stderr at default INFO configuration."
        )
        assert "Failed to fetch URL" in record.getMessage()
    finally:
        logger.level = original_level
        logger.handlers = original_handlers
