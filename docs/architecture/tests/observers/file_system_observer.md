# Test Adapter: FileSystemObserver (Inverse Adapter)
- **Status:** Planned

## 1. Purpose / Responsibility
Acting as the **Observer** in the Test Harness Triad, the `FileSystemObserver` is a specialized test utility responsible for performing complex assertions against the local file system. It abstracts away low-level `pathlib` or `os` calls into a high-level, expressive API for verifying the results of file system operations.

## 2. Ports
- **Primary Driving Adapter:** Used by Integration and Acceptance tests to verify file system side-effects.

## 3. Implementation Details / Logic
- **Recursive Matching:** Provides methods to verify the structure and content of entire directories using glob patterns.
- **Content Verification:** Encapsulates common file content checks (e.g., "file contains string," "file matches regex").
- **Stateless Analysis:** Operates purely as a reader, never modifying the file system.

## 4. Data Contracts / Methods
- `assert_file_exists(path: Path) -> None`: Raises AssertionError if the file is missing.
- `assert_file_content_equals(path: Path, expected: str) -> None`: Verified exact content matching.
- `assert_directory_contains(root: Path, expected_files: list[str]) -> None`: Verifies that a directory contains exactly the specified relative paths.
- `assert_file_matches_pattern(path: Path, pattern: str) -> None`: Verified content against a regex.
