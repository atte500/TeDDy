# Slice: PDF Text Extraction for Local and Remote Reads
- **Status:** In Progress
- **Milestone:** Ad-hoc (00)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None; extraction behaviour is probed by the Harness deliverable
- **Component Docs:** [WebScraper](../../architecture/core/ports/outbound/web_scraper.md), [IFileSystemManager](../../architecture/core/ports/outbound/file_system_manager.md), [ActionFactory](../../architecture/core/services/action_factory.md)
- **Scope Slug:** `pdf-extraction`

## Goal
Make `READ` return extracted text when the target is a PDF, for both a local path and a remote URL, so agents stop receiving empty strings or mojibake. Remove the unused `playwright` dependency in the same slice.

## Context
- `ActionFactory._create_read_action`: routes `http*` to a `WebReadAction` wrapper, a `lines` parameter to a `LinesAwareReadAction` wrapper over `read_raw_file`, and everything else to `read_file`. A `.pdf` path falls through to `read_file`, which reads text as UTF-8 and therefore raises or returns garbage on binary PDF bytes.
- `IFileSystemManager`: `read_file` applies the `read.max_lines` cap through `truncate_lines`; `read_raw_file` returns the full UTF-8 text. Both return `str`; neither returns bytes, and no binary read exists on the port.
- `WebScraperAdapter._get_content_impl`: returns `""` when User-Agent rotation yields nothing or `trafilatura.extract` returns falsy. A PDF URL and a JavaScript shell both land here, silently violating the port's `fail_loud_on_error` invariant.
- `WebScraperAdapter` fetch helpers return decoded `str`, so a PDF payload cannot be recovered from the existing fetch path.
- `exceptions.py`: no `TeddyError` root exists. `WebSearchError` and `ConfigurationError` inherit `Exception`, `SearchTextNotFoundError` inherits `ValueError`, `FileAlreadyExistsError` inherits `FileExistsError`. The architecture law requires every new domain or boundary exception to inherit `TeddyError`.
- `ActionPorts`: a DTO grouping the outbound ports consumed by `ActionFactory`; adding a port requires updating both assembly sites in `container.py`.
- `pyproject.toml`: `playwright` is declared and locked in `uv.lock` but imported nowhere in `src/`, `tests/`, CI, or hooks. `pypdf` is absent.
- **Library choice:** `pypdf` is pure Python with no system dependency and reads through `PdfReader(BytesIO(data))`. It is preferred over `pdfminer.six` (heavier, slower) and `pymupdf` (binary wheel, AGPL). Import it lazily in a private getter per the Binary Stability law.

## Scenarios
> As an agent, I want a `READ` on a PDF to return its text so that I can analyse a document instead of retrying a fetch that silently produced nothing.

```gherkin
Given a local file report.pdf containing extractable text
When the plan READs report.pdf
Then the action result contains the document text
And no UnicodeDecodeError is raised
```

```gherkin
Given a remote URL ending in .pdf that serves a text PDF
When the plan READs that URL
Then the action result contains the document text
```

```gherkin
Given a local Python file
When the plan READs it
Then the action result is unchanged from today's behaviour
```

## Edge Cases
- **Corrupt payload**: If the bytes are not a parseable PDF, then raise `PdfExtractionError` with the path and parser reason, because a silent empty result is the defect this slice removes.
- **Image-only scan**: If extraction yields no text, then raise `PdfExtractionError` stating that the PDF has no text layer, because the caller must be able to tell a scan from an empty document.
- **Encrypted PDF**: If the parser requires a password, then raise `PdfExtractionError`, because prompting for a password is out of scope.
- **Extension without magic**: If a `.pdf` path's bytes do not start with `%PDF`, then raise `PdfExtractionError` naming the mismatch rather than decoding the file as text.
- **Uppercase extension**: If the path ends in `.PDF`, then treat it as a PDF, because extension matching is case-insensitive.
- **`lines` on a PDF**: If a READ carries both a PDF path and a `lines` range, then extract the full text and ignore the range, because page-relative line numbering is not meaningful; the port doc records the behaviour.
- **Cap**: If extracted text exceeds `read.max_lines`, then apply the same head truncation a text file receives, so a PDF obeys one budget rather than inventing a second.
- **Remote URL with query string**: If the URL reads `.../file.pdf?token=...`, then strip the query before the extension check, because signed URLs append parameters after the extension.

## Key Unknowns
- [ ] [Technical] pypdf real-world coverage: Does extraction return usable text for common layouts, and does it raise or return an empty string for scans and encryption? Design sensitivity: if it returns an empty string silently, the adapter must convert that to `PdfExtractionError`; if it raises typed errors, the adapter wraps them one-to-one.
- [ ] [Harness] Deterministic PDF fixture: Can a programmatically built minimal PDF with computed xref offsets parse under pypdf, or is a committed binary fixture required? Design sensitivity: a builder keeps the repo binary-free but must satisfy the parser; a committed fixture is simpler but adds a binary and a `.gitattributes` entry.
- [ ] [Domain] Cap semantics: Is `read.max_lines` meaningful for extracted PDF text? Design sensitivity: reusing it keeps one budget and one config key; a page or character cap needs a new key and a schema change.
- [ ] [Functional] Output shape: Should pages be separated by a visible marker or concatenated with blank lines? Design sensitivity: a marker is easier for the agent to cite but changes both the text the model sees and the fixture assertions.
- [ ] [Technical] Remote detection: Is the `.pdf` URL extension sufficient, or is a content-type or `%PDF` sniff required? Design sensitivity: extension-only misses `download?id=...`; content-type sniffing requires a bytes-returning fetch path in the adapter.
- [ ] [Harness] Driving the local PDF branch: Can the container fixture inject a fake `IPdfExtractor` so an acceptance test exercises the `.pdf` READ without global patching? Design sensitivity: if the port is injected through `ActionPorts`, the existing container fixture covers it; if not, a new harness seam is needed.

## Impact
1. `[NEW]` `TeddyError` root in `src/teddy_executor/core/domain/models/exceptions.py`, with `PdfExtractionError(TeddyError)` beside it. Existing exceptions are not re-parented here.
2. `[NEW]` `IPdfExtractor` outbound port and `PypdfExtractor` adapter.
3. `[EXTEND]` `IFileSystemManager.read_file_bytes` and its `LocalFileSystemAdapter` implementation.
4. `[EXTEND]` `ActionPorts.pdf_extractor`, wired at both `ActionPorts` assembly sites and the scraper registration.
5. `[EXTEND]` `WebScraperAdapter.__init__` accepts `pdf_extractor`.
6. `[MIGRATE]` `ActionFactory._create_read_action` routes `.pdf` paths through the extractor; `WebScraperAdapter._get_content_impl` routes `.pdf` URLs through the extractor.
7. `[MIGRATE]` `registries/infrastructure.py` injects the extractor into the scraper registration.
8. `[PRUNE]` `playwright` removed from `pyproject.toml` and `uv.lock`.

## Deliverables
- [x] **Env** - Remove `playwright` and add `pypdf` (current stable, bounded range) in `pyproject.toml`; regenerate `uv.lock`.
- [x] **Interface** - Add the `TeddyError` root, `PdfExtractionError`, the `IPdfExtractor` protocol, `read_file_bytes` on `IFileSystemManager`, and `pdf_extractor` on `ActionPorts`.
- [ ] **Harness** - Add a deterministic PDF fixture builder under `tests/harness/setup/`, prove pypdf extracts its text, and register a fake `IPdfExtractor` the container fixture can inject.
- [ ] **Wiring** - Route a local `.pdf` READ through the extractor in `ActionFactory` and assert the acceptance path returns text; non-PDF reads stay unchanged.
- [ ] **Core** - Implement the pure PDF detection predicate (case-insensitive extension plus `%PDF` magic) and the cap helper that reuses `truncate_lines` with `read.max_lines`, with unit tests for each edge case.
- [ ] **Adapter** - Implement `PypdfExtractor` with lazy import and typed failures, `LocalFileSystemAdapter.read_file_bytes`, and the `WebScraperAdapter` PDF branch; add the `pdf_extractor` and `pypdf_extractor` component docs.
- [ ] **Migration** - Inject `IPdfExtractor` at both `ActionPorts` assembly sites and the scraper registration; update `web_scraper.md` and `web_scraper_adapter.md` for the PDF branch and add both new docs to the Component Map in `docs/architecture/ARCHITECTURE.md`.

## Implementation Notes
- The remote branch raises `PdfExtractionError` for extraction failures only; network wrapping for every URL stays with Milestone 6's `WebScrapeError` item, which the widened roadmap bullet pins, so the two must land consistently.
- `web_scraper_adapter.py` already exceeds the 300-line gate; keep the PDF branch in a small private helper and record any further growth.
- The cap is applied by the core helper with `read.max_lines` read from `IConfigService`, so the PDF path and the text path share one budget and one config key.
- If the Harness probe shows pypdf cannot parse the builder's output, escalate to the Prototyper for a `spikes/pdf-extraction/` de-risk before continuing.
- **Env (delivered):** `playwright` sat bare on line 21 of `pyproject.toml` and was imported nowhere; it was replaced in place by `pypdf>=7.1.1,<8` (PyPI stable 7.1.1, `requires_python >=3.10`, inside the project's `>=3.11,<3.15` floor), leaving the unsorted dependency list order untouched to keep the commit atomic. `uv lock` + `uv sync` removed `playwright 1.61.0`, `greenlet`, and `pyee`, and added `pypdf 7.1.1`; `git grep -i playwright` over `pyproject.toml` and `uv.lock` now returns nothing. Full suite green afterwards (2416 passed, 5 skipped), as expected since neither package is imported by production or test code yet.
- **Interface (delivered):** `exceptions.py` gained `TeddyError` (the root base, un-parenting left to Milestone 6) and `PdfExtractionError(TeddyError)` carrying a `source` attribute so a failure can name the path or URL. `IPdfExtractor` landed as a `@runtime_checkable` protocol in its own module `core/ports/outbound/pdf_extractor.py`, mirroring the `web_scraper` precedent, and was exported from `core/ports/outbound/__init__.py` by import plus `__all__`. `read_file_bytes` was appended to `IFileSystemManager` as a declaration only; the port is not `@runtime_checkable` and grep finds no `isinstance` callers, so the addition is structurally inert until the Adapter implements it. `ActionPorts` received a trailing `pdf_extractor: Optional[IPdfExtractor] = None`, mirroring `config_service`, which keeps the field non-breaking and defers assembly-site wiring to Migration. Contract tests live in `test_pdf_extraction_error.py` (3 assertions) and `test_pdf_extractor_port.py` (6 assertions, including protocol satisfaction in both directions and the default/injected field behaviour). Red gate errored on the missing `PdfExtractionError`/`IPdfExtractor` imports; targeted Green run returned 10 passed (the nine new assertions plus the untouched `test_action_ports.py`); full suite green at 2424 passed, 5 skipped.

## Verification
1. **Local PDF:**
   Create a small text PDF, then READ it in a session.
   Verify the action result contains the document text and the report shows no error.
2. **Remote PDF:**
   READ a public `.pdf` URL.
   Verify the action result contains the document text.
3. **Non-PDF regression:**
   READ a `.py` file.
   Verify the result is unchanged.
4. **Broken PDF:**
   READ a truncated `.pdf`.
   Verify the report shows a `PdfExtractionError` message rather than an empty result.
5. **Dependency removal:**
   Run `uv tree | grep playwright`.
   Verify no match, and that `uv sync` no longer installs the browser package.
