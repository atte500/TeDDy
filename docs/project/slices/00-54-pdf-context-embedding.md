# Slice: PDF-Aware Context Embedding
- **Status:** Planned
- **Milestone:** Ad-hoc (00)
- **Depends On:** None
- **Specs:** None
- **Prototype:** [Case file: PDF Resource in Context Crashes the Next Payload Assembly](../../debugging/03-pdf-context-utf8-decode.md); the fix is proven in `spikes/debug/pdf-context-utf8-decode/replica_context_service.py`.
- **Component Docs:** [ContextService](../../architecture/core/services/context_service.md), [IPdfExtractor](../../architecture/core/ports/outbound/pdf_extractor.md), [IFileSystemManager](../../architecture/core/ports/outbound/file_system_manager.md)
- **Scope Slug:** `pdf-context`

## Goal
Make context assembly PDF-aware, so a local `.pdf` resource in the turn or session scope embeds as its extracted text layer instead of being decoded as UTF-8 and crashing the next payload with `UnicodeDecodeError`.

## Context
- `ContextService.get_context`: collects every local path into one list and hands it to `IFileSystemManager.read_files_in_vault`, which embeds each file verbatim.
- `LocalFileSystemAdapter.read_files_in_vault` loops `read_raw_file`, a bare `Path.read_text(encoding="utf-8")` that catches only `FileNotFoundError`. The shared `%PDF-1.x\r%` header places `0xe2` at byte index 10, so essentially every PDF raises `UnicodeDecodeError` there.
- READ is already PDF-aware: `ActionFactory._create_pdf_read_action` reads bytes and delegates to `IPdfExtractor`. A successful READ without a `Lines` parameter then registers its path into the next turn's `turn.context` through `SessionService._apply_single_log_effect`, which is how a PDF legitimately reaches the embedder.
- `IPdfExtractor.extract_text(data, source)` is registered in `registries/infrastructure.py` and already injected into `ActionFactory` (via `ActionPorts`) and `WebScraperAdapter`.
- `core/utils/pdf.py` provides `is_pdf_source` (case-insensitive, strips query string and fragment) and `cap_extracted_text`, which delegates to `truncate_lines(..., direction="head", action_type="read")`, so a PDF inherits the same notice a long text file receives.
- `IFileSystemManager.read_file_bytes` already reads raw bytes with no decoding or truncation, and `LocalFileSystemAdapter` implements it.
- `DEFAULT_APP_CONFIG.read.max_lines` is the schema default for the shared read budget; `_resolve_plan_max_lines` already resolves `plan.max_lines` through the same optional `IConfigService` shape.
- `ContextService` is constructed positionally in `tests/suites/unit/core/services/test_context_service_model_threading.py:43` and `test_context_service_performance.py:46`, and by keyword in `container.py` and `tests/suites/integration/core/services/test_context_plan_cap.py:51`, so the new dependency must be appended last, after `config_service`.
- The unit `service` fixture registers `ContextService` as a bare class, so punq auto-resolves its constructor: the new port must be registered in that container for every existing service test to keep resolving.

## Scenarios
> As an agent, I want a PDF I already read to stay readable in the next turn's payload so that I can keep working with the document instead of losing the session to a decode error.

```gherkin
Given a session where the previous turn READ a local report.pdf
When the next turn's payload is assembled
Then report.pdf renders under ## Resource Contents as its extracted text
And no UnicodeDecodeError is raised
```

```gherkin
Given a turn context holding both report.pdf and notes.md
When the payload is assembled
Then notes.md renders verbatim
And report.pdf renders only its extracted text
And the vault reader never receives the PDF path
```

```gherkin
Given a local report.pdf whose extracted text exceeds read.max_lines
When the payload is assembled
Then the embedded text is head-truncated with the same notice a long text file receives
```

## Edge Cases
- **PDF-only scope**: If the working set holds only PDF paths, then the extracted text is the sole resource body and no decode is attempted, because the vault reader is skipped entirely.
- **Mixed scope**: If PDF and text paths are both present, then the vault reader receives only the text paths, because a PDF path must never reach a UTF-8 decode.
- **Uppercase extension**: If the path ends in `.PDF`, then it is treated as a PDF, because `is_pdf_source` matches case-insensitively.
- **Missing PDF**: If the file vanished after being registered, then `read_file_bytes` raises `FileNotFoundError` and the resource renders the existing `--- FILE NOT FOUND ---` marker, because the marker contract outlives the extraction path.
- **Cap**: If the extracted text exceeds `read.max_lines`, then it is head-truncated through `cap_extracted_text`, because a PDF obeys the same budget and the same notice as a text file rather than inventing a second one.
- **Unconfigured cap**: If no config service is injected, then the schema default `read.max_lines` applies, because the service already treats `IConfigService` as an optional handle.
- **Missing port**: If a PDF is in scope while no `IPdfExtractor` was injected, then the contract assertion names `pdf_extractor`, because a silently decoded PDF is the defect this slice removes.
- **Session scope**: If the PDF sits in a non-`Turn` session scope, then it hoists to `## Session Resources` as extracted text, because partitioning is a path decision that applies to every scope.
- **Token accounting**: If token counts are requested, then the PDF's `ContextItem.token_count` is counted over the extracted and capped text, because the item metadata must match the embedded body.

## Key Unknowns
None. The behaviour is proven end to end by the sandbox replica, and every remaining question is answerable from the existing code and test harness: the detection and cap helpers already exist with unit coverage, `read_file_bytes` already exists on both the port and the adapter, and the harness already ships `FakePdfExtractor` and `build_minimal_pdf`.

## Impact
1. `[EXTEND]` `ContextService.__init__` — append an optional `pdf_extractor: Optional[IPdfExtractor] = None` after `config_service`, so both positional call sites stay valid.
2. `[EXTEND]` `ContextService.get_context` — partition local paths into PDF and text sets, keep the vault read for text paths, and embed PDF resources as extracted text capped at `read.max_lines`, preserving the not-found marker.
3. `[MIGRATE]` `container.py` `ContextService` factory — pass the already-registered `IPdfExtractor`, the only production construction site of the service.
4. `[EXTEND]` `tests/suites/unit/core/services/conftest.py` — lift the `service` fixture out of `test_context_service.py` and supply the `fake_pdf_extractor` port, so every service test resolves the extended constructor.
5. `[NEW]` `tests/suites/unit/core/services/test_context_pdf_embedding.py` — regression coverage for the PDF branch, beside the existing service suite.
6. `[EXTEND]` `tests/suites/integration/core/services/test_container_wiring.py` — assert the composition root hands the resolved service the real extractor and that a PDF resource embeds off disk.
7. Explicitly unchanged: `IFileSystemManager` and `LocalFileSystemAdapter` (`read_file_bytes` already exists, and `read_files_in_vault` keeps its verbatim-text contract), `WebScraperAdapter` (a remote PDF already extracts before caching), `ActionFactory` (READ already routes PDFs), and `SessionReplanner` / `SessionPruningService` (audited as unreachable by a PDF path in the case file).

## Deliverables
- [ ] **Core** - Extend `ContextService` with the trailing optional `pdf_extractor`, split local paths by `is_pdf_source`, embed PDF resources as capped extracted text while preserving the not-found marker, lift the shared `service` fixture into the directory `conftest.py` with the port supplied, and add the regression module covering the PDF branch and its edge cases.
- [ ] **Migration** - Pass the resolved `IPdfExtractor` from the `ContextService` factory in `container.py`, extend the composition-root wiring test to prove the injection and the off-disk PDF embed, and confirm the reproduction script assembles the payload.

## Implementation Notes
- Mirror `spikes/debug/pdf-context-utf8-decode/replica_context_service.py`: `_read_pdf_contents` and `_resolve_read_max_lines` as private helpers, `FileNotFoundError` mapped to `None`, and an `assert` contract when the port is absent.
- The case file hands two hygiene items to Milestone 5 (the dead `_check_file_contains` helper and `SessionReplanner._collect_error_resources` swallowing read failures); they stay out of this slice.

## Verification
1. **Reproduction script:**
   Run `uv run python spikes/debug/pdf-context-utf8-decode/01-pdf-context-embed-crash-mre.py`.
   Verify it prints `NO CRASH: the turn context assembled`, a payload character count, and an excerpt containing `Context PDF fixture`, and exits with code 0.
2. **Local PDF in a session:**
   Start a session, READ a local `.pdf`, then continue one more turn.
   Verify the new payload shows the document text under `## Resource Contents` instead of `Error: 'utf-8' codec can't decode byte ...`.
3. **Non-PDF regression:**
   Keep a `.md` file in the same scope as the PDF.
   Verify it still renders its file content verbatim.
4. **Missing PDF:**
   READ a `.pdf`, delete the file from disk, then continue one turn.
   Verify the resource renders `--- FILE NOT FOUND ---` instead of raising.
5. **Cap:**
   Set `read.max_lines: 5` in `.teddy/config.yaml` and READ a PDF with more than five lines of text.
   Verify the embedded text is truncated with the same notice a long text file receives.
