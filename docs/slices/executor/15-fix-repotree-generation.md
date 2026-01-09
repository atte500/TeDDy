# Slice 15: Fix Repo Tree Generation Format

**Status:** In Progress

## 1. Business Goal
As a Developer, I want to change the `repotree.txt` output format from a visual tree to a simple indented list. This will fix a cross-platform bug on Windows, improve reliability, and make the format more token-efficient for the LLM that consumes it.

## 2. Scope of Work
1.  Modify the acceptance test `test_context_command_honors_teddyignore_overrides` to assert the new indented list format.
2.  Replace the `_TreeFormatter` class in `local_repo_tree_generator.py` with an `_IndentedListFormatter` that produces the desired output.
3.  Update the architectural notes in `ARCHITECTURE.md` to reflect the new canonical pattern for the repo tree generator.

## 3. Architectural Changes
-   The `LocalRepoTreeGenerator` adapter will now produce a simple, space-indented list instead of a visual tree with box-drawing characters. This is the new canonical format for machine-readable file hierarchies.
