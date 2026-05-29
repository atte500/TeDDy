# Milestone: 02-Stability & Polish

- **Status:** Planned
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)

## Goal (The "Why")
To harden the system against external failures and improve the reliability of the core session workflow.

## Proposed Solution (The "What")
Implement resilient infrastructure patterns (retries, User-Agent rotation) and improve context management (recursion, turn limits, auto-addition).

## Guidelines (The "How")
- **Test Harness Triad Strategy:**
    - **Driver:** Use `MockLlmClient` to simulate transient SSL/Timeout failures.
    - **Observer:** Use `FileSystemObserver` to verify recursive context contents in `input.md`.
    - **Setup:** Use `TestEnvironment` to patch `IFileSystemManager` for directory traversal tests.
- **Fail-Fast:** Ensure `LiteLLMAdapter` distinguishes between transient (retryable) and permanent (fatal) errors.

## Technical Specifications
- **Retry Logic:** 3 attempts for `SSLV3_ALERT_BAD_RECORD_MAC` and `TimeoutError`.
- **Recursion:** `ContextService` uses `IRepoTreeGenerator` logic to expand directories while respecting ignores.

## Vertical Slices
1. [02-01-resilient-infrastructure.md](/docs/project/slices/02-01-resilient-infrastructure.md): LLM retries and recursive context expansion.
2. **02-02-web-scraping-resilience**: User-Agent rotation and GitHub raw fixes.
3. **02-03-session-turn-limits**: 99-turn limit and session migration.
4. **02-04-context-automation**: Auto-addition of CREATE/EDIT targets.
