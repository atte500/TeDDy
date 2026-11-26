# Slice: Domain Exception Hierarchy and Boundary Translation
- **Status:** Planned
- **Milestone:** [Milestone 6: Cross-Cutting Consolidation](/docs/project/milestones/06-cross-cutting-consolidation.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [SessionService](/docs/architecture/core/services/session_service.md), [ShellAdapter](/docs/architecture/adapters/outbound/shell_adapter.md), [WebScraperAdapter](/docs/architecture/adapters/outbound/web_scraper_adapter.md), [CLI Adapter](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `domain-exception-hierarchy`

## Goal
Make error handling decidable from the type alone: every domain rejection raises a `TeddyError` subclass with a name that says what failed, every boundary translates its library's failure into one of those subclasses, and the outer controllers catch that root so a user sees a clean line while a programming defect still fails fast.

## Context
- `TeddyError` already exists at `src/teddy_executor/core/domain/models/exceptions.py` and `PdfExtractionError` already inherits from it, so this slice re-parents the remaining exceptions rather than inventing the root.
- Existing exceptions to re-parent: `ConfigurationError`, `FileAlreadyExistsError`, `MultipleMatchesFoundError`, `SearchTextNotFoundError`, `WebSearchError`, `InvalidPlanError`, `LlmApiError`, `PlanValidationError`.
- Inconsistent bases to standardize: `FileAlreadyExistsError` inherits from `FileExistsError`/`OSError` and `SearchTextNotFoundError` from `ValueError`, so a caller's `except OSError` or `except ValueError` silently catches a domain rejection today.
- Bare built-in raises, measured: 21 in `src/`, of which 11 sit in `session_repository.py` — every one a domain rejection ("No sessions found", "could not resolve session from path", "not found", "already exists") — plus 2 each in `session_service.py`, `action_factory.py`, and `session_cli_handlers.py`, and 1 each in `string.py`, `session_orchestrator.py`, `execution_orchestrator.py`, and `shell_adapter.py`. The milestone named only `session_manager.py` and `session_service.py`, so `session_repository.py` is the largest unlisted site.
- Boundary translation gap: `WebScraperAdapter` leaks `trafilatura` and HTTP/socket exceptions across `IWebScraper.get_content` while its component page claims it raises a web-content error, and its silent empty-string returns make a blocked page indistinguishable from an empty one.
- Naming collision to resolve in the same pass: `InvalidPlanError` (parse-time syntax), `PlanValidationError` (semantic pre-flight), and `ValidationError` — a report DTO dataclass in `core/domain/models/plan.py`, not an exception at all.
- Enforcement gap: an `En` hook exists for six other structural rules but nothing forbids a bare `raise ValueError` in `src/`, which is why the count reached 21 while `ARCHITECTURE.md` already forbade it.
- Consumer contract: the CLI and TUI catch `TeddyError` for user-facing reporting, and the current stdlib bases mean a `ValueError` from `session_repository.py` is handled by whichever `except` happens to wrap it — including a bare `except Exception` from the sweep's inventory, which would mislabel a not-found as an unexpected defect.

## Scenarios

> As a user, I want a missing session reported as one clean line.

```gherkin
Given a resume targeting a slug that does not exist
When the command runs
Then the CLI prints a single not-found message naming the slug
And no traceback is shown
```

> As a maintainer, I want a path escaping the project root to be distinguishable from a bad argument.

```gherkin
Given an EXECUTE action whose cwd resolves outside the project root
When the shell adapter prepares the command
Then it raises WorkingDirectoryEscapeError naming the path
And the plan is rejected pre-flight
```

> As a maintainer, I want a blocked scrape to be distinguishable from an empty page.

```gherkin
Given a remote page that returns an empty document
When the scraper extracts content
Then it raises WebScrapeError naming the URL and the reason
And it never returns an empty string in place of a failure
```

## Edge Cases
- **`except OSError` compatibility**: If a re-parented `FileAlreadyExistsError` stops inheriting `OSError` and a caller catches `OSError`, then that caller silently stops catching it; every such site is grepped and migrated in the same commit, because dropping a base is a behavioural change even when the raise is unchanged.
- **Dual inheritance**: If a domain rejection must stay catchable both as `TeddyError` and as the stdlib type its callers rely on, then it dual-inherits explicitly rather than keeping the stdlib base alone, because the root class is what the outer controllers catch.
- **Message text**: If a user-facing string is currently built from the bare raise's message, then the subclass preserves that text verbatim, because this slice changes types and not wording.
- **Pickling and `args`**: If a subclass overrides `__init__`, then it passes its message to `super().__init__`, because a dropped `args` makes a logged exception unreadable.
- **Interrupt and exit**: If a bare raise carries a control-flow meaning, then it never becomes a `TeddyError`, because `KeyboardInterrupt` and `SystemExit` carry exit semantics this repository depends on.
- **Tests asserting the stdlib type**: If a test asserts `pytest.raises(ValueError)`, then it changes to the domain subclass in the same commit, because the assertion is the contract and leaving it would keep the old type alive in spirit.
- **Boundary that cannot translate**: If a scraper failure has no observable reason (a socket reset mid-read), then the error names the URL and carries the original exception as its cause, because losing the cause loses the diagnosis.
- **DTO rename ripple**: If `ValidationError` is renamed, then every report template, observer parser, and byte-exact assertion that names it is updated in the same commit, because a partially renamed DTO breaks report parsing silently.

## Key Unknowns
- [ ] [Technical] Whether any caller narrows on the stdlib base of a re-parented exception (`except OSError` for `FileAlreadyExistsError`, `except ValueError` for `SearchTextNotFoundError` or any of the 21 bare raises). Design Sensitivity: if no caller does → each exception drops its stdlib base outright and the hierarchy becomes single-rooted; if a caller does → that exception dual-inherits and its page records why, because a silently orphaned handler is worse than an impure hierarchy.

## Impact
1. `[MIGRATE]` `src/teddy_executor/core/domain/models/exceptions.py` — re-parent every existing exception under `TeddyError`, and add `SessionNotFoundError`, `SessionAlreadyExistsError`, `InvalidSessionPathError`, `WorkingDirectoryEscapeError`, `UnknownActionError`, and `WebScrapeError`.
2. `[MIGRATE]` The 21 bare built-in raises — replaced by the named subclass, starting with the 11 in `session_repository.py`.
3. `[MIGRATE]` `WebScraperAdapter` — wrap scraping and network failures, and replace the silent empty-string returns with a typed failure naming the URL.
4. `[MIGRATE]` `ValidationError` in `core/domain/models/plan.py` → `ValidationFinding`, with every template, parser, and assertion updated.
5. `[MIGRATE]` The CLI and TUI controllers — catch `TeddyError` for user-facing reporting and let unexpected defects keep their traceback.
6. `[NEW]` `.githooks/check_domain_exception_types.py` — a structural check failing on a bare `raise ValueError`, `RuntimeError`, or `Exception` in `src/`.
7. `[MIGRATE]` `.pre-commit-config.yaml` and the `manual`-stage step list — register the new hook.
8. `[MIGRATE]` The four component pages above plus `ARCHITECTURE.md` — record the hierarchy, the translation contract per adapter, and the hook as the enforcement.

## Deliverables
- [ ] **Env** — Add the bare-raise hook, register it in the `manual` stage, and wire it into the structural-check step list.
- [ ] **Interface** — Land the re-parented hierarchy and the six new subclasses, documenting each one's meaning and its owning layer on the exception module.
- [ ] **Harness** — Unit-test the hook, and add a table-driven assertion that every `TeddyError` subclass is reachable from the root and carries a non-empty message.
- [ ] **Core** — Replace the 21 bare raises and re-parent the existing exceptions, proving each user-facing message is byte-identical.
- [ ] **Adapter** — Translate the scraper boundary and rename the `ValidationError` DTO with every consumer updated.
- [ ] **Cleanup** — Record the hierarchy and the translation contract on the four component pages and in `ARCHITECTURE.md`, and remove the milestone bullets this slice delivers.

## Implementation Notes

## Verification
1. **Root catch works:**
   Run `uv run teddy resume nonexistent-slug`.
   Verify one not-found line prints, with no traceback and a non-zero exit.
2. **Programming defect still fails fast:**
   Force an `AttributeError` inside a service on a scratch branch and run the CLI.
   Verify the traceback is complete rather than reported as a user error.
3. **Boundary:**
   Point the scraper at an unreachable host and call `get_content`.
   Verify it raises `WebScrapeError` naming the URL rather than returning an empty string.
4. **Hook bites:**
   Add `raise ValueError("x")` to a scratch module and run `uv run python .githooks/check_domain_exception_types.py`.
   Verify it exits non-zero naming the file and line.
