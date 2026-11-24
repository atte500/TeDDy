# Component Design: PypdfExtractor
- **Status:** Implemented
- **Source:** [`src/teddy_executor/adapters/outbound/pypdf_extractor.py`](/src/teddy_executor/adapters/outbound/pypdf_extractor.py)

## Purpose
Implements `IPdfExtractor` using `pypdf`, translating every parse outcome into a typed `PdfExtractionError` that names the originating path or URL.

## Consumers
- [`ActionFactory`](../../core/services/action_factory.md): Extracts text for a local PDF `READ`.
- [`WebScraperAdapter`](./web_scraper_adapter.md): Extracts text for a remote PDF URL.

## Dependencies
- [`IPdfExtractor`](../../core/ports/outbound/pdf_extractor.md): The driven contract this adapter implements.
- **`require_pdf_magic`** (`teddy_executor.core.utils.pdf`): Rejects a PDF-named payload without the `%PDF-` header before the parser is constructed.
- **`PdfExtractionError`** (`teddy_executor.core.domain.models.exceptions`): The typed failure carrying `source`.
- **`pypdf`** (external): The parser; imported lazily inside `_get_pypdf`.

## Class Invariants
- `lazy_heavy_imports`: `pypdf` loads only inside `_get_pypdf`, so importing this module costs nothing at CLI startup.
- `magic_before_parse`: The `%PDF-` header is checked before `PdfReader` is built, so a misnamed binary file fails with the mismatch message rather than a parser error.
- `encrypted_pre_check`: A readable-but-encrypted document is detected through `is_encrypted` and reported as a password requirement, because page access raises `FileNotDecryptedError` rather than construction.
- `single_typed_failure`: Every parse outcome surfaces as `PdfExtractionError` carrying `source`; a third-party `PyPdfError` never crosses the port.
- `text_layer_required`: A payload whose text layer is empty or whitespace-only is a failure, so a caller can tell a scan from an empty document.
- `pages_join_with_newline`: Pages are concatenated with a single `\n` and no page marker.

## Inbound Ports
None — this is an outbound (driven) adapter.

## Outbound Ports
- **`IPdfExtractor`**: The driven contract implemented by this adapter.

## Data Contracts
- **`PdfExtractionError`** (`TeddyError`): Raised for a magic-byte mismatch, an encrypted document, a `pypdf` parse failure, or a missing text layer; `source` names the path or URL.
- **Payload origin:** local reads supply bytes from [`IFileSystemManager.read_file_bytes`](../../core/ports/outbound/file_system_manager.md); remote reads supply the raw response body from the scraper's byte fetch.

## Operations

### `extract_text(data, source) -> str`
- **Preconditions:** `data` is non-empty bytes; `source` names the path or URL.
- **Postconditions:** Returns the concatenated text of every page, joined by `\n`.
- **Exceptions:**
  - `PdfExtractionError`: The payload does not start with `%PDF`; or the reader reports the document as encrypted, so a password is required; or `pypdf` raises a `PyPdfError`, whose message is wrapped and chained; or the extracted text is empty after stripping whitespace, meaning there is no text layer.

### Internal helpers
`_get_pypdf` imports and returns the `pypdf` module on first use.
