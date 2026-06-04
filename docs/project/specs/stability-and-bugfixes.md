# Spec: Stability & Bug Fixes

## 1. Infrastructure & Environment
- **LiteLLM Warnings:** Suppress `LiteLLM:WARNING` regarding missing `botocore` dependency in production environments (e.g., PyPI installs).
- **SSL/API Resilience:** Implement a retry mechanism (3 attempts) for LLM completion failures involving `SSLV3_ALERT_BAD_RECORD_MAC` errors or OpenRouter timeouts.
- **Safety Limits:** Implement `max-turns` (99) and `max-cost` ($5.00) limits in `config.yaml`, enforced strictly in `--yolo` (`-y`) mode.
- **Pruning Logic:** The `global_context_threshold` calculation MUST only sum the token counts of files residing in the `Turn` scope (originating from `turn.context`). Files from the `Session` scope (`session.context`) and the `System` scope (system prompts) are excluded from the threshold check, although they remain part of the final payload.
- **Web Scraper (403 Bypassing):** The `WebScraperAdapter` must attempt to bypass 403 Forbidden errors (Reproduce via: `https://www.pnas.org/doi/10.1073/pnas.2416294121`) by rotating User-Agents or using common headers.
- **GitHub Raw Compatibility:** Fix the issue where `raw.githubusercontent.com` links return `SUCCESS` but with empty content (Reproduce via: `https://raw.githubusercontent.com/lllyasviel/LayerDiffuse/main/README.md`).

## 2. Context Service & Session Management
- **Recursive Expansion:** If a path in a `.context` file or `-c` flag is a directory, the `ContextService` must recursively expand it and include all files, respecting `.gitignore` and `.teddyignore`.
- **Deduplication & Cleanliness:** Ensure context items are deduplicated. In session mode, NEVER include resource contents in `report.md` (since contents are already gathered in `input.md`).
- **Auto-Addition:** `CREATE` and `EDIT` actions must automatically add the target file path to the turn's context (provided the file exists).
- **Session Migration:** Cap turns at 99 using 2-digit padding (01, ..., 99). At turn 100, automatically migrate to a new continuation session (e.g., `original-name-2`) by cloning `session.context` and the active prompt, transitioning the `turn.context` to preserve the working state.
- **Architecture Polish:** Store agent-specific prompts (e.g., `pathfinder.xml`) at the session root rather than copying or cloning them into turn directories.
- **Efficiency:** Add configuration to prevent "Message Turns" from being pruned.
- **Mid-Execution Consistency:** Gracefully return `FAILURE` for `EDIT` actions if a file is modified externally during execution (e.g., by a preceding `EXECUTE`).
- **Sequential Edits:** The execution state (e.g., file hashes) MUST be updated immediately after every successful `EDIT` action within a single plan. This ensures that a chain of multiple `EDIT` actions on the same file does not trigger a consistency error.
- **Windows TTY Probe:** Investigate using `WaitForInputIdle` as a proactive "fast-fail" mechanism for Windows child processes to complement the timeout-based detection.

## 3. Execution Hardening & TTY Detection
- **Standardized Fail-Fast:** The `ShellAdapter` must detect interactive prompts and fail-fast with the standardized message: `FAILURE: Interactive prompt detected`.
- **UNIX Strategy:** Leverage signal handling to detect `SIGTTIN` (attempting to read from TTY when in background/orphaned).
- **Windows Strategy:**
    - **Proactive Probe:** Investigate using `WaitForInputIdle` (via `ctypes`) as a "fast-fail" probe for console/GUI processes.
    - **EOF Mapping:** Detect and map "Unexpected EOF" or "Input required" error patterns in `stderr` (triggered when `stdin` is redirected to `NUL`) to the standardized error message.
- **Sequential Edits:** To support chaining multiple `EDIT` actions on the same file in one plan, the execution state (file hashes/metadata) MUST be updated immediately after every successful `EDIT`. This prevents subsequent edits in the same plan from triggering "External Modification" consistency errors.

## 4. TUI & CLI UX
- **Editor Precision:** Ensure the `(e)` key in the TUI strictly respects the `editor` configuration in `config.yaml` as the highest priority.
- **Explicit Fallbacks:** Remove all implicit "code" (VS Code) fallbacks in the adapter layer. The system must strictly follow Config -> Env -> Terminal Fallback.
- **Layout Consistency:** Ensure padding for Rationale items and Message sections matches the padding of the right-hand panel across all views.
- **Tier 2 Editing:** If a parameter is multiline or exceeds 100 characters, automatically open the external editor for that parameter instead of an inline prompt.
- **UX Hints:** In the hint appended to user request messages, remind the user to "update reference documents accordingly if needed."
- **Parser Resilience:** For all actions (e.g., `READ`, `MESSAGE`), ignore and clean up unforeseen codeblocks, thematic breaks (`---`), trailing text within codeblock delimiters (e.g., `~~~~~~ trailing text`), and unexpected codeblocks in the AST during parsing without triggering validation errors. **Note:** Other unforeseen text outside delimiters must still raise a validation error.
- **EXECUTE Fail-Fast:** Detect interactive prompts to fail early; on timeout, identify the specific failing command in a chain.
- **Relaxed Context Validation:** Do not throw validation errors for `READ`-ing files already in context or `EDIT`-ing files not in context; rely on matching logic for enforcement.
- **Redundant Edits:** Do not throw validation errors for `EDIT` actions where the `FIND` and `REPLACE` blocks are identical; treat them as successful no-ops.
- **Post-Execution Logging:** The `ExecutionOrchestrator` (or `SessionOrchestrator`) must detect if an additional user message was provided during the review phase (via TUI 'm' key or message reply) and log it to the console *after* all actions have executed. Format: `User Message: [content]`.

## 5. Config Validation & Transient Retry
- **Startup Validation:** Validate LLM configuration (API key format, model availability, provider capabilities) before any completion call. If config is invalid, immediately abort with a fatal error (no retry).
- **Transient Retry:** During the LLM completion call, retry on any error (not just SSL/Timeout) using the existing 3-attempt loop, because by this point config validation has passed so the error must be transient.
- **Configurable Timeout:** Support a configurable timeout (default 5 minutes) for LLM completion, after which the call is retried.
