# Slice 11: CLI Performance Optimization (Lazy Loading)

## 1. Business Goal

To reduce the CLI's cold-start latency from ~2.3 seconds to under 0.5 seconds. Snappy CLI response times are critical for the "Interactive Session Workflow" to feel responsive. The current slowness is caused by the greedy loading of heavy third-party libraries (`litellm`, `trafilatura`) during the Dependency Injection container initialization.

## 2. Acceptance Criteria (Scenarios)

### Scenario: CLI is snappy
- **Given** the `teddy` tool is installed.
- **When** I run `time poetry run teddy --help`.
- **Then** the command MUST complete in less than 0.5 seconds (real time).

### Scenario: Heavy libraries are lazy-loaded
- **Given** I am profiling imports with `python3 -X importtime`.
- **When** I run `teddy --help`.
- **Then** the output MUST NOT show `litellm` or `trafilatura` being imported.
- **And** when I run `teddy execute` with a plan requiring an LLM, the libraries MUST be loaded on-demand.

## 3. Architectural Changes

- **Lazy Imports:** Modify adapters that wrap heavy external libraries to use internal/local imports within their methods or `__init__`, rather than global/module-level imports.
- **Lazy DI Registration:** Refactor `src/teddy_executor/container.py` to use `punq`'s lazy resolution capabilities, avoiding any calls to `container.resolve()` during the registration phase.

## 4. Scope of Work

1. [ ] **Adapter Refactor:**
   - In `src/teddy_executor/adapters/outbound/litellm_adapter.py`, move `import litellm` inside the class or its methods.
   - In `src/teddy_executor/adapters/outbound/web_scraper_adapter.py`, move `import trafilatura` and `import pycurl` inside the class or its methods.
   - In `src/teddy_executor/adapters/outbound/web_searcher_adapter.py`, move `from duckduckgo_search import DDGS` inside the class or its methods.
2. [ ] **Container Refactor:**
   - Update `src/teddy_executor/container.py` to register components using the `factory` pattern or ensuring no eager resolutions happen in `create_container()`.
   - Specifically, ensure `PlanValidator` registration doesn't eagerly resolve its sub-validators if they trigger adapter imports.
3. [ ] **Verification:**
   - Run `time poetry run teddy --help` to verify the fix.
   - Use `PYTHONPATH=src python3 -X importtime -m teddy_executor --help 2> import_times.txt` and check that heavy hitters are gone.
