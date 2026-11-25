# Component Design: WebScraper
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/outbound/web_scraper.py`](/src/teddy_executor/core/ports/outbound/web_scraper.py)

## Purpose
Defines the outbound port for fetching and converting remote web content to Markdown. It abstracts the HTTP client and extraction library from the core.

## Consumers
- [`WebContentService`](../../services/web_content_service.md): The only caller, fetching each remote body verbatim before caching it and capping the value it returns.

## Dependencies
None — this port declares no injected dependencies.

## Class Invariants
- `runtime_checkable`: The protocol supports `isinstance` checks.
- `fail_loud_on_error`: Network, timeout, and non-2xx failures must raise a catchable exception, never return empty content silently.
- `pdf_returns_text`: A PDF source yields the document's text layer, never a Markdown conversion of its bytes.
- `verbatim_bodies`: A returned body is the fetch's full extracted text. The port applies no line cap, so `read.max_lines` stays the cache-aware coordinator's single responsibility.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`WebScraper`**: The driven contract consumed by `WebContentService` and implemented by the `WebScraperAdapter`.

## Data Contracts
- **Body:** the fetch's full extracted text, uncapped. A caller that needs the `read.max_lines` budget applies it itself.
- **PDF source:** a URL whose path ends in `.pdf` is a PDF read, matched case-insensitively and with any query string or fragment ignored.

## Operations

### `get_content(url, **_kwargs) -> str`
- **Preconditions:** `url` is a well-formed absolute URL.
- **Postconditions:** Returns the page content as Markdown text, untruncated. A PDF source returns the document's extracted text layer instead.
- **Exceptions:** Raises a web-content error for network failures and non-2xx responses.
