# Slice: Systemic Encoding Fix for Test Suite
- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **MRE:** [spikes/debug/18-mre-systemic-fix.py](../../../spikes/debug/18-mre-systemic-fix.py)

## Business Goal
Ensure the test suite is resilient to platform-specific encoding differences (Windows `cp1252` vs `utf-8`) by forcing a global UTF-8 default for file operations in tests.

## Scenarios
> As a developer running tests on Windows, I want file read/write operations in tests to default to UTF-8, so that I don't encounter UnicodeEncodeErrors when using emojis or non-ASCII characters.
```gherkin
Given a test writes a file containing "🟢" using Path.write_text() without an explicit encoding
When the test is executed on a Windows runner
Then the file is written correctly using UTF-8
And no UnicodeEncodeError is raised
```

## Deliverables
- [ ] **Harness** - Implement `pytest_configure` hook in `tests/conftest.py` to monkeypatch `pathlib.Path.read_text` and `pathlib.Path.write_text`.
- [ ] **Cleanup** - Revert the manual `encoding="utf-8"` additions in `tests/suites/acceptance/test_context_management_ui.py` (optional, as the global fix covers it).

## Implementation Guidelines
### Systemic Monkeypatch logic
The following logic should be added to `tests/conftest.py`:

```python
import pathlib
import functools
from pathlib import Path

def pytest_configure(config):
    original_write_text = Path.write_text
    original_read_text = Path.read_text

    @functools.wraps(original_write_text)
    def utf8_write_text(self, data, encoding=None, errors=None, newline=None):
        if encoding is None:
            encoding = "utf-8"
        return original_write_text(self, data, encoding=encoding, errors=errors, newline=newline)

    @functools.wraps(original_read_text)
    def utf8_read_text(self, encoding=None, errors=None):
        if encoding is None:
            encoding = "utf-8"
        return original_read_text(self, encoding=encoding, errors=errors)

    Path.write_text = utf8_write_text
    Path.read_text = utf8_read_text
```
