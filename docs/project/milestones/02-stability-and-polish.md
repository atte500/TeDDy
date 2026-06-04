# Milestone 2: Stability & Infrastructure

- **Status:** In Progress
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)

## Goal (The "Why")
To harden the system against external failures, ensure cost/safety limits, and improve the reliability of the core session workflow.

## Proposed Solution (The "What")
Implement resilient infrastructure patterns (retries, User-Agent rotation), enforce strict safety bounds (turn/cost limits), automate context management (auto-addition, recursion), and harden the parser/orchestrator against edge-case failures.

## Guidelines (The "How")
- **Test Harness Triad Strategy:**
    - **Driver:** Use `MockLlmClient` to simulate transient SSL/Timeout failures.
    - **Observer:** Use `FileSystemObserver` to verify recursive context contents in `input.md`.
    - **Setup:** Use `TestEnvironment` to patch `IFileSystemManager` for directory traversal tests.
- **Fail-Fast:** Ensure `LiteLLMAdapter` distinguishes between transient (retryable) and permanent (fatal) errors.
- **Poka-Yoke:** Use `--yolo` mode enforcement for safety limits.

## Technical Specifications
- **Retry Logic:** 3 attempts for LLM completion failures involving `SSLV3_ALERT_BAD_RECORD_MAC` errors or OpenRouter timeouts.
- **Recursion:** `ContextService` must recursively expand directory context paths while respecting `.gitignore` and `.teddyignore`.
- **Safety Bounds:** Implement `max-turns` (99) and `max-cost` ($5.00) limits in `config.yaml`, enforced strictly in `--yolo` (`-y`) mode.
- **Web Scraping:** Bypass 403 Forbidden errors via User-Agent rotation (Reproduce via: `https://www.pnas.org/doi/10.1073/pnas.2416294121`); fix GitHub raw content extraction (Reproduce via: `https://raw.githubusercontent.com/lllyasviel/LayerDiffuse/main/README.md`).
- **Migration:** Cap turns at 99 with 2-digit padding; automate session continuation (e.g., `original-name-2`) by cloning `session.context` and transitioning `turn.context`.
- **Parser Resilience:** Ignore and clean up unforeseen codeblocks, thematic breaks (`---`), trailing text within delimiters (e.g., `~~~~~~ trailing text`), and unexpected codeblocks in the AST during parsing without validation errors (Note: Preserve trailing text outside delimiters).
- **Config Validation & Transient Retry:** Validate LLM configuration (API key, model) at startup, then retry on any error during LLM completion (default 3 attempts, configurable timeout).
- **Provider Routing & Display:** Remove `llm.provider` special-casing in `litellm_adapter._prepare_completion_params`; extract actual provider from `_hidden_params["provider"]` after completion; persist provider in `meta.yaml`; display `model / provider` in TUI right panel metadata; document pass-through behavior of `llm` config section and `:nitro`/`:floor` shortcuts.
- **Architecture Polish:** Store agent-specific prompts (e.g., `pathfinder.xml`) at session root; strictly deprecate turn-local prompt cloning; implement session termination on empty message without creating `report.md`; prevent pruning of "Message Turns".
- **Validation Failure Pruning Timing:** Modify Heuristic 4 in `session_pruning_service.py` to prune validation-failed turns ONLY when a subsequent valid plan has been produced. Guard Heuristic 4 with the same green-state check as Heuristic 3 (Recovery Cleanup): prune validation failures only when `is_currently_green or is_latest_green`. This ensures validation failure turns remain visible in context during chains of consecutive failures.
- **Session Context Write-Time Dedup:** Add path deduplication in `SessionService._prepare_session_context()` before writing to `session.context`. Currently, `init.context` lines merged with `additional_context` can contain duplicates that are written to disk. Ensure the merged list is deduplicated so that `session.context` never contains duplicate paths at creation time. (Note: read-time dedup via `read_context_file` already handles the `session.context` → `resolve_context_paths` pipeline, but write-time dedup is a defensive best practice.)
- **Fail-Fast & Hardening:** Synchronous `EXECUTE` must fail-fast on interactive prompts (UNIX signals/Windows exit codes) with a shared error message; `EDIT` must gracefully return `FAILURE` if file modified during execution.
- **Validation:** Relax context rules for `READ`/`EDIT` to rely on matching logic; ignore redundant edits (identical FIND and REPLACE blocks); ensure parser ignores trailing text in `~~~~~~` and ` `````` ` fences.

## Vertical Slices
> **Note:** The rename of `global_context_threshold` to `turn_context_threshold` is deferred until slice 02-07 (Pruning Refinement) is implemented, as the scoping logic is not yet in place.

- [x] **02-01-Resilient Infrastructure**: LLM retries and recursive context expansion.
- [x] **02-02-Web Scraping Resilience**: User-Agent rotation and GitHub raw fixes.
- [x] **02-03-Safety Limits**: 99-turn limit, session cost tracking, and loop protection.
- [x] **02-04-Context Automation**: Auto-addition of CREATE/EDIT targets, remote URL context, and relaxed validation.
- [x] **02-05-Architecture Efficiency**: Session prompt relocation and session efficiency improvements.
- [x] **02-06-Orchestrator Hardening**: Fail-fast execution, mid-execution consistency, and parser resilience.
- [ ] **02-07-Pruning Refinement**: Turn-only pruning threshold calculation.
- [ ] **02-08-Provider Routing and Display**: Remove `llm.provider` special-casing, extract provider, persist in `meta.yaml`, display in TUI, document pass-through and shortcuts.
- [ ] **02-09-Context Awareness**: Session web content caching (file-based cache for context URLs).
- [ ] **02-10-Preserve User-Message Turns**: Protect action turns with user messages from auto-pruning by checking report metadata.
- [ ] **02-11-AST Parser Resilience**: Extend parser to ignore unexpected codeblocks in the AST during plan parsing.
- [ ] **02-12-Config Validation & Transient Retry**: Validate LLM config upfront; retry on any error during completion.
- [ ] **02-13-Validation Failure Pruning Timing**: Modify Heuristic 4 to prune only when a subsequent valid plan exists.
- [ ] **02-14-Session Context Write-Time Dedup**: Add deduplication in `_prepare_session_context()` before writing to `session.context`.
