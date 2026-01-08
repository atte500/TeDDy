**Status:** Implemented

# Vertical Slice: `.teddyignore` Override

## 1. Business Goal
To provide users with fine-grained control over the context provided to the AI. Users must be able to exclude files from the `repotree` output using a `.teddyignore` file, and critically, to also re-include specific files or directories that are ignored by `.gitignore`. This allows a clean separation between the version control context and the AI's operational context.

## 2. Acceptance Criteria (Scenarios)

**Scenario 1: Re-include a file ignored by `.gitignore`**
```gherkin
Given a project with the following structure:
  - a file "dist/index.html"
  - a file "dist/bundle.js"
And a ".gitignore" file containing:
  """
  dist/
  """
And a ".teddyignore" file at the project root containing:
  """
  !dist/index.html
  """
When the user runs the "teddy context" command
Then the generated repotree output should contain "dist/index.html"
And the generated repotree output should not contain "dist/bundle.js"
```

## 3. Architectural Changes
-   **Adapter (`Outbound`):** `LocalRepoTreeGenerator`
    -   Modify the logic to load patterns from `.teddyignore` and apply them with higher precedence than `.gitignore` patterns.
-   **Documentation:** `README.md`
    -   Update the Project Roadmap to include this feature.
    -   Update the `context` command description to explain the new override capability.
-   **Documentation:** `docs/ARCHITECTURE.md`
    -   Add an architectural note detailing the design decision and precedence logic for `.teddyignore`.

## 4. Interaction Sequence
1.  The `LocalRepoTreeGenerator` is invoked.
2.  The generator first traverses the directory structure to find and load all patterns from all `.gitignore` files.
3.  It then checks for a `.teddyignore` file in the project root.
4.  If `.teddyignore` exists, its patterns are loaded and appended to the list of `.gitignore` patterns.
5.  The combined list of patterns (with `.teddyignore` patterns last) is used to initialize the pathspec matching library.
6.  The library processes the file tree, correctly applying the "last match wins" rule, which allows `!` patterns in `.teddyignore` to override ignore patterns from `.gitignore`.
7.  The final, filtered tree is generated.

## 5. Scope of Work

This section details the file-by-file changes required to implement this slice.

### Source Code

1.  **`packages/executor/src/teddy_executor/adapters/outbound/local_repo_tree_generator.py`**
    -   **Modify `_load_ignore_patterns` method (or equivalent logic):**
        -   The existing logic loads patterns from `.gitignore` files. Retain this.
        -   Add new logic to check for a `.teddyignore` file in the `root_dir`.
        -   If `.teddyignore` exists, read its patterns.
        -   **Crucially, append the `.teddyignore` patterns to the end of the `.gitignore` patterns list.** This ensures they have higher precedence when the `pathspec` is initialized.

### Test Code

1.  **`packages/executor/tests/acceptance/test_context_command.py`**
    -   **Create a new acceptance test:** `test_context_command_honors_teddyignore_overrides`
    -   **Test Setup:**
        -   Use the `repo_builder` helper to create a temporary directory structure.
        -   Create `dist/index.html` and `dist/bundle.js`.
        -   Create a `.gitignore` file with the content `dist/`.
        -   Create a `.teddyignore` file with the content `!dist/index.html`.
        -   Create a `.teddy/repotree.txt` file to trigger the tree generation.
    -   **Execution:**
        -   Run the `teddy context` command within the temporary directory.
    -   **Assertions:**
        -   Parse the output of the command to find the `repotree.md` content.
        -   Assert that the string `dist/index.html` **is present** in the repotree output.
        -   Assert that the string `dist/bundle.js` **is not present** in the repotree output.
