"""Regression test: WebReadAction error log level must be DEBUG.

When a URL fetch fails, the diagnostic message from WebReadAction
should be logged at DEBUG level so it does not appear on the user's
terminal at the default INFO log level.
"""

import logging

from teddy_executor.core.domain.models.action_ports import ActionPorts
from teddy_executor.core.services.action_factory import ActionFactory
from teddy_executor.core.services.web_content_service import WebContentService
from tests.harness.setup.fake_web_content_cache import FakeWebContentCache
from tests.harness.setup.fake_web_scraper import FakeWebScraper

FACTORY_LOGGER = "teddy_executor.core.services.action_factory"
FAILING_URL = "https://example.com/fail"
FETCH_FAILURE = Exception("404 Client Error: Not Found for url: " + FAILING_URL)


def _build_factory() -> ActionFactory:
    """A factory whose coordinator re-raises the scraper's fetch failure."""
    ports = ActionPorts(
        shell_executor=None,
        file_system_manager=None,
        user_interactor=None,
        web_searcher=None,
    )
    coordinator = WebContentService(
        web_scraper=FakeWebScraper(failures={FAILING_URL: FETCH_FAILURE}),
        cache=FakeWebContentCache(),
    )
    return ActionFactory(ports=ports, web_content_service=coordinator)


def test_web_read_error_log_level_is_debug_not_warning(caplog):
    """A failed URL fetch logs its diagnostic at DEBUG, never at WARNING."""
    factory = _build_factory()
    read_action = factory.create_action("READ", {"path": FAILING_URL})

    with caplog.at_level(logging.DEBUG, logger=FACTORY_LOGGER):
        result = read_action.execute(path=FAILING_URL)

    assert "Error: Failed to fetch URL" in result

    records = [record for record in caplog.records if record.name == FACTORY_LOGGER]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.DEBUG, (
        f"Expected DEBUG level, got {logging.getLevelName(record.levelno)}. "
        "WARNING level would leak to stderr at default INFO configuration."
    )
    assert "Failed to fetch URL" in record.getMessage()
