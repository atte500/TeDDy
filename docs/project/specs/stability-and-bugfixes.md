# Spec: Stability & Bug Fixes

## 1. Web Scraper Resilience
- **403 Bypassing:** The `WebScraperAdapter` must attempt to bypass 403 Forbidden errors by rotating User-Agents or using common headers. If bypass fails, it must provide a clear hint to the user to provide the content manually.
- **GitHub Compatibility:** Fix the issue where `raw.githubusercontent.com` links return empty content despite successful status codes.

## 2. Context Service Robustness
- **Directory Expansion:** If a path provided in a `.context` file or via the `-c` flag is a directory, the `ContextService` must recursively expand it and include all files, respecting `.gitignore` and `.teddyignore`.
- **URLs in Context:** Support adding URLs directly to `.context` files; these should be fetched and treated like local resources during context gathering.
- **Deduplication:** Ensure final context items are deduplicated and that resource contents are not redundantly added to reports if they are already present in the turn's `input.md`.
- **Auto-Addition:** The `CREATE` action must automatically add the newly created file to the current turn's `turn.context`.

## 3. Configuration & UX
- **LiteLLM Noise:** Suppress the "could not pre-load bedrock/sagemaker" warnings in production environments.
- **Editor Precision:** Ensure the `(e)` key in the TUI strictly respects the `editor` configuration in `config.yaml` as the highest priority.
- **SSL Resilience:** Implement a retry mechanism (3 attempts) for LLM completion failures involving SSL MAC errors or OpenRouter timeouts.
- **Session Limits:** Support `--max-turns` and `--max-cost` flags for auto-approval (`-y`) mode. These limits apply per `teddy resume` session and are not cumulative across the entire session history.
- **Auto-Pruning:** Add a configuration to prevent `## Message` turns from being pruned, preserving conversation history.
- **Deprecation:** Formally deprecate the `--console` flag in favor of the TUI.
- **Truncation Hints:** If `EXECUTE` or `READ` output is truncated, include a hint in the report suggesting the user output to a file and read it in a separate turn (for `EXECUTE`) or use `sed` with line counts (for `READ`).
- **Input Fail-Fast:** `EXECUTE` must fail fast if a command prompts for user input (detected via TTY polling or timeouts) and report the specific command that caused the hang.
