# Bug: Web Scraper Adapter GetTLD Import Error
- **Status:** Resolved
- **Milestone:** [02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md) (Milestone 2: Stability & Infrastructure - "GitHub Compatibility", "Web Scraper (403 Bypassing)")
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
**Expected:** `READ` action with a URL resource (e.g., `https://en.wikipedia.org/wiki/United_States`) fetches and returns the page content. URLs in `init.context` should be fetched and included in context content.

**Actual:** Two related symptoms:
1. Web scraping fails with `cannot import name 'get_tld' from 'tld'` (imported from `/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/tld.py`).
2. When a URL is added to `init.context`, the context output shows `--- FILE NOT FOUND ---` for that entry. This is a consequence of symptom 1: the web scraper fails, so `context_service.py` marks the URL content as `None` (via its `except Exception` block), which then renders as "--- FILE NOT FOUND ---". See `context_service.py` lines ~84-87.

**Minimal Reproduction Steps (for the root cause):**
1. Use system Python (Python 3.14) without activating the Poetry virtualenv.
2. Run `python3 -c "from tld import get_tld"` — this fails with `ImportError: cannot import name 'get_tld' from 'tld'`.
3. The system site-packages contains a standalone `tld.py` file (16411 bytes) which shadows the proper `tld` package (a directory with `__init__.py`).

**Local Reproduction (within Poetry virtualenv):**
- The MRE (deleted after fix) succeeded via Poetry run, confirming the issue was environment-specific (outside Poetry). The regression test at `tests/suites/integration/adapters/outbound/test_bug_03_tld_regression.py` permanently covers the import chain verification scenario.

## Context & Scope
### Regressing Delta
The `tld` package is not a direct dependency of TeDDy (not listed in `pyproject.toml`). It is an indirect dependency, likely pulled in by `trafilatura` (version `^2.0.0`). The installed version is `tld==0.13.1`. The regressing delta could be:
- A `tld` version upgrade from a compatible version (which included `get_tld`) to `0.13.1` (which may have removed/renamed it).
- A `trafilatura` version change that switched to a newer `tld` API.
- The system environment has a globally installed `tld.py` (system Python at `/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/tld.py`) that shadows the correct package.

### Environmental Triggers
- Python 3.14 (system-installed).
- `tld==0.13.1` installed via Poetry.
- The error trace points to `/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/tld.py` — this is the system Python site-packages, NOT the Poetry virtualenv path. This suggests the import resolution is picking up a system-level `tld.py` module instead of the Poetry-managed `tld` package. (Note: Poetry `run` should activate the virtualenv, but if the system environment has a `tld.py` file shadowing the package, it could cause this.)

### Ruled Out
- Direct import of `get_tld` in `web_scraper_adapter.py`: The adapter does not import `tld` directly.
- Direct `tld` usage in TeDDy source: (to be confirmed via search).
- Python 3.14 incompatibility: (to be verified).

## Diagnostic Analysis
### Causal Model
**Verified Model:** The system Python 3.14 environment has a standalone `tld.py` file at `/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/tld.py` (16411 bytes). This file is not a proper `tld` package (it is a single module, not a directory with `__init__.py`). It does **not** expose the `get_tld` function that `trafilatura` expects. When TeDDy is installed via test PyPI using system Python (outside the Poetry virtualenv), Python resolves `import tld` to this standalone `tld.py` module instead of the properly installed `tld` package within the virtualenv. The Poetry virtualenv (Python 3.11) has the correctly installed `tld` package (version 0.13.1 as a directory at `.venv/lib/python3.11/site-packages/tld/`), which does provide `get_tld`.

The second symptom ("--- FILE NOT FOUND ---" for URLs in `init.context`) is a direct consequence: when the web scraper fails due to the import error, `context_service.py` catches the exception and sets `file_contents[url] = None`, which renders as "--- FILE NOT FOUND ---" in the context output. This is visible in the source at `context_service.py` lines ~84-87.

### Discrepancies
- Installed `tld==0.13.1` allows `from tld import get_tld` (succeeds locally), but the bug report shows the import fails. **(resolved: the bug occurs outside the Poetry virtualenv, where a standalone `tld.py` file shadows the proper package)**
- The error trace uses system Python path (`/Library/Frameworks/Python.framework/...`) rather than the Poetry virtualenv path. **(resolved: the user is running outside the Poetry virtualenv, likely via test PyPI installation using system Python 3.14)**

### Investigation History
1. **Hypothesis: get_tld is missing from the tld package due to an API breaking change.** Observation: Within the Poetry virtualenv, `from tld import get_tld` succeeds (tld==0.13.1 installed as a directory package). Conclusion: The bug is not a simple package version issue within the managed environment.
2. **Hypothesis: A system-level tld.py shadows the proper package when running outside Poetry.** Observation: A standalone `tld.py` (16411 bytes) exists at system Python's site-packages (`/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/tld.py`). The error trace references this path. Conclusion: When running without Poetry (e.g., test PyPI install using system Python), Python loads this standalone module, which lacks `get_tld`. The Poetry virtualenv has the correct installed package and works fine.
3. **Hypothesis: The "FILE NOT FOUND" for URLs in .context is a separate bug.** Observation: `context_service.py` catches exceptions from `self._web_scraper.get_content(url)` and sets `file_contents[url] = None`, which renders as "--- FILE NOT FOUND ---". Conclusion: This is a consequence of symptom 1, not a separate bug.

## Solution
**Root Cause:** There were two layers to this bug:

1. **System Python 3.14 shadowing:** A standalone `tld.py` file (16411 bytes) — an unrelated task list manager (package name `tld` version 1.0.1) — sat in `/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/`. When TeDDy was run outside the Poetry virtualenv (e.g., via test PyPI installation), Python resolved `import tld` to this rogue module, which does not expose `get_tld` (required by `courlan` → `trafilatura` chain).

2. **uv tool environment shadowing:** The same rogue `tld==1.0.1` package was pulled into the uv tool environment at `~/.local/share/uv/tools/teddy-cli/lib/python3.11/site-packages/tld.py`. This happened because the original dependency constraint `tld>=0.10` was too permissive — it allowed `tld==1.0.1` (which satisfies `>=0.10`) to be installed, shadowing the proper `tld` directory package (version 0.13.x) that provides `get_tld`.

**Fix Applied:**
1. **Added `tld>=0.10` as an explicit dependency in `pyproject.toml`** — ensures pip installs the correct `tld` package whenever TeDDy is installed, overwriting any conflicting files.
2. **Tightened constraint to `tld>=0.10,<1.0`** — prevents the rogue 1.0.1 version from being resolved, forcing `uv`/`pip` to install only the compatible 0.13.x versions that provide `get_tld`.
3. **Deleted the rogue `tld.py` file and its `tld-1.0.1.dist-info`** from:
   - `/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/` (system Python)
   - `/Users/raphaelatteritano/.local/share/uv/tools/teddy-cli/lib/python3.11/site-packages/` (uv tool environment)
4. **Added regression test** (`test_bug_03_tld_regression.py`) that verifies the tld import chain works in the managed environment.
5. **Cleaned up temporary probe scripts** after successful verification.

**Systemic Preventative Measures:**
- Adding `tld>=0.10,<1.0` as an explicit dependency prevents this entire class of import-shadowing bugs by ensuring the correct package is always explicitly required at install time. The upper bound `<1.0` prevents version-confusion attacks where a different package with the same name takes the same namespace.
- Future audit recommendation: review all dependency constraints in `pyproject.toml` for overly permissive lower bounds that could allow similar version-confusion issues.
