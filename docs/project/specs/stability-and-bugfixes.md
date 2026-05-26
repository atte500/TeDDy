# Spec: Stability & Bug Fixes

## 1. Infrastructure & Environment
- **LiteLLM Warnings:** Suppress `LiteLLM:WARNING` regarding missing `botocore` dependency in production environments (e.g., PyPI installs).
- **SSL/API Resilience:** Implement a retry mechanism (3 attempts) for LLM completion failures involving `SSLV3_ALERT_BAD_RECORD_MAC` errors or OpenRouter timeouts.
- **Web Scraper (403 Bypassing):** The `WebScraperAdapter` must attempt to bypass 403 Forbidden errors (Reproduce via: `https://www.pnas.org/doi/10.1073/pnas.2416294121`) by rotating User-Agents or using common headers.
- **GitHub Raw Compatibility:** Fix the issue where `raw.githubusercontent.com` links return `SUCCESS` but with empty content (Reproduce via: `https://raw.githubusercontent.com/lllyasviel/LayerDiffuse/main/README.md`).
- **RESEARCH Full Scrape:** The `RESEARCH` action should attempt to scrape and return full contents (or at least significant excerpts) instead of just SERP snippets.

## 2. Context Service & Session Management
- **Recursive Expansion:** If a path in a `.context` file or `-c` flag is a directory, the `ContextService` must recursively expand it and include all files, respecting `.gitignore` and `.teddyignore`.
- **Deduplication & Cleanliness:** Ensure context items are deduplicated. In session mode, NEVER include resource contents in `report.md` (since contents are already gathered in `input.md`).
- **Auto-Addition:** The `CREATE` action must automatically add the newly created file to the current turn's `turn.context`.
- **Mid-Execution Consistency:** Prevent crashes if a file is modified during execution (e.g., an `EXECUTE` command modifies a file that an `EDIT` action later attempts to touch). In such cases, the `EDIT` should report `FAILURE` gracefully.

## 3. TUI & CLI UX
- **Editor Precision:** Ensure the `(e)` key in the TUI strictly respects the `editor` configuration in `config.yaml` as the highest priority.
- **Explicit Fallbacks:** Remove all implicit "code" (VS Code) fallbacks in the adapter layer. The system must strictly follow Config -> Env -> Terminal Fallback.
- **Validation Visibility:** "Validation failed replanning" logs must include the concise version of the encountered errors and remove redundant empty lines.
- **Layout Consistency:** Ensure padding for Rationale items and Message sections matches the padding of the right-hand panel across all views.
- **Tier 2 Editing:** If a parameter is multiline or exceeds 100 characters, automatically open the external editor for that parameter instead of an inline prompt.
- **UX Hints:** In the hint appended to user request messages, remind the user to "update reference documents accordingly if needed."
- **Parser Resilience:** For all actions (e.g., `READ`, `MESSAGE`), the parser must ignore and clean up unforeseen codeblocks or thematic breaks (`---`) following the action block without throwing validation errors. **Note:** Trailing text must be preserved and NOT ignored.
