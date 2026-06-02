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
- **Parser Resilience:** Ignore and clean up unforeseen codeblocks, thematic breaks (`---`), or trailing text within delimiters (e.g., `~~~~~~ trailing text`) without validation errors (Note: Preserve trailing text outside delimiters).
- **Efficiency:** Store `system_prompt.xml` at session root; prevent pruning of "Message Turns".
- **Fail-Fast:** Synchronous `EXECUTE` must fail-fast on interactive prompts; `EDIT` must gracefully return `FAILURE` if file modified during execution.
- **Validation:** Relax context rules for `READ`/`EDIT` to rely on matching logic rather than throwing validation errors for context presence; ignore redundant edits (identical FIND and REPLACE blocks) without triggering validation errors.

## Vertical Slices
- [x] **02-01-Resilient Infrastructure**: LLM retries and recursive context expansion.
- [x] **02-02-Web Scraping Resilience**: User-Agent rotation and GitHub raw fixes.
- [ ] **02-03-Safety Limits**: 99-turn limit, session cost tracking, and loop protection.
- [ ] **02-04-Context Automation**: Auto-addition of CREATE/EDIT targets, remote URL context, and relaxed validation.
- [ ] **02-05-Architecture Efficiency**: Session prompt relocation and session efficiency improvements.
- [ ] **02-06-Parser and Orchestrator Hardening**: Fail-fast execution, mid-execution consistency, and parser resilience.
