# Bug: macOS CI DNS Timeout in Web Scraper Tests

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](/docs/project/milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

Tests in `tests/integration/adapters/outbound/test_web_scraper_github_scraping.py` fail on macOS CI runners with a `Timeout (>5.0s)` from `pytest-timeout`.

The stack trace indicates the hang occurs in `socket.getfqdn('127.0.0.1')` called by `werkzeug.serving.BaseWSGIServer` during `pytest-httpserver` initialization.

## System Model

### Understanding
Integration tests use `pytest-httpserver` to mock GitHub API and HTML responses. The underlying `werkzeug` server calls `socket.getfqdn('127.0.0.1')` to determine the server name. On macOS CI runners, this reverse DNS lookup hangs.

Patching `socket.getfqdn` to return a static value like `'localhost'` bypasses the network lookup and allows the server to bind instantly.

### Discrepancies
None. The root cause is the blocking nature of `socket.getfqdn` on misconfigured CI runners.

## Solution

### Implemented Fixes
- Added a session-scoped `autouse` fixture `patch_socket_getfqdn` in `tests/conftest.py`.
- The fixture patches `socket.getfqdn` to return `'localhost'` immediately, bypassing environment-dependent DNS lookups that were timing out.

### Prevention
- This is a systemic fix in the root `conftest.py`. Any future tests utilizing `pytest-httpserver` or `werkzeug` servers will benefit from this patch automatically, preventing the recurrence of DNS-related timeouts in the test harness.
