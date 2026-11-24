# Slice: PDF Text Extraction for Local and Remote Reads
- **Status:** In Progress
- **Milestone:** Ad-hoc (00)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None; extraction behaviour is probed by the Harness deliverable
- **Component Docs:** [WebScraper](../../architecture/core/ports/outbound/web_scraper.md), [IFileSystemManager](../../architecture/core/ports/outbound/file_system_manager.md), [ActionFactory](../../architecture/core/services/action_factory.md), [IPdfExtractor](../../architecture/core/ports/outbound/pdf_extractor.md), [PypdfExtractor](../../architecture/adapters/outbound/pypdf_extractor.md)
- **Scope Slug:** `pdf-extraction`

## Goal
Make `READ` return extracted text when the target is a PDF, for both a local path and a remote URL, so agents stop receiving empty strings or mojibake. Remove the unused `playwright` dependency in the same slice.

## Context
- `ActionFactory._create_read_action`: routes `http*` to a `WebReadAction` wrapper, a `lines` parameter to a `LinesAwareReadAction` wrapper over `read_raw_file`, and everything else to `read_file`. A `.pdf` path falls through to `read_file`, which reads text as UTF-8 and therefore raises or returns garbage on binary PDF bytes.
- `IFileSystemManager`: `read_file` applies the `read.max_lines` cap through `truncate_lines`; `read_raw_file` returns the full UTF-8 text. Both return `str`; neither returns bytes, and no binary read exists on the port.
- `WebScraperAdapter._get_content_impl`: returns `""` when User-Agent rotation yields nothing or `trafilatura.extract` returns falsy. A PDF URL and a JavaScript shell both land here, silently violating the port's `fail_loud_on_error` invariant.
- `WebScraperAdapter` fetch helpers return decoded `str`, so a PDF payload cannot be recovered from the existing fetch path.
- `exceptions.py`: no `TeddyError` root exists. `WebSearchError` and `ConfigurationError` inherit `Exception`, `SearchTextNotFoundError` inherits `ValueError`, `FileAlreadyExistsError` inherits `FileExistsError`. The architecture law requires every new domain or boundary exception to inherit `TeddyError`.
- `ActionPorts`: a DTO grouping the outbound ports consumed by `ActionFactory`; adding a port requires updating the production assembly site in `container.py`.
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
4. `[EXTEND]` `ActionPorts.pdf_extractor`, wired at the single production `ActionPorts` assembly site in `container.py` plus the scraper registration.
5. `[EXTEND]` `WebScraperAdapter.__init__` accepts `pdf_extractor`.
6. `[MIGRATE]` `ActionFactory._create_read_action` routes `.pdf` paths through the extractor; `WebScraperAdapter._get_content_impl` routes `.pdf` URLs through the extractor.
7. `[MIGRATE]` `registries/infrastructure.py` injects the extractor into the scraper registration.
8. `[PRUNE]` `playwright` removed from `pyproject.toml` and `uv.lock`.

## Deliverables
- [x] **Env** - Remove `playwright` and add `pypdf` (current stable, bounded range) in `pyproject.toml`; regenerate `uv.lock`.
- [x] **Interface** - Add the `TeddyError` root, `PdfExtractionError`, the `IPdfExtractor` protocol, `read_file_bytes` on `IFileSystemManager`, and `pdf_extractor` on `ActionPorts`.
- [x] **Harness** - Add a deterministic PDF fixture builder under `tests/harness/setup/`, prove pypdf extracts its text, and register a fake `IPdfExtractor` the container fixture can inject.
- [x] **Wiring** - Route a local `.pdf` READ through the extractor in `ActionFactory` and assert the acceptance path returns text; non-PDF reads stay unchanged.
- [x] **Core** - Implement the pure PDF detection predicate (case-insensitive extension plus `%PDF` magic) and the cap helper that reuses `truncate_lines` with `read.max_lines`, with unit tests for each edge case.
- [x] **Adapter** - Implement `PypdfExtractor` with a lazy `pypdf` import inside a private getter, a `require_pdf_magic` guard before parsing, and typed `PdfExtractionError` failures for corrupt, encrypted, and text-less payloads; implement `LocalFileSystemAdapter.read_file_bytes`; add the `WebScraperAdapter` PDF branch as a small private helper; replace `ActionFactory`'s naked `.pdf` suffix check with `is_pdf_source` and route the extracted text through `cap_extracted_text` with `read.max_lines`; add the `pdf_extractor` and `pypdf_extractor` component docs.
- [x] **Migration** - Inject `IPdfExtractor` at the production `ActionPorts` assembly site and the scraper registration; update `web_scraper.md` and `web_scraper_adapter.md` for the PDF branch and add both new docs to the Component Map in `docs/architecture/ARCHITECTURE.md`.

## Implementation Notes
- The remote branch raises `PdfExtractionError` for extraction failures only; network wrapping for every URL stays with Milestone 6's `WebScrapeError` item, which the widened roadmap bullet pins, so the two must land consistently.
- `web_scraper_adapter.py` already exceeds the 300-line gate; keep the PDF branch in a small private helper and record any further growth.
- The cap is applied by the core helper with `read.max_lines` read from `IConfigService`, so the PDF path and the text path share one budget and one config key.
- If the Harness probe shows pypdf cannot parse the builder's output, escalate to the Prototyper for a `spikes/pdf-extraction/` de-risk before continuing.
- **Env (delivered):** `playwright` sat bare on line 21 of `pyproject.toml` and was imported nowhere; it was replaced in place by `pypdf>=7.1.1,<8` (PyPI stable 7.1.1, `requires_python >=3.10`, inside the project's `>=3.11,<3.15` floor), leaving the unsorted dependency list order untouched to keep the commit atomic. `uv lock` + `uv sync` removed `playwright 1.61.0`, `greenlet`, and `pyee`, and added `pypdf 7.1.1`; `git grep -i playwright` over `pyproject.toml` and `uv.lock` now returns nothing. Full suite green afterwards (2416 passed, 5 skipped), as expected since neither package is imported by production or test code yet.
- **Interface (delivered):** `exceptions.py` gained `TeddyError` (the root base, un-parenting left to Milestone 6) and `PdfExtractionError(TeddyError)` carrying a `source` attribute so a failure can name the path or URL. `IPdfExtractor` landed as a `@runtime_checkable` protocol in its own module `core/ports/outbound/pdf_extractor.py`, mirroring the `web_scraper` precedent, and was exported from `core/ports/outbound/__init__.py` by import plus `__all__`. `read_file_bytes` was appended to `IFileSystemManager` as a declaration only; the port is not `@runtime_checkable` and grep finds no `isinstance` callers, so the addition is structurally inert until the Adapter implements it. `ActionPorts` received a trailing `pdf_extractor: Optional[IPdfExtractor] = None`, mirroring `config_service`, which keeps the field non-breaking and defers assembly-site wiring to Migration. Contract tests live in `test_pdf_extraction_error.py` (3 assertions) and `test_pdf_extractor_port.py` (6 assertions, including protocol satisfaction in both directions and the default/injected field behaviour). Red gate errored on the missing `PdfExtractionError`/`IPdfExtractor` imports; targeted Green run returned 10 passed (the nine new assertions plus the untouched `test_action_ports.py`); full suite green at 2424 passed, 5 skipped.
- **Harness (delivered):** `tests/harness/setup/pdf_fixture.py` exposes `build_minimal_pdf(text=DEFAULT_PDF_TEXT)` — an uncompressed five-object PDF with hand-computed xref offsets, built in-repo so no binary fixture is committed; `text` must not contain raw parentheses, which would terminate the PDF string literal early. `tests/harness/setup/fake_pdf_extractor.py` holds `FakePdfExtractor`, a hand-rolled in-memory double that returns a fixed text layer and records every call as a `list[tuple[bytes, str]]`, so Wiring can assert both the result and the exact bytes/source that reached the port. `mocks.py` adds a `fake_pdf_extractor` fixture that registers it via `container.register(IPdfExtractor, instance=fake)`, re-exported through `composition.py` and published by `tests/conftest.py`. The gate is pinned permanently by `tests/suites/unit/test_pdf_fixture_harness.py`: three parameterized texts prove pypdf 7.1.1 extracts the builder's text verbatim, the magic check pins `%PDF-`, and the fake's behaviour plus container identity are asserted. The builder approach was first proven empirically in the Harness orientation probe (BytesIO and a temp file both extracting `'Hello PDF'`). The first Green run returned 5 passed, 1 error because `fake_pdf_extractor` was invisible to pytest; `tests/conftest.py` publishes composition fixtures through an explicit import list plus `__all__`, and both omitted the new name, so extending both made it discoverable (targeted rerun 6 passed). Full suite green at 2430 passed, 5 skipped.
- **Wiring (delivered):** `ActionFactory.__init__` now stores `ports.pdf_extractor`, and `_create_read_action` routes a resource whose lowercased name ends in `.pdf` to a new private `_create_pdf_read_action` helper placed before the `lines` branch, so a PDF read ignores a line range (matching the slice's `lines`-on-a-PDF edge case). The helper reads bytes via `IFileSystemManager.read_file_bytes` and delegates to `IPdfExtractor.extract_text`, guarded by `assert extractor is not None, "pdf_extractor port is required for a local PDF read"` (a contract assertion, not input validation). Detection here is deliberately naive — extension-only, no `%PDF` sniff, no `read.max_lines` cap — because robust detection and the cap are the Core deliverable; the Production Double Audit must confirm nothing skeleton survives once Core lands. The tracer bullet assembles `ActionFactory` directly from an explicit `ActionPorts` carrying the `FakePdfExtractor`, not via the container, whose production `pdf_extractor` stays `None` until Migration. Acceptance test `tests/suites/acceptance/test_local_pdf_read_wiring.py` drives the house-style `create_action("READ", ...).execute(...)` chain: Red returned 1 failed, 1 passed (the PDF read fell through to `read_file`, returning a `POSIXPathMock`); Green returned 2 passed (PDF returns the fake's `"Quarterly Report body"` and records `[(payload, "report.pdf")]`, while a `.py` read returns `read_file`'s value with zero extractor calls). Full suite green at 2432 passed, 5 skipped.

- **Core (delivered):** `core/utils/pdf.py` holds the four pure helpers: `is_pdf_source` strips the query string and fragment before a case-insensitive `.pdf` check, so a signed `file.pdf?token=...` URL matches while `download?id=5`, `report.pdf.txt`, and an empty string do not; `has_pdf_magic`/`require_pdf_magic` pin the `%PDF-` prefix and raise `PdfExtractionError` carrying `source`, so the failure names the path or URL; `cap_extracted_text` delegates to `truncate_lines(..., direction="head", action_type="read")`, so a PDF and a text file share one budget and one config key and emit the identical truncation hint. `tests/suites/unit/core/utils/test_pdf_utils.py` parameterizes the slice's detection edge cases (uppercase and mixed-case extensions, nested path, signed URL, fragment URL; rejects `.txt`, `.pdf.txt`, bare name, query-only URL, empty string), pins the magic check in both directions, pins the error's `source` attribute and `%PDF` message text, and asserts the cap equals the shared `truncate_lines` output rather than a re-derived literal. The pair arrived untracked from the previous session with no recorded run, so this session supplied the empirical gate: targeted module 20 passed, full suite 2452 passed and 5 skipped, exactly +20 over Wiring's 2432. The helpers have no production caller yet; the Adapter deliverable is scoped to adopt `require_pdf_magic` in `PypdfExtractor` and `is_pdf_source`/`cap_extracted_text` in `ActionFactory`, so the Production Double Audit finds neither dead code nor shadow detection.

- **Adapter (delivered):** `adapters/outbound/pypdf_extractor.py` is byte-in/text-out with no configuration: `_get_pypdf` lazily imports `pypdf`, `require_pdf_magic` runs before the parser is constructed, the `is_encrypted` pre-check raises with a password message (Turn 11 proved `PdfReader` builds fine on the RC4-128 fixture and only `.pages` raises `FileNotDecryptedError`), a single `PyPdfError` translation covers the corrupt case (`PdfStreamError` at construction) as well as any later parse failure, and a whitespace-strip check turns the empty-text fixture's `''` into the text-layer error. Pages join with a bare `\n` and no page marker, which settles the slice's open output-shape unknown in favour of the shape the model reads most plainly. `LocalFileSystemAdapter.read_file_bytes` mirrors `read_raw_file`'s error shape — `FileNotFoundError` re-raised, every other `IOError` wrapped with the path — so existing degradation paths behave identically. `WebScraperAdapter` gained a `pdf_extractor` parameter with an explicit `| None` annotation, which incidentally removed the bare `# type: ignore` that had been guarding `config_service`; `_handle_pdf` asserts the port, fetches through `_fetch_pdf_bytes` (transient retries across the three `requests` failure classes, with an asserted `last_error` so the budget can never return `None`), extracts with the full URL as `source`, and reuses `_truncate_content` when `truncate` is true, so the remote cap stays the adapter's own rather than re-deriving `read.max_lines`; the dispatch sits at the top of `_get_content_impl`, ahead of the GitHub and rotation paths, so a PDF never reaches `trafilatura`. Because `_fetch_pdf_bytes` would have been a third verbatim copy of the retry-budget lookup, that block collapsed into `_max_scraper_retries()` with `int(val)` semantics preserved exactly — a configured `0` is still honoured rather than clamped. `ActionFactory` imports `coerce_param` at module scope (two function-local imports dropped), detects with `is_pdf_source` so signed and fragment URLs route correctly, and resolves the cap once at action-creation time in `_resolve_read_max_lines`: `get_setting("read.max_lines", None)` through `coerce_param(raw, int)`, returning `None` for absent, non-integer, or non-positive values, so the committed acceptance wiring test — whose fixture returns the caller default of `None` — keeps its verbatim text. The first Green plan was rejected pre-execution for an ambiguous `FIND` (the retry block appeared twice at similarity 1.0000); both sites are now anchored on their distinguishing trailing lines, which is why the same-code resubmission validated cleanly. Red was 11 failed / 13 passed / 6 errors, every failure traced to the missing module, keyword, method, or adoption; Green returned 30 passed across `test_pypdf_extractor.py` (7), `test_web_scraper_pdf.py` (6), `test_action_factory_pdf_read.py` (5), and the extended `test_file_system_adapter_contract.py` (12), with the full suite at 2472 passed and 5 skipped. `tests/harness/setup/pdf_fixture.py` gained `build_encrypted_pdf`, which writes an RC4-128-encrypted document using a default password, importing pypdf inside the function so only the encrypted-branch test pays that import.

- **Migration (delivered):** The briefing's "both assembly sites in `container.py`" premise had gone stale: `git grep "ActionPorts("` found exactly one production construction, inside `_register_services`, with every other hit in tests. Wiring therefore touched three seams. `registries/infrastructure.py` registers `IPdfExtractor` → `PypdfExtractor` at `punq.Scope.transient` in the file's own idiom, and the `IWebScraper` factory switched to keyword arguments so it supplies both collaborators while keeping the late-bound resolution the incumbent code depends on (`IConfigService` is registered after the scraper, which only works because resolution happens when the factory runs). The single production `ActionPorts` site gained `pdf_extractor=container.resolve(IPdfExtractor)`. `with_real_web_scraper` in the harness mixin deliberately still registers the bare class, so punq auto-resolves both constructor keywords to `None`; that integration path carries no PDF coverage and injecting there would have widened the deliverable. Composition coverage extends the existing `tests/suites/integration/core/services/test_container_wiring.py` instead of adding a file, because Migration adapts consumers rather than introducing behaviour: three assertions drive `create_container()` directly — the extractor resolves to a real `PypdfExtractor`, the resolved scraper extracts `Hello PDF` from the harness fixture with only `_fetch_pdf_bytes` replaced, and the resolved factory reads `Quarterly Report` off disk through `LocalFileSystemAdapter` → `IPdfExtractor` → the `read.max_lines` cap. Turn 21's probe had already observed the three Red surfaces in-process (`punq.MissingDependencyError`, then the two contract assertions), Turn 23 reproduced them through pytest at 3 failed / 4 passed, and Green returned 7 passed; the unfiltered suite moved 2472 → 2475 passed with 5 skipped, exactly the three new assertions.

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
