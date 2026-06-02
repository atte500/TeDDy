# Spec: Stability & Bug Fixes

## 1. Infrastructure & Environment
- **LiteLLM Warnings:** Suppress `LiteLLM:WARNING` regarding missing `botocore` dependency in production environments (e.g., PyPI installs).
- **SSL/API Resilience:** Implement a retry mechanism (3 attempts) for LLM completion failures involving `SSLV3_ALERT_BAD_RECORD_MAC` errors or OpenRouter timeouts.
- **Safety Limits:** Implement `max-turns` (99) and `max-cost` ($5.00) limits in `config.yaml`, enforced strictly in `--yolo` (`-y`) mode.
- **Web Scraper (403 Bypassing):** The `WebScraperAdapter` must attempt to bypass 403 Forbidden errors (Reproduce via: `https://www.pnas.org/doi/10.1073/pnas.2416294121`) by rotating User-Agents or using common headers.
- **GitHub Raw Compatibility:** Fix the issue where `raw.githubusercontent.com` links return `SUCCESS` but with empty content (Reproduce via: `https://raw.githubusercontent.com/lllyasviel/LayerDiffuse/main/README.md`).

## 2. Context Service & Session Management
- **Recursive Expansion:** If a path in a `.context` file or `-c` flag is a directory, the `ContextService` must recursively expand it and include all files, respecting `.gitignore` and `.teddyignore`.
- **Deduplication & Cleanliness:** Ensure context items are deduplicated. In session mode, NEVER include resource contents in `report.md` (since contents are already gathered in `input.md`).
- **Auto-Addition:** `CREATE` and `EDIT` actions must automatically add the target file path to the turn's context (provided the file exists).
- **Session Migration:** Cap turns at 99 using 2-digit padding (01, ..., 99). At turn 100, automatically migrate to a new continuation session (e.g., `original-name-2`) by cloning `session.context` and the active prompt, transitioning the `turn.context` to preserve the working state.
- **Architecture Polish:** Store `system_prompt.xml` at the session root rather than copying it into every turn directory.
- **Efficiency:** Add configuration to prevent "Message Turns" from being pruned.
- **Mid-Execution Consistency:** Gracefully return `FAILURE` for `EDIT` actions if a file is modified during execution (e.g., by a preceding `EXECUTE`).

## 3. TUI & CLI UX
- **Editor Precision:** Ensure the `(e)` key in the TUI strictly respects the `editor` configuration in `config.yaml` as the highest priority.
- **Explicit Fallbacks:** Remove all implicit "code" (VS Code) fallbacks in the adapter layer. The system must strictly follow Config -> Env -> Terminal Fallback.
- **Validation Visibility:** "Validation failed replanning" logs must include the concise version of the encountered errors and remove redundant empty lines.
- **Layout Consistency:** Ensure padding for Rationale items and Message sections matches the padding of the right-hand panel across all views.
- **Tier 2 Editing:** If a parameter is multiline or exceeds 100 characters, automatically open the external editor for that parameter instead of an inline prompt.
- **UX Hints:** In the hint appended to user request messages, remind the user to "update reference documents accordingly if needed."
- **Parser Resilience:** For all actions (e.g., `READ`, `MESSAGE`), ignore and clean up unforeseen codeblocks, thematic breaks (`---`), or trailing text within codeblock delimiters (e.g., `~~~~~~ trailing text`) following the action block without triggering validation errors. **Note:** Other unforeseen text outside delimiters must still raise a validation error.
- **EXECUTE Fail-Fast:** Detect interactive prompts to fail early; on timeout, identify the specific failing command in a chain.
- **Relaxed Context Validation:** Do not throw validation errors for `READ`-ing files already in context or `EDIT`-ing files not in context; rely on matching logic for enforcement.
- **Redundant Edits:** Do not throw validation errors for `EDIT` actions where the `FIND` and `REPLACE` blocks are identical; treat them as successful no-ops.
