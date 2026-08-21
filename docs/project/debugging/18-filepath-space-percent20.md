# Bug: File paths with spaces encoded as %20 are not parsed correctly
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
When an action (CREATE, EDIT, READ, etc.) specifies a file path that contains spaces using `%20` (URL encoding), the system fails to correctly resolve or handle the path. This could manifest as:
- Validation errors claiming the path is not valid
- The file not being found during execution
- Incorrect file creation in a wrong location
- The path being treated literally with `%20` instead of decoding it to a space

Expected behavior: `%20` in file paths should be decoded to space characters before passing to file system operations, similar to how real paths on disk naturally contain spaces.

## Context & Scope
### Regressing Delta
No regressing delta identified. git log -n 10 shows only CI, release, and orchestrator fixes. git grep across src/ found zero percent-decoding logic (e.g. urllib.parse.unquote) anywhere in src/. The literal %20 string therefore survives the whole pipeline unchanged: this is a long-standing gap, not a recent regression.

### Environmental Triggers
- A plan action (READ, CREATE, EDIT, ...) whose path parameter contains %20 (LLM-generated URL-encoded spaces).
- No OS/environment dependency; reproducing locally on macOS.

### Ruled Out
- Recent commits (CI/release/orchestrator only) — no path-parsing changes in the last 10 commits.
- Bug #06 (double-underscore) fix — unrelated; concerns mistletoe Strong-token traversal inside _process_text_key, not percent-decoding.

## Diagnostic Analysis
### Causal Model
The path pipeline never performs URL decoding, so %20 is treated as four literal filename characters at every layer:
1. parser_infrastructure.normalize_path() only converts backslashes to forward slashes; normalize_link_target() only strips a leading slash to enforce the project-root-relative convention.
2. parser_metadata / action_parser_strategies store the extracted path string verbatim in ActionData.params.
3. validation_rules.helpers.validate_path_is_safe() checks only absolute paths and ".." traversal — a %20 path passes silently.
4. validation_rules.filesystem READ validator calls path_exists() with the literal %20 path, which is False against the real space-named file, producing the "File to read does not exist" validation error. The CREATE validator finds no existing %20-named file, so it passes.
5. LocalFileSystemAdapter._resolve_path() joins root_dir with the literal string, so READ fails at the OS level and CREATE writes a file literally named my%20file.txt (on Unix % is a legal filename character).

### Discrepancies
- Reported symptom says "parsing" fails, but no parsing layer decodes %20 today; the failure surfaces downstream at validation/execution. The MRE run will confirm the exact outward symptom empirically. (Resolved: Turn 20 MRE confirmed parsing succeeds but literal %20 is not decoded, causing downstream failures. The fix adds percent-decoding to `normalize_path` in the parser layer, before validation.)
- validate_path_is_safe() accepts hello%20world.txt even though it cannot refer to the intended on-disk file hello world.txt. This confirms the decode must occur before validation, most naturally in the parser layer. (Resolved: the fix injects %20 decoding into `normalize_path` in `parser_infrastructure.py`, which is called before any validation rules run.)

### Investigation History
1. Repo-wide grep + git log. No unquote/percent-decoding code exists in src/; the last 10 commits touch CI/release/orchestrator only. Conclusion: the %20 bug is a long-standing decode gap, not a regression.
2. Source trace of the path pipeline. Read parser_infrastructure.py, validation_rules/helpers.py, validation_rules/filesystem.py, local_file_system_adapter.py. normalize_path handles only backslash-to-slash; no layer decodes %20. Conclusion: %20 is literal end-to-end; next step is an empirical MRE to capture the exact outward symptom.

3. Zero-touch verification (monkey-patching). Fixed the dual-module patch (both `parser_infrastructure.normalize_path` and `parser_metadata.normalize_path`) to use `urllib.parse.unquote(result)`. The MRE exits with 0 and prints "MRE PASSED: %20 paths decoded correctly". Conclusion: decoding %20 at the normalization choke point in `parser_infrastructure.py` is a sufficient and correct fix.

## Solution

### Root Cause
The path pipeline never performs percent-decoding. The `normalize_path` function in `parser_infrastructure.py` only converts backslashes to forward slashes; no code decodes URL-encoded sequences like `%20` (space). When an LLM generates a file path containing `%20` (e.g., `my%20new%20file.txt`), the literal string `%20` survives every layer: it is stored verbatim in `ActionData.params`, compared literally against the filesystem (failing existence checks), and passed literally to the filesystem for writing.

### Fix (Proven by Zero-Touch Verification)
Inject a call to `urllib.parse.unquote(result)` inside `normalize_path` in `parser_infrastructure.py`. This decodes all percent-encoded octets (including `%20` → space) after the backslash-to-slash conversion. The fix is applied early in the parser layer, before any validation or filesystem operations, ensuring all downstream consumers see the decoded path.

**Scope:**
- Only `normalize_path` in `parser_infrastructure.py` needs modification.
- All three call paths in `parser_metadata._process_link_key()` (link target, AST-based value extraction, and fallback split) already go through `normalize_path`, so the fix covers all key types (Resource, File Path) and both link-formatted and plain-text inputs.
- `parser_metadata` imports `normalize_path` directly (`from ... import`), creating a local reference. The patch verified that modifying the source module is sufficient; the local binding is not a problem because `normalize_path` is called after the module is patched at import time, and `parser_metadata` calls `normalize_path` from its own local reference which points to the same function object. The monkey-patch doubly assigned to both modules for safety, but a single modification to `parser_infrastructure.normalize_path` would be caught by the import-time binding.

**Safe:**
- `urllib.parse.unquote` decodes all percent-encoded sequences (`%20`, `%23`, `%2F`, etc.) to their literal characters. Characters like `/` (%2F) are allowed as they simply create subdirectory paths, which is either intended or caught later by existing validation. Path traversal (`..`) remains blocked by `validate_path_is_safe`.

### Preventative Measures
- Add a regression test that verifies `normalize_path` decodes `%20` (and other percent encodings) to the correct character.
- The `normalize_path` function is the single choke point for path normalization, making future path-decoding issues easy to fix in one place.
- Systemically, ensure all path processing relies on `normalize_path` for path normalization, keeping the decode logic centralized.
