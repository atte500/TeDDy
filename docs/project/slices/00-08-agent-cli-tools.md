# Slice: Agent CLI Tools (Log Fetcher & VCP)
- **Status:** Planned
- **Milestone:** N/A
- **Specs:** N/A
- **Prototype:** N/A
- **MRE:** N/A
- **Showcase:** N/A
- **Component Docs:**
  - [CLI Adapter](../../architecture/adapters/inbound/cli.md)

## Business Goal
Implement the `teddy run <script>` dynamic execution architecture to provide agents with robust, cross-platform Python utilities. This follows TeDDy's bundling pattern: default scripts (like `vcp.py` and `fetch-gh-log.py`) are bundled in the package and copied into the user's `.teddy/scripts/` directory by the `InitService`. This eliminates the architectural code smell of embedding complex bash inside prompts, while keeping the CLI perfectly clean and granting end-users infinite hackability to customize their agent's tools.

## Scenarios
> As an AI Debugger agent, I want to fetch clean CI logs without worrying about ANSI garbage or matrix job URL encoding.
```gherkin
Given a GitHub Actions run ID and an optional target step name
When I execute `teddy run fetch-gh-log [ID] "[STEP]"`
Then the command retrieves the logs via the `gh` CLI
And it uses Python to strip all ANSI escape sequences and GitHub Actions boilerplate
And it outputs clean, distilled plain-text to stdout
```

> As an AI agent, I want to commit my work safely without battling quote-escaping, pre-commit auto-fixes, or token-heavy test stack traces.
```gherkin
Given modified files in the workspace
When I execute `teddy run commit -m "feat: my changes" --test "pytest"`
Then the system runs the test command and truncates output if it fails catastrophically
And it runs pre-commit, automatically re-staging files if linters auto-format them
And it commits using the provided message securely
And it pushes the changes to the remote repository
```

## Deliverables
- [ ] **Contract** - Add `run <script_name>` command to the root Typer CLI adapter.
- [ ] **Logic (CLI)** - Implement dynamic script resolution with extension auto-discovery: `teddy run commit` should automatically resolve `commit.py`, `commit.sh`, or `commit` in `.teddy/scripts/`. If not found, it MUST fall back to `src/teddy_executor/resources/scripts/`. If still not found, it MUST halt with a clean error (do NOT fall back to global shell binaries).
- [ ] **Logic (InitService)** - Update `InitService` to scaffold `.teddy/scripts/` and copy contents from `resources/scripts/` on project initialization.
- [ ] **Feature** - Create bundled script `src/teddy_executor/resources/scripts/fetch-gh-log.py`.
- [ ] **Feature** - Create bundled script `src/teddy_executor/resources/scripts/commit.py` supporting `-m`, `-t`, and `--no-verify`.
- [ ] **Migration (Log Fetcher)** - Edit `src/teddy_executor/resources/prompts/debugger.xml` to replace the `awk` one-liner with `teddy run fetch-gh-log [ID] "[STEP]"`.
- [ ] **Migration (VCP)** - Edit **ALL** agent prompts in `src/teddy_executor/resources/prompts/*.xml` to replace the raw bash Version Control Protocol block with the new `teddy run commit` command.

## Implementation Notes
*To be filled by the Developer during implementation.*

## Delta Analysis
- **CLI Inbound Adapter:** Top-level `run` command added.
- **InitService:** Expanded to handle scaffolding of the `scripts/` directory.
- **Prompt Resources:** All `.xml` agent prompts will shed massive bash block complexity in favor of declarative `teddy run` commands.

## Guidelines for Implementation
- **Log Fetcher (Template):** Use the precise `awk/sed` state machine logic currently living in the `debugger.xml` prompt as your conceptual blueprint for the Python string processing logic.
- **Log Fetcher (Fallback):** If the `<step_name>` argument is omitted, the script MUST NOT filter by step. It must process the entire run log, strip all ANSI codes and `##[group]` boilerplate, and return the complete distilled trace.
- **Commit Tool (Token Protection):** Truncate test failure output to the last 50-100 lines to strictly protect the LLM context window from stack-trace blowouts.
- **Commit Tool (Pre-commit Logic):** If `pre-commit` returns a non-zero exit code, check `git status --porcelain`. If files were modified (meaning the linter auto-fixed them), auto-run `git add .` and continue. Only halt the script on hard errors (non-zero exit and no modified files).
- **Commit Tool (Process Safety):** When invoking Git, pass arguments as a list (e.g., `["git", "commit", "-m", message]`) to `subprocess.run` to absolutely guarantee that shell-injection and quote-escaping bugs are eliminated.
