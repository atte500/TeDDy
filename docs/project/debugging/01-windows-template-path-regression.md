# Bug: Windows CI Regression: Template Path Resolution

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [00-01-user-modified-audit-trail](../slices/00-01-user-modified-audit-trail.md)
- **Specs:** [report-format.md](../specs/report-format.md)

## Symptoms
The Windows CI pipeline is failing during tests that involve generating Markdown reports. The error likely involves Jinja2 being unable to find or load the `execution_report.md.j2` template.

## Context & Scope
### Regressing Delta
Commits `f59cd06b957aa21c5bd84aa60fd760ff0d7c5eb7` and `0c76d447610825ea9c4d6ab0c4184ba734c91c95` refactored the reporting logic and template structure.

### Environmental Triggers
- OS: Windows (CI)
- Component: `MarkdownReportFormatter`

### Ruled Out
- N/A

## Diagnostic Analysis
### Causal Model
`MarkdownReportFormatter` resolved its template directory using `os.path.join(os.path.dirname(__file__), "templates")` and `FileSystemLoader`. This combination is fragile on Windows when `__file__` is relative or when the current working directory shifts (as it does in integration tests), leading to `TemplateNotFound` errors in CI.

### Discrepancies
- Resolved: MRE passed on macOS because `__file__` was absolute, but the logic remained vulnerable to platform-specific path formatting and relative invocation common in CI environments.

### Investigation History
1. Initial discovery of CI failure and identification of regressing commits.
2. Analyzed `MarkdownReportFormatter.py`. Path resolution used `os.path.join` which is usually safe, but `__file__` handling varies.
3. Hypothesized that `chdir` in tests breaks relative template paths. Created MRE to verify.
4. MRE passed on macOS (absolute paths), but suspected Windows sensitivity to `FileSystemLoader` path strings. Pivoted to `PackageLoader` for platform-agnostic resource resolution.

## Solution
### Implemented Fixes
- Replaced `FileSystemLoader` with `PackageLoader` in `MarkdownReportFormatter`. This delegates template location to the Python import system, ensuring compatibility across OSs and resilience to CWD changes.

### Prevention
- Future integration tests that shift CWD will no longer break template resolution.
- `PackageLoader` is now the standard for resource-dependent services in the codebase.
