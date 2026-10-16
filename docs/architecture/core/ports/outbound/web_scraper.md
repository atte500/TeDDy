# Component Design: WebScraper
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/outbound/web_scraper.py`](/src/teddy_executor/core/ports/outbound/web_scraper.py)

## Purpose
Defines the outbound port for fetching and converting remote web content to Markdown. It abstracts the HTTP client and extraction library from the core.

## Consumers
- [`ActionFactory`](../../services/action_factory.md): Builds `WEB_READ` actions that call the port.

## Dependencies
None — this port declares no injected dependencies.

## Class Invariants
- `runtime_checkable`: The protocol supports `isinstance` checks.
- `fail_loud_on_error`: Network, timeout, and non-2xx failures must raise a catchable exception, never return empty content silently.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`WebScraper`**: The driven contract consumed by the action layer and implemented by the `WebScraperAdapter`.

## Data Contracts
- **`truncate` flag:** when `True` (default) the adapter applies the `read.max_lines` cap; context assembly passes `False` for verbatim content.

## Operations

### `get_content(url, truncate=True, **_kwargs) -> str`
- **Preconditions:** `url` is a well-formed absolute URL.
- **Postconditions:** Returns the page content as Markdown text.
- **Exceptions:** Raises a web-content error for network failures and non-2xx responses.
