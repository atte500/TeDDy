# Slice: "ls -R" Style Repository Tree Format
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Specs:** [context-payload-format.md](../specs/context-payload-format.md)

## Business Goal
Improve the clarity and familiarity of the repository tree for LLMs by adopting a recursive directory listing format similar to `ls -R`. This format provides explicit directory context for every file and reduces reliance on deep indentation, making it more resilient to parsing errors and more token-efficient.

## Scenarios

> As a Developer Agent, I want the project structure to be presented as a recursive list so that I can clearly identify the directory context of every file without tracking complex indentation.

```gherkin
Feature: Recursive Repository Tree Generation

  Scenario: Generate tree for root and subdirectories
    Given a repository with the following structure:
      | path                      |
      | README.md                 |
      | pyproject.toml            |
      | src/teddy/__init__.py      |
      | src/teddy/main.py         |
      | docs/specs/context.md     |
    When the tree generator is invoked
    Then the output should be exactly:
      """
      README.md
      docs
      pyproject.toml
      src

      ./docs:
      specs

      ./docs/specs:
      context.md

      ./src:
      teddy

      ./src/teddy:
      __init__.py
      main.py
      """

  Scenario: Root directory contents are sorted alphabetically intermingling files and folders
    Given a repository with the following files in the root:
      | path         |
      | src          |
      | README.md    |
      | z_end.txt    |
      | docs         |
    When the tree generator is invoked
    Then the first section (root) should be:
      """
      README.md
      docs
      src
      z_end.txt
      """
```

## Deliverables
- [ ] **Logic** - Replace `_IndentedListFormatter` with `_RecursiveListFormatter` in `src/teddy_executor/adapters/outbound/local_repo_tree_generator.py`.
- [ ] **Logic** - Update `LocalRepoTreeGenerator` to utilize the new formatter.
- [ ] **Refactor** - Update integration tests in `tests/suites/integration/adapters/outbound/test_local_repo_tree_generator.py` to match the new format.
- [ ] **Doc** - Update `docs/architecture/adapters/outbound/local_repo_tree_generator.md` to reflect the new output format.
- [ ] **Doc** - Update `docs/project/specs/context-payload-format.md` section 3.3 to match the new format.

## Delta Analysis
- **Current State:** The system uses `_IndentedListFormatter` which produces a space-indented tree with trailing slashes for directories and groups directories at the top.
- **Changes Needed:**
    - The new formatter should group entries by directory.
    - The root directory should NOT have a header.
    - Each subdirectory section MUST start with a `./path:` header followed by a blank line.
    - Sections MUST be separated by a blank line.
    - Within each section, entries are sorted alphabetically (case-insensitive).
    - No trailing slashes for directory names within the lists.

## Guidelines for Implementation
- Ensure that the recursion order for sections follows a depth-first or alphabetical traversal of directories.
- The `LocalRepoTreeGenerator._get_included_paths` method already provides the set of non-ignored paths; the formatter just needs to organize them.
- Be careful with path normalization; use `./` prefixes for all headers except the root.
- The existing `test_local_repo_tree_generator.py` has multiple scenarios (ignores, symlinks); all must be updated to the new format.
