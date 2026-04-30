# Bug: VS Code Opening New Instance from TUI

- **Status:** Unresolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
When opening a file or diff from the TUI (Textual Plan Reviewer), VS Code opens in a new window/instance rather than reusing the existing one.

## Context & Scope
### Regressing Delta
TBD. Likely an omission of the `-r` flag in the editor resolution logic or TUI invocation.

### Environmental Triggers
- VS Code installed and in PATH.
- macOS (Darwin) observed, but likely platform-independent logic issue.

### Ruled Out
- TBD.

## Diagnostic Analysis
### Causal Model
The `ConsoleToolingHelper` resolves the editor command. While it handled the `-r --diff --wait` flags correctly for the *diff viewer* when `code` was detected, the `find_editor` method (used for general file editing and capturing messages) simply returned the path to the executable without these flags when it fell back to "discovery mode" or when resolving a simple "code" string from config/env.

### Discrepancies
- `get_diff_viewer_command` uses `["code", "-r", "--diff", "--wait"]` but `find_editor` used `["code"]`. Conflict: Inconsistent behavior for the same tool. (resolved: confirmed in `console_tooling.py`)

### Investigation History
1. Found `console_tooling.py` and `textual_plan_reviewer_editor.py` as primary suspects.
2. Verified `console_tooling.py` logic: Fallback discovery loop for "code" only returned `[path]`.
3. Created MRE `debug/mre_editor_reuse.py` to confirm the missing flags.
4. Implemented fix in `ConsoleToolingHelper` to append `-r --wait` for VS Code.

## Solution
### Implemented Fixes
- Updated `ConsoleToolingHelper.find_editor` to append `['-r', '--wait']` when VS Code is discovered as a fallback.
- Updated `ConsoleToolingHelper._resolve_editor_cmd` to append `['-r', '--wait']` when a simple "code" command is resolved from environment variables or configuration.

### Prevention
- A regression test in `tests/suites/unit/adapters/outbound/test_console_tooling_editor.py` will verify that discovery of `code` includes the necessary flags.
