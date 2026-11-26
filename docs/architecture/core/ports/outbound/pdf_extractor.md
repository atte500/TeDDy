# Component Design: IPdfExtractor
- **Status:** Implemented
- **Classification:** Core Outbound Port
- **Source:** [`src/teddy_executor/core/ports/outbound/pdf_extractor.py`](/src/teddy_executor/core/ports/outbound/pdf_extractor.py)

## Purpose
Defines the outbound port for turning raw PDF bytes into extracted text. It keeps the core independent of the parsing library, so extraction can be faked in tests and swapped without touching a caller.

## Consumers
- [`ActionFactory`](../../services/action_factory.md): Builds the local PDF `READ` handler that calls the port.
- [`WebScraperAdapter`](../../../adapters/outbound/web_scraper_adapter.md): Calls the port for a remote PDF URL.
- [`ActionPorts`](../../domain/action_ports.md): Carries the port into the action layer.

## Dependencies
None — this port declares no injected dependencies.

## Class Invariants
- `runtime_checkable`: The protocol supports `isinstance` checks.
- `fail_loud_on_error`: An unparseable, encrypted, or text-less payload raises `PdfExtractionError`; returning an empty string silently is forbidden, because that silent result is the defect the port exists to remove.
- `source_named_on_failure`: Every failure carries the path or URL the payload came from, so a caller can report where the document lived.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`IPdfExtractor`**: The driven contract consumed by the action layer and the scraper, implemented by the [PypdfExtractor](../../../adapters/outbound/pypdf_extractor.md).

## Data Contracts
- **`PdfExtractionError`** (`TeddyError`): The single failure type for extraction, with a `source` attribute naming the path or URL.

## Operations

### `extract_text(data, source) -> str`
- **Preconditions:** `data` holds the raw bytes of a PDF document; `source` names the local path or URL the bytes came from.
- **Postconditions:** Returns the document's extracted text layer.
- **Exceptions:**
  - `PdfExtractionError`: The payload lacks the `%PDF` magic bytes, cannot be parsed, is encrypted, or carries no extractable text layer.
