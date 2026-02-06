# RCA: `LocalFileSystemAdapter` Path Resolution Bug

## 1. Executive Summary

Acceptance tests for file operations (`CREATE`, `EDIT`, `READ`) were failing with a `Read-only file system` error. The investigation revealed a two-part root cause:
1.  **Test Implementation Flaw:** The tests were not using the canonical `runner.isolated_filesystem()` context manager, which is required for isolating file I/O during `typer.testing.CliRunner` invocations.
2.  **Latent Application Bug:** This test flaw exposed a critical bug in `LocalFileSystemAdapter._resolve_path`, where it misinterpreted project-root-relative paths (e.g., `/hello.txt`) as filesystem-absolute paths, causing the application to attempt writes to protected areas of the disk.

The solution involves fixing the application bug and updating the test suite to use the correct isolation pattern.

## 2. The Diagnostic Journey

### Symptom

The initial MRE showed consistent failures in `tests/acceptance/test_markdown_plans.py`. The test would set up files in a temporary directory (`pytest`'s `tmp_path`), but the application, when run via `CliRunner`, would fail to find or create them, resulting in a non-zero exit code.

### Initial Hypothesis: CWD Mismatch

The first hypothesis was that `CliRunner` did not change the Current Working Directory (CWD) to the test's `tmp_path`. An **Oracle Spike** confirmed this was true: `CliRunner` runs from the project root by default. This led to the conclusion that tests must use `runner.isolated_filesystem()`.

### Discovery of Deeper Bug

When the `isolated_filesystem` pattern was applied to the failing test, the error changed. Instead of a simple failure, a much more specific error emerged from the application:

```
details: "Failed to create file at /hello.txt: [Errno 30] Read-only file system: '/hello.txt'"
```

This revealed the problem was not just CWD management. The application was actively trying to write to the filesystem root (`/`), not the temporary directory.

### Root Cause Isolation

A second, more focused spike was created to test `LocalFileSystemAdapter` in isolation. This test confirmed that calling `adapter.create_file('/hello.txt', ...)` would raise a "Read-only file system" error.

The flawed logic was in the `_resolve_path` method:
```python
# FLAWED LOGIC
def _resolve_path(self, path: str) -> Path:
    path_obj = Path(path)
    # On Unix, Path('/hello.txt').is_absolute() is True.
    # This caused the method to return Path('/hello.txt') immediately,
    # bypassing the logic that should join it with the adapter's root_dir.
    if path_obj.is_absolute():
        return path_obj

    if path.startswith("/"):
        path = path[1:]
    return self.root_dir.resolve() / path
```

## 3. The Verified Solution

The solution is a two-part patch.

### Part 1: Fix the Application Bug

The `_resolve_path` method in `src/teddy_executor/adapters/outbound/local_file_system_adapter.py` must be corrected to handle project-relative paths before checking for absolute paths.

```diff
--- a/src/teddy_executor/adapters/outbound/local_file_system_adapter.py
+++ b/src/teddy_executor/adapters/outbound/local_file_system_adapter.py
@@ -14,19 +14,18 @@
     def _resolve_path(self, path: str) -> Path:
         """
         Resolves a path relative to the root_dir.
-        Handles root-relative paths (e.g., '/file.txt') by stripping the
+        Handles project-root-relative paths (e.g., '/file.txt') by stripping the
         leading slash before joining with the root directory.
         """
-        # If path is absolute, use it directly. Otherwise, treat as relative.
+        # Strip leading slash first to treat it as relative to root_dir.
+        # This ensures that a path like '/file.txt' is not misinterpreted
+        # as a filesystem-absolute path by Path.is_absolute() on Unix.
+        if path.startswith("/"):
+            path = path[1:]
+
         path_obj = Path(path)
+        # If path is now absolute after stripping, use it directly.
+        # This would only happen on Windows with paths like 'C:\...'.
         if path_obj.is_absolute():
             return path_obj

-        # Strip leading slash to treat it as relative to root_dir
-        if path.startswith("/"):
-            path = path[1:]
         return self.root_dir.resolve() / path
```

### Part 2: Fix the Test Pattern

All file-based acceptance tests must be updated to use the `runner.isolated_filesystem()` context manager. This ensures proper test isolation and CWD management.

```diff
--- a/tests/acceptance/test_markdown_plans.py
+++ b/tests/acceptance/test_markdown_plans.py
@@ -8,45 +8,44 @@
     When the user executes the plan,
     Then the file should be created with the correct content and the report is valid.
     """
+    # NOTE: This is just one example. The pattern should be applied to all
+    # file-based tests in this file (test_markdown_edit_action, etc.)
     # Arrange
     runner = CliRunner()
     file_name = "hello.txt"
-    new_file_path = tmp_path / file_name
+    plan_name = "plan.md"

     plan_content = f"""
 # Create a test file
 - **Status:** Green 🟢
 - **Plan Type:** Implementation
 - **Agent:** Developer
 - **Goal:** Create a simple file.

 ## Action Plan

 ### `CREATE`
 - **File Path:** [{file_name}](/{file_name})
 - **Description:** Create a hello world file.
-````text
+``````text
 Hello, world!
-````
+``````
 """
-    plan_file = tmp_path / "plan.md"
-    plan_file.write_text(plan_content, encoding="utf-8")
-
     real_container = create_container()

     # Act
-    with patch("teddy_executor.main.container", real_container):
-        result = runner.invoke(app, ["execute", str(plan_file), "--yes"])
+    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
+        plan_file = Path(td) / plan_name
+        plan_file.write_text(plan_content, encoding="utf-8")
+        new_file_path = Path(td) / file_name
+
+        with patch("teddy_executor.main.container", real_container):
+            result = runner.invoke(app, ["execute", str(plan_file), "--yes"])

     # Assert
     assert result.exit_code == 0, (
-        f"Teddy failed with stderr: {result.stderr}\\n{result.exception}"
+        f"Teddy failed!\\n"
+        f"Exception: {result.exception}\\n"
+        f"Stdout: {result.stdout}"
     )
     assert new_file_path.exists(), "The new file was not created."
     assert new_file_path.read_text() == "Hello, world!", (
         "The file content is incorrect."
     )

     # Verify the report output
     report = parse_yaml_report(result.stdout)
     assert report["run_summary"]["status"] == "SUCCESS"
     action_log = report["action_logs"][0]
     assert action_log["status"] == "SUCCESS"
```

## 4. Prevention

-   **Code Review:** When reviewing code that handles file paths, pay special attention to the handling of "magic" characters like `/` and `\`, especially in cross-platform contexts.
-   **Test Patterns:** The `runner.isolated_filesystem()` pattern should be documented and enforced as the standard for any acceptance test that interacts with the filesystem. This could be added to `docs/ARCHITECTURE.md`.
