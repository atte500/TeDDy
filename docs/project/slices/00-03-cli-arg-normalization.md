# Slice: CLI Arg Case-Insensitivity & Path Normalization

- **Status:** Draft
- **Type:** Bugfix
- **Milestone:** N/A
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** N/A
- **Scope Slug:** `cli-arg-normalization`

## Business Goal

Users should be able to specify the `-a/--agent` argument with any case (e.g., `Developer`, `DEVELOPER`, `developer`) and the system should resolve the correct prompt file. Additionally, paths passed via `-c/--context` should be normalized to root-relative form (strip leading slash, `./` prefix, normalize backslashes) to prevent downstream failures.

## Scenarios

> As a user, I want to start a session with `teddy start -a Developer` so that I don't have to remember the exact capitalization of agent names.

```gherkin
Feature: Case-insensitive agent name resolution

  Scenario: Matched with capitalized agent name
    Given the project has a prompt file `developer.xml` at `.teddy/prompts/developer.xml`
    When the user runs `teddy start -a Developer`
    Then the session is created with the developer prompt
    And no `ValueError` is raised
```

> As a user, I want to pass `/abs/path/file.md` or `./docs/readme.md` via `-c` and have them normalized to `abs/path/file.md` and `docs/readme.md` so that context resolution works correctly.

```gherkin
Feature: Context path normalization

  Scenario: Path with leading slash is normalized
    Given the user runs `teddy start -c /abs/path/file.md`
    Then the path `abs/path/file.md` appears in `session.context` without leading slash

  Scenario: Path with ./ prefix is stripped
    Given the user runs `teddy start -c ./docs/readme.md`
    Then the path `docs/readme.md` appears in `session.context`

  Scenario: Backslash paths are normalized (Windows)
    Given the user runs `teddy start -c docs\guide.md`
    Then the path `docs/guide.md` appears in `session.context`
```

## Edge Cases

- **Casefold Collision**: If two prompt files differ only by case, the first casefold match wins. This is acceptable because duplicate agents differing only by case are a user configuration error.
- **Empty Context Entries**: `-c ""` or trailing commas must not append empty lines to `session.context`.
- **Preserved Leading Dots**: Normalization must strip only the exact `./` prefix; paths like `.hidden/file.md` must retain their leading dot.

## Implementation Plan

The fix spans 5 files and 2 distinct bug categories. All changes are localized and testable via the existing MRE (`spikes/debug/16-cli-case-insensitive-mre.py`) and new unit tests. The shared helper extraction is deferrable but recommended for maintainability.

## Deliverables

1. [ ] **Contract** - No new interfaces required.
2. [ ] **Harness** - Regression tests for `session_repository.copy_prompt` (casefold match), `prompts.find_prompt_content` (case-insensitive lookup), and `session_service` (`create_session` + `_prepare_session_context`).
3. [ ] **Seam** - No new abstractions.
4. [ ] **Wiring** - No new wiring required.
5. [ ] **Logic** - Apply casefold in `session_service.py:83`, `session_service.py:522`, `session_repository.py:139`. Add path normalization in `session_service._prepare_session_context`. Make `prompts._search_prompt_in_dir` case-insensitive.
6. [ ] **Migration** - No upgrade path required.
7. [ ] **Refactor** - Extract a shared `normalize_path()` helper to reduce duplication with `_extract_resource_path`.
8. [ ] **Cleanup** - Remove superseded `00-03-casefold-agent-name-comparison` debt entry after merge.

## Implementation Notes

Filled by the Developer as things get implemented.

## Verification

1. `USE_SHADOW=1 python3 spikes/debug/16-cli-case-insensitive-mre.py` passes with exit code 0.
2. Unit tests for `_clone_session_artifacts` pass.
3. Unit tests for `session_repository.copy_prompt` pass with a case-insensitive agent name.
4. Unit test for `prompts.find_prompt_content("developer")` returns content.
5. Unit test for `prompts.find_prompt_content("DEVELOPER")` returns the same content.