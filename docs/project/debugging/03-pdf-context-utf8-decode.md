# Bug: PDF Resource in Context Crashes the Next Payload Assembly
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** None.

## Symptoms
A session reads one local PDF and one remote PDF. Both READ actions report SUCCESS and that turn's payload assembles fine, but the following turn dies before it produces a plan:

```
Error: 'utf-8' codec can't decode byte 0xe2 in position 10: invalid continuation byte
```

Reproduction steps:
1. Start a session and ask the agent to READ a local PDF file and a remote PDF URL (observed with `govinfo_Overview_1019.pdf` and `https://www.federalreserve.gov/publications/files/financial-stability-report-20261113.pdf`).
2. Observe both READ actions report SUCCESS.
3. Observe the next turn fail with the decode error above, with no plan produced.

Minimal reproduction:
```
# Generates its own fixture PDF, then crashes on the production service (exit 1)
uv run python spikes/debug/pdf-context-utf8-decode/01-pdf-context-embed-crash-mre.py

# Same input against the sandbox replica carrying the fix (exit 0)
MRE_CONTEXT_SERVICE_MODULE=replica_context_service \
  uv run python spikes/debug/pdf-context-utf8-decode/01-pdf-context-embed-crash-mre.py
```
The MRE writes a 564-byte one-page PDF to `.tmp/debug/` and feeds it into the turn scope only, so no URL fetch, token counting, or git status takes part. It raises the reported `UnicodeDecodeError` against the production `ContextService` and assembles a payload of extracted PDF text against the replica. Set `MRE_PDF_PATH=<path>` to run it against a real document instead of the fixture.

## Context & Scope

### Regressing Delta
The PDF-extraction feature series taught the READ action to turn a PDF into text but never taught context assembly to embed a PDF resource:
- `82492412` `feat(pdf-extraction): add pure PDF detection and text cap helpers` — introduces `is_pdf_source`, `cap_extracted_text`.
- `1b366ad0` `feat(pdf-extraction): add PDF extraction contracts` — introduces `IFileSystemManager.read_file_bytes`, documented for binary payloads "such as PDF documents".
- `177e8ba2` `feat(pdf-extraction): add pypdf extractor and route PDF reads through it` — routes READ through `PdfReadAction`.
- `9de19482` `feat(pdf-extraction): inject the pdf extractor into the composition root` — registers `IPdfExtractor` and injects it into the web scraper only.

The gap sits where the feature stopped:
- `src/teddy_executor/core/services/context_service.py` — `get_context` embeds every local resource through `read_files_in_vault(local_paths)`.
- `src/teddy_executor/adapters/outbound/local_file_system_adapter.py:190` — `read_files_in_vault` loops `read_raw_file`, which is a bare `Path.read_text(encoding="utf-8")` (line 306). `read_files_in_vault` dates from `9394e254` and never carried a PDF guard, so no guard was removed: the feature added a new legitimate way for a PDF path to enter the working set without extending the embedder.
- `src/teddy_executor/container.py:233` — the `ContextService` factory never receives `IPdfExtractor`, although the port is already registered.

Remote PDFs are unaffected because `WebScraperAdapter._handle_pdf` extracts text before caching, so no URL ever reaches a text decode.

### Environmental Triggers
None beyond placing a local `.pdf` in the session or turn working set. The crash is deterministic on the file bytes: the shared `%PDF-1.x\r%` header puts a binary comment marker (`\xe2\xe3\xcf\xd3`) at index 10, which is not a valid UTF-8 continuation byte for essentially every PDF.

### Ruled Out
- **READ action byte handling.** `ActionFactory._create_pdf_read_action` reads with `read_file_bytes` and extracts via `IPdfExtractor`; the READ path never decodes a PDF as text. Both READs in the reported session reported SUCCESS, consistent with this.
- **Remote PDF handling.** `WebScraperAdapter._handle_pdf` extracts text before caching, so the remote report reaches the payload already as text.
- **`read_files_in_vault` swallowing decode errors.** It catches only `FileNotFoundError`; a `UnicodeDecodeError` propagates out of `get_context`.
- **The line-range READ branch.** It also routes through `read_raw_file`, but the failing READ used no line range, and a `Lines` READ is skipped at context registration anyway.
- **"Two distinct defects" hypothesis.** The `position 10` offset matches the local file's header, so a single unguarded local text read explains the whole symptom.
- **A second crashing reader in pruning or replanning.** `SessionPruningService._safe_read` is only reachable from `_check_plan_failed` (path must end in `plan.md`) and the three `_check_report_is_*` predicates (`report.md`); `_check_file_contains` has no call site; `SessionReplanner._collect_error_resources` returns `{}` in session mode and degrades on read failure instead of raising.
- **Breaking caller signatures.** Two suites construct `ContextService` positionally and the composition root by keyword, so the new dependency must be appended last; nothing else in `src/` or `tests/` binds its constructor.

## Diagnostic Analysis

### Causal Model
```
turn N:  READ govinfo_Overview_1019.pdf
  ActionFactory._create_read_action -> is_pdf_source -> PdfReadAction
    fs.read_file_bytes + IPdfExtractor.extract_text -> SUCCESS (text delivered via payload)
  SessionService._apply_single_log_effect
    status == SUCCESS, action_type == READ, no Lines param
    -> adds "govinfo_Overview_1019.pdf" to turn N+1 turn.context

turn N+1: payload assembly
  ContextService.get_context
    local_paths includes "govinfo_Overview_1019.pdf"
    -> LocalFileSystemAdapter.read_files_in_vault(local_paths)
      -> read_raw_file
        -> Path.read_text(encoding="utf-8")
          -> UnicodeDecodeError: byte 0xe2 in position 10
```

### Discrepancies
- [x] A READ of a local PDF reports SUCCESS, yet the next turn dies with a UTF-8 decode error. (Resolved: READ converts the PDF to text via `PdfReadAction`, but the path is registered verbatim into the next turn's context, where the embedder decodes it as raw text.)
- [x] The crash `position 10` suggests a small text file rather than a 315 KB PDF. (Resolved: the offset is the PDF header comment marker `%PDF-1.6\r%\xe2`, matched at runtime by reading the file as UTF-8.)
- [x] `SessionReplanner` and `SessionPruningService._safe_read` also decode context paths as text with only `FileNotFoundError`/`OSError` handlers; whether a PDF path can reach them is not yet established. (Resolved: neither can receive a PDF path. `_safe_read` is reached only through predicates gated on the item path ending in `plan.md` or `report.md`, `_check_file_contains` is unused, and the replanner's error-resource reader returns `{}` in session mode and swallows read failures. The embedder is the only reader that touches arbitrary context resources.)

### Investigation History
1. Read the local PDF as UTF-8 text; observed `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe2 in position 10: invalid continuation byte` on a 315 KB file whose header is `%PDF-1.6\r%\xe2\xe3\xcf\xd3`, confirming the exact reported signature byte for byte.
2. Enumerated PDF handling in `src/`; observed PDF-aware routing on both READ branches (`ActionFactory._create_pdf_read_action`, `WebScraperAdapter._handle_pdf`), eliminating the READ action as the decoding site.
3. Enumerated every text-read call site; observed `ContextService.get_context` as the only embedder of local resources, via a single `read_files_in_vault(local_paths)` call with no PDF awareness.
4. Read `LocalFileSystemAdapter.read_files_in_vault` and `read_raw_file`; observed an unguarded `Path.read_text(encoding="utf-8")` that catches only `FileNotFoundError` and `IOError`.
5. Ran `read_files_in_vault(["govinfo_Overview_1019.pdf"])` with the adapter's real collaborators; observed the same `UnicodeDecodeError`, confirming the adapter is the decoding site.
6. Read `SessionService._apply_single_log_effect`; observed a successful READ without a `Lines` parameter adds its resource path to the next turn's context set, closing the registration half of the chain.
7. Built `spikes/debug/pdf-context-utf8-decode/01-pdf-context-embed-crash-mre.py` and ran it against the production `ContextService`; observed `REPRODUCED: 'utf-8' codec can't decode byte 0xe2 in position 10: invalid continuation byte` (exit 1), proving the crash through the real assembly path.
8. Built the MRE without a `config_service` and with a web-scraper stub that raises if called; observed the reproduction still raises `UnicodeDecodeError`, so credentials, provider settings, and remote fetching play no part — the failure needs only a local PDF in the turn scope.
9. Built the sandbox replica `spikes/debug/pdf-context-utf8-decode/replica_context_service.py` from the production file by scripted single-occurrence replacements (each anchor asserted to match exactly once); observed a new optional `pdf_extractor` dependency, a split of local paths into PDF and text sets, and two helpers (`_read_pdf_contents`, `_resolve_read_max_lines`), with `read.max_lines` defaulting to 1000.
10. Ran the same MRE against the replica via `MRE_CONTEXT_SERVICE_MODULE=replica_context_service`; observed `NO CRASH: the turn context assembled`, a 4438-character payload, no `FILE NOT FOUND` marker, and a resource excerpt of readable govinfo prose — proving the fix empirically without touching production code.
11. Built `spikes/debug/pdf-context-utf8-decode/fixture_pdf.py`, a hand-built one-page PDF whose header places `0xe2` at index 10; observed a 564-byte fixture that fails a naive UTF-8 decode at `position 10` and parses through the production `PypdfExtractor` into `'Context PDF fixture'`, so the MRE needs no untracked download.
12. Ran both MRE modes against the generated fixture; observed `REPRODUCED: 'utf-8' codec can't decode byte 0xe2 in position 10` (exit 1) on the production service and `NO CRASH: the turn context assembled` (exit 0) on the replica, whose payload carries a fenced block containing `Context PDF fixture` — the fix is proven on a self-contained input.
13. Audited the peer text readers by reading their call sites; observed `SessionPruningService._safe_read` reachable only from `_check_plan_failed` (gated on a `plan.md` path) and the three `_check_report_is_*` predicates (gated on a `report.md` path), `_check_file_contains` with no call site at all, and `SessionReplanner._collect_error_resources` returning `{}` in session mode and swallowing read failures — so no PDF path reaches a crashing text read outside the embedder.
14. Ran the impact audit; observed `ContextService` constructed positionally in `tests/suites/unit/core/services/test_context_service_model_threading.py:43` and `test_context_service_performance.py:46` and by keyword in `src/teddy_executor/container.py:233`, so an optional trailing `pdf_extractor` keeps every caller source-compatible; `.tmp/` is already ignored (`.gitignore:103`).

## Solution

### Root Cause
Context assembly embeds every local resource as UTF-8 text. The PDF-extraction feature made "a PDF path in the working set" a normal occurrence by routing READ through `read_file_bytes` + `IPdfExtractor` and registering the path into the next turn's `turn.context`, but the embedder was never extended to match: `LocalFileSystemAdapter.read_files_in_vault` still calls `read_raw_file`, which decodes raw PDF bytes with `read_text(encoding="utf-8")`.

The fix is to make context assembly PDF-aware: `.pdf` local resources are read as bytes and embedded as their extracted text layer, capped by `read.max_lines`, while every other path keeps the existing verbatim read. `ContextService` gains an optional `IPdfExtractor` port and the composition root passes the already-registered one.

Verification status: proven in the sandbox replica `spikes/debug/pdf-context-utf8-decode/replica_context_service.py`, on an input the MRE generates itself (`.tmp/debug/pdf-context-fixture.pdf`, 564 bytes, parsed into `Context PDF fixture` by the production extractor). The same MRE raises `UnicodeDecodeError` against the production service (exit 1) and assembles a payload of extracted PDF text against the replica (exit 0, no `FILE NOT FOUND`).

Delivered in [Slice: PDF-Aware Context Embedding](../slices/00-54-pdf-context-embedding.md) as two commits: `d4ed938b` made `ContextService` PDF-aware (trailing optional `pdf_extractor`, `is_pdf_source` path partition, extracted text capped at `read.max_lines`, `FileNotFoundError` mapped to the existing not-found marker), and `ba93537b` wired the composition root so the factory resolves the already-registered `IPdfExtractor` instead of constructing the service with `pdf_extractor=None`. The regression module `tests/suites/unit/core/services/test_context_pdf_embedding.py` and two composition-root tests in `test_container_wiring.py` now lock both halves. The reproduction script prints `NO CRASH: the turn context assembled` (exit 0) against the production service, and a real session's first local PDF no longer reaches a text decode.

No new lint or structural check is added. The root cause is incomplete adoption of an existing port by one consumer, not a repeatable anti-pattern, platform assumption, or boundary leak — no generic rule can flag "a consumer accepts an optional port and silently ignores it" without banning legitimate optional ports. The deterministic guard is the regression test named under Affected Components: it fails the moment context assembly stops handling a PDF resource.

### Affected Components
- `ContextService` (`src/teddy_executor/core/services/context_service.py`): gains an optional trailing `pdf_extractor`, splits local paths into a PDF set and a text set, extracts PDF text through `IPdfExtractor`, and caps it via `read.max_lines`. No import beyond `IPdfExtractor` and the existing `core/utils/pdf` helpers is needed.
- Composition root (`src/teddy_executor/container.py:233`): the `ContextService` factory resolves and passes the already-registered `IPdfExtractor` — the same port already injected into `WebScraperAdapter` (`container.py:110`), so this is one additional keyword.
- `IFileSystemManager` / `LocalFileSystemAdapter`: contract unchanged; `read_file_bytes` already exists for binary payloads and `read_files_in_vault` keeps its verbatim-text behaviour, so no adapter edit is required.
- `SessionReplanner`, `SessionPruningService`: no change required — audited as unreachable by a PDF path. Two hygiene items surfaced and are deferred out of this fix to [Milestone 5: Quality Gate & Debt Reconciliation](../milestones/05-quality-gate-debt-reconciliation.md) as anticipated slices 32 and 33: the dead `_check_file_contains` helper, and `_collect_error_resources` swallowing read failures through a bare `except Exception`.
- Tests: a regression test beside `tests/suites/unit/core/services/test_context_service.py` asserting a PDF in the turn scope renders its extracted text under `Resource Contents` with no decode error. The new keyword must be appended after `config_service` so the two positionally-constructing suites stay valid.
