# Bug: CLI Agent Name Case-Insensitivity and Context Path Normalization

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

**1. Agent name case-insensitivity**
- **Expected:** `teddy start -a Developer` (capital D) should resolve to the `veloper.xml` prompt file.
- **Actual:** The comparison `Path(f).stem == options.agnet_name` in `session_service.py:83` is case-sensitive. Passing `Developer` raises a `ValueError: "Agent prompt 'Developer' not found in .teddy/prompts/."`

**2. Context path leading-slash normalization**- **Expected:** Passing `/home/user/file.txt` via `-c` should either reject absolute paths gracefully or normalize them to root- relative (e.g., remove leading /).
 - **Actual:** The path is inserted as- is into `additional_context` in `_prepare_session_context` without stripping the leading slash. Later path resolution fails because the leading / pushes the path outside the project root.

## Context & Scope

### Regressing Delta
Both issues are pre-existing behaviors, not recent regressions. The causative code paths are:
1. `session_ervice.py:83` — `if Path(f).stem == options.agent_name` is an exact, case-sensitive stem comparison against prompt filenames. Prompt files are lowercase (e.g., `developer.xml`), so any case variant of `-a` fails. The same exact-match pattern also exists in `_ lone_session_artifacts`and `session_repository.py` (~line 139 per the PROJECT.md slice `00-03` audit note).
2. `ession_service.py::_ prepre_session_context` — entries from `options.additional_context`( the `- c` flag) are appended verbatim, without stripping leading slashes, `./` prefixes, or normalizing backslashes. The class already owns `_ extract_resource_path()` which performs exactly this normalization (used for READ/CREATE/EDT resorce dedup), but it is not reused for `-` seeding.
3. `session_cli_handlers.py::_ run_cli_prefight_check` — calls `prompt_manager.get_prompt_content(agent)` beore session
real estate; this   is another case-sensitive gate that must be aligned for an end-to-end fix.

### Environmental Triggers
Any OS with a case- sensitive filesystem (Linux/MacOS) triggers the agent name bug. Path normalization issue is cross-platform.

### Ruled Out
- Not related to YAML parser, LLM client, or orchestration.
- Not related to session lifecycle or pruning.

## Diagnostic Analysis

### Causal Model
- **Bug 1 (Agent name case-insensitivity):** `SessionService.create_session()` iterates the entries of `".teddy/prompts"` and compares `Path(f).stem == options.agent_name` with exact equality. `"developer" != "Developer"`, so `prompt_filename` remains `None` and a `ValueError` is raised even though `.teddy/prompts/developer.xml` exists. The same exact-match pattern is used by `_ lone_session_artifacts` and `session_repository.py`; the preflight gate `prompt_manager.get_prompt_content(agent)` is an additional case-sensitivity boundary.
- **Bug 2 (Context path normalization):** `start` splits `-c` on commons into `SessionOption.additional_context`, and `_prepre_session_context()` appends each entry verbatim to the `session.context` lines. Paths like `/abs/path/file.md`, `./docs/readme.md`, or `docs\guide.md` keep their leading slash / `./` prefix / backslashes, so donstream root-relative resolution fails. The codebase already centralizes this normalization in `_ extract_resource_path()` but never applies it to `-c` seeding.

### Dsrcpancies
- None. The MRE empiricaly confirms both symptoms at the service level.

### Investigation History
1. Hypothesis: the stem comparison is case-sensitive. Observation: with `.teddy/prompts` present and only `developer.xml` listed, `create_session(agent_name="Developer")` still raises `ValueError`. Conclusion: the exact `stem == agent_name` comparison is the failing point — Bug 1 confirmed.
2. Hypothesis: `- c` entries are appended verbatim. Observation: `_prepre_session_context` output retained `/abs/path/file.md`, `./docs/readme.md`, and `docs\guide.md` unchanged. Conclusion: no normalization is applied to `additional_context` — Bug 2 confirmed.
3. Hypothesis: Both bugs are reproducible at the service level. Observation: MRE `spikes/debug/16-cli-case-insensitive-mre.py` exited with code 1, printing `[FAIL]` for the case-insensitive agent name test and for the path normalization test. Conclusion: both bugs are confirmed in the current source — Reproduction phase complete.
4. Hypothesis: The fixes (casefold comparison for agent name; path normalization for additional_context) resolve both bugs. Observation: Shadow file `spikes/debug/shadow_session_service.py` with both fixes applied was created. Running `USE_SHADOW=1 python3 spikes/debug/16-cli-case-insensitive-mre.py` exited with code 0, printing `[PASS] create_session('Developer') succeeded` and no `[FAIL]` lines. Conclusion: both fixes are empirically verified without touching production code.

## Solution

### Root Cause 1: Case-Sensitive Agent Name Matching

**Root Cause:** `session_service.py:83` (`create_session`), `session_service.py:522` (`_clone_session_artifacts`), and `session_repository.py:139` (`copy_prompt`) all use case-sensitive stem comparisons:
```python
if Path(f).stem == agent_name:
```
The glob `directory.glob(f"{prompt_name}.*")` in `prompts.py:_search_prompt_in_dir` is also case-sensitive. When a user passes `-a Developer` (capital D), the prompt file `developer.xml` (lowercase d) is not matched, causing a `ValueError` at the CLI preflight gate (`session_cli_handlers.py:_run_cli_preflight_check`) before `create_session` even runs.

**Proven Fix (Shadow Verification):** Replace all case-sensitive comparisons with casefold:
```python
if Path(f).stem.casefold() == options.agent_name.casefold():
```
For `prompts.py`, the lookup must become case-insensitive (e.g., iterate the directory and compare stems casefold). The MRE and shadow verification confirm this resolves the bug.

### Root Cause 2: Context Path Normalization

**Root Cause:** In `_prepare_session_context` (`session_service.py` ~116), entries from `options.additional_context` are appended verbatim without stripping leading slash, `./` prefix, or normalizing backslashes. The service already owns `_extract_resource_path()` which performs this exact normalization, but it is not reused for `-c` seeding.

**Proven Fix (Shadow Verification):** Replace the verbatim append loop with normalization:
```python
for path in options.additional_context:
    if path:
        normalized = path.strip().replace("\\", "/")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        normalized = normalized.lstrip("/")
        if normalized and normalized not in clean_lines:
            clean_lines.append(normalized)
```

### Systemic Preventative Measures

1. **Introduce a shared case-insensitive matching helper** (`Path(f).stem.casefold() == query.casefold()`) and use it in all agent-name resolution contexts: `session_service.py`, `session_repository.py`, and `prompts.py`.
2. **Establish a centralized path normalization helper** that handles leading slashes, `./` prefixes, and backslash normalization. Reuse it in both `_extract_resource_path()` and `_prepare_session_context()`, and consider expanding it to any other path-entry points.
3. **Audit all other file pattern matches** for case-sensitivity using the same casefold pattern to prevent recurrence.

The full fix requires a Vertical Slice covering 5 files and 2 distinct bug categories, with new regression tests for each gate.
