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
- `pdf_returns_text`: A PDF source yields the document's text layer, never a Markdown conversion of its bytes.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`WebScraper`**: The driven contract consumed by the action layer and implemented by the `WebScraperAdapter`.

## Data Contracts
- **`truncate` flag:** when `True` (default) the adapter applies the `read.max_lines` cap; context assembly passes `False` for verbatim content.
- **PDF source:** a URL whose path ends in `.pdf` is a PDF read, matched case-insensitively and with any query string or fragment ignored.

## Operations

### `get_content(url, truncate=True, **_kwargs) -> str`
- **Preconditions:** `url` is a well-formed absolute URL.
- **Postconditions:** Returns the page content as Markdown text. A PDF source returns the document's extracted text layer instead, capped by `read.max_lines` when `truncate` is `True`.
- **Exceptions:** Raises a web-content error for network failures and non-2xx responses.
