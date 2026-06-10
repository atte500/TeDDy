# Task: CLI Refinements - Add `teddy init` and Remove `teddy plan`

## Business Goal
Provide an explicit `teddy init` command that initializes the `.teddy` folder and pre-warms heavy imports to reduce startup time for subsequent commands. Remove the standalone `teddy plan` command since planning is handled internally by session commands (`start`, `resume`).

## Context

### Current State
- The CLI has 5 commands: `start`, `plan`, `context`, `resume`, `execute`.
- Auto-initialization (`_ensure_project_initialized`) runs before every command.
- Heavy libraries (`litellm`, `trafilatura`, `pyperclip`, `bs4`, `ddgs`) are imported lazily, causing first-run slowness.
- The `plan` command is a simple wrapper calling `handle_plan_generation`. This function is also used internally by `start` and `resume`.

### Desired State
- Add `teddy init` command that creates `.teddy/` (idempotent) and pre-warms imports by importing the heavy modules directly.
- Remove `teddy plan` from the CLI (the internal `handle_plan_generation` must remain).
- Update documentation and tests accordingly.

## Implementation Steps

### Step 1: Add `teddy init` command to `__main__.py`
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:** Insert a new `@app.command()` block for `init` after the existing `start` command (or at the end of command definitions, but before `create_parser_for_plan`). The command should:
  1. Call `get_container()`
  2. Call `_ensure_project_initialized(container)` to create `.teddy/` and default files if missing (idempotent).
  3. Import the heavy modules (`litellm`, `trafilatura`, `pyperclip`, `bs4`, `ddgs`) in a try/except block that silently ignores ImportError (in case some aren't installed).
  4. Print a success message using `typer.echo`: `"TeDDy initialized in .teddy folder."`
  5. No other options (no `--no-copy`, no TUI mode). Keep it simple.

  The command does NOT need `--no-copy` or `--tui/--console` flags. It should not accept positional arguments.

  ```python
  @app.command()
  def init():
      """
      Initializes the .teddy directory and pre-warms heavy imports for faster startup.
      """
      container = get_container()
      _ensure_project_initialized(container)
      # Pre-warm heavy imports to reduce first-run latency
      try:
          import litellm  # noqa: F401
          import trafilatura  # noqa: F401
          import pyperclip  # noqa: F401
          from bs4 import BeautifulSoup  # noqa: F401
          from ddgs import DDGS  # noqa: F401
      except ImportError:
          pass  # Some optional dependencies may not be installed
      typer.echo("TeDDy initialized in .teddy folder.")
  ```

  Place this after the `start` command block and before the `plan` command block. The ordering of commands in `--help` will be: start, init, plan, context, resume, execute.

### Step 2: Remove `teddy plan` command from `__main__.py`
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:** Delete the entire `@app.command()` block for `plan` (lines 151-167). This includes:
  ```python
  @app.command()
  def plan(
      message: Optional[str] = typer.Option(
          None, "--message", "-m", help="The instructions for the AI."
      ),
  ):
      """
      Generates a plan.md within the current turn directory.
      """
      from teddy_executor.adapters.inbound.session_cli_handlers import (
          handle_plan_generation,
      )

      container = get_container()
      _ensure_project_initialized(container)
      handle_plan_generation(container, message)
  ```
  DO NOT remove the `handle_plan_generation` import or function – it is still used by the `resume` and `start` commands.

### Step 3: Update integration test that references `teddy plan` CLI command
- **File:** [tests/suites/integration/core/services/test_session_orchestration_integration.py](/tests/suites/integration/core/services/test_session_orchestration_integration.py)
- **Change:** Read the function `test_teddy_plan_generates_plan_file`. If it uses `CliRunner` to invoke `teddy plan` directly, update it to use the internal `handle_plan_generation` function instead (or remove the CLI-level test and replace with a unit test for the handler). Determine the exact change after reading the file.

### Step 4: Update CLI architecture documentation
- **File:** [docs/architecture/adapters/inbound/cli.md](/docs/architecture/adapters/inbound/cli.md)
- **Change:** In the Command-Line Interface section (section 4):
  1. Add a new subsection for `init` command after the `start` command.
  2. Remove the subsection for `plan` command (or mark it as removed).
  3. Update the command listing table if one exists.
  4. Include a note that the `plan` command was removed in version X.X and planning is now handled internally by session commands.

### Step 5: Update `README.md` command reference (if needed)
- **File:** [README.md](/README.md)
- **Change:** The README in the root has a small command table. Check if `plan` command is listed. If so, remove it. Add `init` command description. (Likely not present since the README only shows `execute`, `context`, `get-prompt`.)

### Step 6: Update CLI help text to reflect new command list
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:** Ensure `teddy init` has a concise docstring (used as help text). The `teddy plan` removal means it won't appear in `--help`. No other changes needed.

### Step 7: Update OAuth spec to document `init` → `login` linkage
- **File:** [docs/project/specs/openrouter-monetization-oauth.md](/docs/project/specs/openrouter-monetization-oauth.md)
- **Change:** In the "Guiding Principles" section, add a new bullet: "**Init→Login Funnel:** Running `teddy init` automatically checks for existing credentials in `.teddy/credentials.yaml`. If no valid credentials are found, it echoes a message and auto-launches the `teddy login` OAuth browser flow without prompting. This funnels new users into OpenRouter monetization."

### Step 8: Add auto-login trigger to `teddy init` behavior
- **File:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Change:** After the import pre-warming block in the `init` command, add logic to check for existing credentials. If no credentials file exists (or it's empty/invalid), echo a message: `"No credentials found. Launching login to OpenRouter..."` and then call the login handler (same function used by `teddy login`). This happens after the success message.

  The login handler import will be lazy:
  ```python
  # After import pre-warming and success message, check credentials
  from teddy_executor.adapters.inbound.session_cli_handlers import handle_login
  # Check if credentials exist
  credentials_path = Path(".teddy") / "credentials.yaml"
  if not credentials_path.exists() or not credentials_path.read_text().strip():
      typer.echo("No credentials found. Launching login to OpenRouter...")
      handle_login(container)
  ```

### Step 9: Remove `teddy plan` from README command table (if present)
- **File:** [README.md](/README.md)
- **Change:** The README command table (in section "Command-Line Reference") currently lists `execute`, `context`, `get-prompt`. No change needed since `plan` is not listed. Verify and add `init` description.

### Step 10: Update CLI architecture documentation
- **File:** [docs/architecture/adapters/inbound/cli.md](/docs/architecture/adapters/inbound/cli.md)
- **Change:** Remove the "Session Command: plan" subsection and add a new "Utility Command: init" subsection describing the init command behavior.

## Verification
1. Run `poetry run teddy init` (from project root) – it should create `.teddy/` if missing and print "TeDDy initialized in .teddy folder." If `.teddy/` already exists, it should still print the message (idempotent).
2. Run `poetry run teddy --help` – verify `init` appears in the command list and `plan` does NOT appear.
3. Run `poetry run teddy plan` – should produce an error indicating `plan` is not a valid command (exit code 2 from Typer).
4. Run `poetry run teddy start -a assistant -m "test"` and confirm it still works (planning happens internally).
5. Run the full test suite: `poetry run pytest tests/ -x` – all existing tests must pass.
6. Verify that the integration test `test_teddy_plan_generates_plan_file` still passes (if updated correctly).
7. Verify CLI documentation is accurate.
