# Spec: Editor Validation & Discovery (Milestone 3, Slice 03-01)

- **Status:** Active

## Overview / Problem Statement

The initial editor configuration UX has three gaps:

1. **Misleading default:** `editor: "code"` is hardcoded in the bundled config.yaml. If VS Code is not installed, the user gets a silent failure only when the editor is first needed (e.g., pressing `e` in the ask loop).
2. **No early validation:** The editor is only checked when first used, not at session startup. Users are not warned if their configured editor is missing from PATH.
3. **No fallback discovery:** When the editor is missing or unconfigured, there is no mechanism to discover available editors in PATH and prompt the user to select one.

The goal is to make editor configuration frictionless: empty default by default, early PATH validation, automatic discovery of available editors, and an interactive selection prompt that persists the result to config.

## Guiding Principles / Core Logic

1. **Fail early, fail clearly:** Editor validation must happen during the preflight check (`_run_cli_preflight_check`), before any session interaction begins.
2. **Gate on "will the session read the terminal":** Editor setup is decoupled from approval mode. It runs when the session will actually read stdin — an interactive run, or a `--yolo` / `yolo_default: true` run without `-m` (which still blocks on the opening-message prompt), on a TTY. It is skipped for fully-specified batch runs (`-y -m`), `--pipeline` runs, and any non-TTY stdin (CI/piped). The `interactive` flag is approval-only; headless/automated runs use `-y` (or non-TTY stdin), not the retired `--yes`/`--no-interactive`/`--non-interactive` aliases.
3. **Always persist:** The user's selection is always saved to `.teddy/config.yaml`. A message logs where the config can be edited.
4. **"disabled" sentinel:** If the user provides no input (empty), save `"disabled"` to config. This gracefully disables editor functionality everywhere.
5. **Curated discovery, but no guessing:** Scan a comprehensive list of known editors in PATH. If nothing is found, prompt for a custom command. If the custom command is not in PATH, reject and loop back.
6. **Diff flags: reliable fallback:** Known editors use precise diff flags from the `_DIFF_FLAGS` translation table. Unknown editors open both files as separate arguments (universally supported). A `diff_flags` config override provides escape hatch for power users.

## Technical Specification

### 1. Default Config Change

**File:** `src/teddy_executor/resources/config/config.yaml`

Change:
```yaml
editor: "code"
```
To:
```yaml
editor: ""
```

Add a commented-out `diff_flags` option below `editor`:
```yaml
# The preferred external editor for reviewing and modifying plans/messages.
# Supports arbitrary command strings (e.g., "code --wait", "nvim -R", "zed").
# Fallback chain: Config -> VISUAL/EDITOR env vars -> discovery prompt.
editor: ""

# Optional diff viewer flags override. If set, these flags are used instead
# of the built-in translation table for this editor.
# Example: ["--diff", "--wait"]
# diff_flags: []
```

### 2. ConsoleToolingHelper Enhancements

**File:** `src/teddy_executor/adapters/outbound/console_tooling.py`

#### 2a. Add `discover_editors()` method

```python
KNOWN_EDITORS: list[str] = [
    # Terminal editors (modern)
    "nvim", "vim", "vi", "helix", "hx", "nano", "micro", "kak",
    "emacs", "ne", "joe", "ed", "ex", "mg", "zee", "amp",
    # GUI editors
    "code", "codium", "cursor", "zed", "sublime_text", "subl",
    "atom", "pulsar", "brackets", "idea", "idea.sh", "webstorm",
    "phpstorm", "pycharm", "rubymine", "goland", "clion", "fleet",
    "eclipse", "netbeans", "bluefish", "gedit", "gnome-text-editor",
    "kate", "kwrite", "mousepad", "xed", "pluma", "leafpad", "geany",
    "notepadqq", "notepad++", "notepad", "wordpad", "vimr", "macvim",
    "textmate", "bbedit", "ultraedit", "windsurf", "tabnine", "tea",
    "cot", "textastic", "nova", "xcode", "android-studio",
]

def discover_editors(self) -> list[tuple[str, str]]:
    """Scan PATH for known editors. Returns (basename, resolved_path) pairs.
    Deduplicates by resolved path (same binary under different aliases)."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for editor in self.KNOWN_EDITORS:
        resolved = self._system_env.which(editor)
        if resolved and resolved not in seen:
            seen.add(resolved)
            found.append((editor, resolved))
    return found
```

The `KNOWN_EDITORS` list should be a class-level constant for testability.

#### 2b. Modify `find_editor()` to handle "disabled" sentinel

```python
def find_editor(self) -> Optional[list[str]]:
    # 0. Check for "disabled" sentinel
    editor_str = self._config_service.get_setting("editor")
    if editor_str and editor_str.strip().lower() == "disabled":
        return None

    # 1. Check Config
    if editor_str:
        if cmd := self._resolve_editor_cmd(editor_str):
            return cmd

    # 2. Check Env
    env_editor = self._system_env.get_env("VISUAL") or self._system_env.get_env("EDITOR")
    if cmd := self._resolve_editor_cmd(env_editor):
        return cmd

    return None
```

#### 2c. Modify `get_diff_viewer_command()` for unknown editors fallback

```python
def get_diff_viewer_command(self) -> Optional[list[str]]:
    # 0. Check for diff_flags config override
    diff_flags = self._config_service.get_setting("diff_flags")
    if diff_flags and isinstance(diff_flags, list):
        editor_cmd = self.find_editor()
        if editor_cmd:
            return editor_cmd[:1] + diff_flags

    # 1. Check TEDDY_DIFF_TOOL env var (existing behavior)
    custom_tool_str = self._system_env.get_env("TEDDY_DIFF_TOOL")
    if custom_tool_str:
        custom_tool_parts = shlex.split(custom_tool_str)
        tool_name = custom_tool_parts[0]
        if tool_path := self._system_env.which(tool_name):
            custom_tool_parts[0] = tool_path
            return custom_tool_parts
        return None

    # 2. Resolve editor and check translation table
    editor_cmd = self.find_editor()
    if not editor_cmd:
        return None

    basename = os.path.basename(editor_cmd[0]).lower()
    if flags := self._DIFF_FLAGS.get(basename):
        return editor_cmd[:1] + flags

    # 3. Unknown editor: return editor path without flags.
    #    Caller passes both file paths as arguments, so the editor opens
    #    both files in separate tabs (reliable no-guess fallback).
    return editor_cmd[:1]
```

#### 2d. Extend `_DIFF_FLAGS` translation table

Add entries for all editors in `KNOWN_EDITORS` whose diff flags are known:

```python
_DIFF_FLAGS: dict[str, list[str]] = {
    "vim": ["-d"],
    "vi": ["-d"],
    "nvim": ["-d"],
    "code": ["--diff"],
    "cursor": ["--diff"],
    "codium": ["--diff"],
    "zed": ["--diff"],
    "idea": ["diff"],
    "idea.sh": ["diff"],
    "webstorm": ["diff"],
    "phpstorm": ["diff"],
    "pycharm": ["diff"],
    "rubymine": ["diff"],
    "goland": ["diff"],
    "clion": ["diff"],
    "fleet": ["diff"],
}
```

### 3. YamlConfigAdapter: Add `set_setting()` Method

**File:** `src/teddy_executor/adapters/outbound/yaml_config_adapter.py`

Add a new method to write settings back to the user config file.

> **Prototype-verified (Slice 03-01 spike `probe_ku1`).** The naive body first
> drafted here omitted directory creation AND cache synchronization; the spike
> proved BOTH are mandatory: (1) a `root_dir`-based path whose `.teddy/` parent
> does not yet exist raises `FileNotFoundError` on write, and (2) a disk-only
> write leaves the in-memory merged `_config` cache stale — a subsequent
> `get_setting()` on the SAME adapter returns the pre-write value. `os` is a
> module-level import in the adapter, so no local import is needed.

```python
def set_setting(self, key: str, value: Any) -> None:
    """Sets a configuration value and persists to the user config file.
    Supports dot-notation for nested keys (e.g., 'editor', 'diff_flags').
    Reads the current file, merges the new value, and writes back."""
    # 1. Ensure the parent directory exists. A root_dir-based path (e.g.,
    #    <root>/.teddy/config.yaml) may not have created .teddy/ yet; without
    #    this, the write below raises FileNotFoundError (spike-verified).
    parent_dir = os.path.dirname(self._config_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    # 2. Load current user config (edit only the user-override file; the
    #    bundled baseline is never written to).
    user_config: dict = {}
    if os.path.exists(self._config_path):
        with open(self._config_path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}

    # 3. Set the value using dot-notation traversal
    keys = key.split(".")
    current = user_config
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value

    # 4. Write back
    with open(self._config_path, "w", encoding="utf-8") as f:
        yaml.dump(user_config, f, default_flow_style=False, allow_unicode=True)

    # 5. Synchronize the in-memory merged cache so a subsequent get_setting()
    #    on THIS adapter reflects the change without a reload (spike-verified).
    cache = self._config
    for k in keys[:-1]:
        cache = cache.setdefault(k, {})
    cache[keys[-1]] = value
```

### 4. Editor Validation in Preflight Check

**File:** `src/teddy_executor/adapters/inbound/session_cli_handlers.py`

Add a new function and call it from `_run_cli_preflight_check()` when the session will read the terminal (gated on the `setup_editor` signal):

```python
def _validate_editor_config(container: Container) -> None:
    """Validates editor configuration during preflight check.
    If the editor is unconfigured, missing from PATH, or set to 'disabled',
    prompts the user to select or configure one during interactive sessions.
    The result is persisted to .teddy/config.yaml."""
    from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
    from teddy_executor.core.ports.outbound.config_service import IConfigService
    from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
    from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter

    config_service = container.resolve(IConfigService)
    system_env = container.resolve(ISystemEnvironment)
    helper = ConsoleToolingHelper(system_env, config_service)

    editor_str = config_service.get_setting("editor") or ""

    # Check for "disabled" sentinel — skip validation (user explicitly disabled)
    if editor_str.strip().lower() == "disabled":
        return

    # If editor is configured, check if it's available in PATH
    if editor_str:
        editor_cmd = helper.find_editor()
        if editor_cmd:
            return  # All good, editor is resolved
        # Editor is configured but not found — log warning before falling through
        typer.secho(
            f"⚠ Configured editor '{editor_str}' not found in PATH. Discovering alternatives...",
            fg=typer.colors.YELLOW,
            err=True,
        )
    else:
        typer.secho(
            "No editor configured. Scanning for available editors in PATH...",
            fg=typer.colors.YELLOW,
            err=True,
        )

    # Discover available editors
    available = helper.discover_editors()
    if available:
        _prompt_for_editor_selection(config_service, helper, available)
    else:
        _prompt_for_custom_editor(config_service, helper)
```

The prompting functions (`_prompt_for_editor_selection`, `_prompt_for_custom_editor`) use `typer.prompt()` directly to avoid circular DI concerns with `IUserInteractor`. The **finalized console UI** below was validated interactively against the prototype `spikes/prototypes/editor-validation-and-discovery/editors_demo.py` (`--selftest` → 18/18 pass; its `--list-format` / `--show-paths` / `--prompt` / `--invalid-mode` / `--header` knobs were used to select these values).

**Editor-found branch (`_prompt_for_editor_selection`)** — rendered top-to-bottom, entirely on **stderr**:

1. A yellow warning line — the branch-appropriate status string from Step 4 above.
2. Blank line.
3. An **always-present** header line `Editor Setup` (cyan, bold). It is shown on BOTH branches (editors found AND nothing found).
4. Blank line.
5. The discovered editors, one per line, in **bracket** format with the resolved path **hidden**: `[1] nvim`, `[2] vim`, … (only the name is shown; the reader does not need the path).
6. Blank line.
7. A **single primary selection prompt** (a number, a custom command, and empty are all accepted here):
   `Select an editor [1-{n}] (number, custom command, or empty to disable): ` (`{n}` = the discovered count).

Primary-prompt input handling:

- **Valid in-range number** → persist the selected editor's **basename** to config (portable across machines; the read path re-resolves it on `PATH`), then a blank line and the green confirmation `Editor preference saved to .teddy/config.yaml.`
- **Out-of-range / non-numeric number** → the red message `'{raw}' is not a valid selection. Choose 1-{n}.` then re-prompt the primary prompt.
- **Custom command** → validate the first token with `which()`. If available, persist the command **exactly as typed** (so flags such as `code --wait` are preserved); if NOT available, the red message `'{raw}' was not found in PATH.` then re-prompt. A custom command is **never** accepted without passing `which()`.
- **Empty input** → persist `"disabled"` to config (then the green confirmation).
- **EOF / closed input** → persist `"disabled"`.

**Nothing-found branch (`_prompt_for_custom_editor`)** — when `discover_editors()` returns nothing: the warning, blank line, and the `Editor Setup` header still render, followed by the single prompt `No known editors found. Enter a custom editor command (leave empty to disable):`. The same `which()`-validation loop applies (unavailable → `'{raw}' was not found in PATH.` + re-prompt), as do empty→`"disabled"` and EOF→`"disabled"`.

**Rendering conventions:** yellow warning, cyan header, green confirmation, red invalid messages, emitted via `typer.secho(..., fg=..., err=True)` in keeping with the codebase's existing console style. All editor-selection output goes to **stderr** (never stdout).

The `_run_cli_preflight_check()` function accepts a dedicated `setup_editor` parameter, computed at the CLI boundary as `setup_editor = system_env.isatty() and not pipeline and (interactive or message is None)`, decoupling the one-time setup from the approval flag:

```python
def _run_cli_preflight_check(
    container: Container,
    agent: Optional[str] = None,
    setup_editor: Optional[bool] = None,
) -> None:
    # ... existing LLM config validation ...

    # Editor validation (only when the session will read the terminal)
    if setup_editor:
        _validate_editor_config(container)
```

The callers in `handle_new_session()` and `handle_resume_session()` pass the computed `setup_editor` flag; the one-shot `handle_plan_generation()` passes `setup_editor=False`.

### 5. "disabled" Sentinel Handling Downstream

All consumers of `find_editor()` already handle `None` gracefully by returning an empty string or falling back to in-terminal diff. The "disabled" sentinel causes `find_editor()` to return `None`, so existing `None`-based handling paths work correctly.

However, add a log/info message in `ConsoleAskLoop._launch_editor_background()` and `ConsoleInteractorAdapter._launch_editor_synchronous()` to inform the user when the editor is disabled:

```python
if not editor_cmd:
    logger.info(
        "Editor is disabled in config. Set 'editor' in .teddy/config.yaml to enable."
    )
    return ""
```

This message replaces the current generic "No editor configured" message.

### 6. IConfigService Interface: Add `set_setting()` Abstract Method

**File:** `src/teddy_executor/core/ports/outbound/config_service.py`

Add a new abstract method to the protocol:

```python
def set_setting(self, key: str, value: Any) -> None:
    """Sets a configuration value and persists to the config file.
    Supports dot-notation for nested keys."""
    ...
```

This is a BREAKING change to the protocol. All implementations of `IConfigService` MUST implement this method. Currently only `YamlConfigAdapter` implements this protocol. Any test fakes/mocks (e.g., in tests that spec=`IConfigService`) must also implement it. Update test harness mocks accordingly.

### 7. Editor Classification: Add Editors to `_CLI_EDITORS`

**File:** `src/teddy_executor/adapters/outbound/console_interactor_ask_loop.py`

Add `helix`/`hx` and `kak` to the `_CLI_EDITORS` set for correct synchronous launch behavior:

```python
_CLI_EDITORS: set[str] = {
    "vim", "nvim", "vi", "nano", "micro", "emacs", "pico",
    "helix", "hx", "kak",
}

**Unknown editor fallback:** When the resolved editor is not found in `_CLI_EDITORS` (terminal) and not in `_DIFF_FLAGS` (known GUI editors with diff flags), the TUI EDIT action flow (press `e` on an EDIT action) MUST default to the **annotated unified diff format** — the same behavior used for known CLI editors. The `_is_cli_editor()` check in `textual_plan_reviewer_editor.py` returns `False` for unknown editors, which currently routes to the before/after files (GUI) path. This MUST be changed so that unknown editors also route through the annotated diff path (`preview_edit_diff_viewer()` + `subprocess.run()` inside `app.suspend()`). Rationale: the annotated diff format is a reliable single-file approach that works with any editor, regardless of diff flag support or background process handling.
```

## Guidelines

### Phasing & Sequencing

1. **Phase 1 (Ice-Box):** Interface changes (IConfigService.set_setting() + YamlConfigAdapter implementation).
2. **Phase 2 (Foundation):** Default config change, ConsoleToolingHelper.discover_editors(), find_editor() sentinel handling, _DIFF_FLAGS expansion.
3. **Phase 3 (Core Logic):** Preflight check editor validation, prompting functions (_prompt_for_editor_selection, _prompt_for_custom_editor).
4. **Phase 4 (Diff Flags Refinement):** get_diff_viewer_command() unknown editor fallback + diff_flags config override.
5. **Phase 5 (Polish):** CLI editor set expansion, log message updates for "disabled" sentinel, test updates.

### Test Strategy

- **ConsoleToolingHelper:**
  - `discover_editors()`: Test with mocked `which()` returning paths for a subset of KNOWN_EDITORS. Verify deduplication (same path for different names).
  - `find_editor()`: Test "disabled" sentinel returns None. Test that config value `"disabled"` bypasses env fallback.
  - `get_diff_viewer_command()`: Test unknown editor returns `[editor_path]` (no flags). Test `diff_flags` config override precedence.
- **YamlConfigAdapter.set_setting():**
  - Test with non-existent config file (creates it).
  - Test with existing file, verify the new setting is merged and written.
  - Test dot-notation (e.g., `editor` vs empty).
- **Preflight Check:**
  - Test with setup_editor=True, empty config → discover and prompt.
  - Test with setup_editor=False → skip editor validation.
  - Test with configured editor available → no prompt.
  - Test with "disabled" sentinel → skip validation.
  - Test with configured but missing editor → warn and fall through to discovery.
- **Prompting Flow:**
  - Mock `typer.prompt` to simulate numbered selection, custom command, and empty input.
  - Verify `config_service.set_setting` is called with the correct value.
  - Verify "disabled" sentinel is saved on empty input.

### Risk Assessment

- **Breaking change to IConfigService protocol:** Impact is limited — only one production implementation (YamlConfigAdapter). Test harness mocks using `spec=IConfigService` must be updated. This is manageable and justified.
- **Circular DI concern:** The prompting uses direct `typer.prompt()` calls rather than `IUserInteractor` to avoid `ConsoleToolingHelper` being pulled into a DI cycle. This is an acceptable design trade-off for a one-off CLI interaction.
- **Config write race condition:** `YamlConfigAdapter.set_setting()` uses read-modify-write. In single-user CLI usage, this is safe. No concurrent access expected.
