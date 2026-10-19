# Slice: Porcelain Git Status in Context Payload
- **Status:** Completed
- **Milestone:** N/A (ad-hoc slice)
- **Depends On:** N/A
- **Specs:** [Context Payload Format](/docs/project/specs/context-payload-format.md)
- **Prototype:** N/A
- **Component Docs:** [IEnvironmentInspector](/docs/architecture/core/ports/outbound/environment_inspector.md), [SystemEnvironmentInspector](/docs/architecture/adapters/outbound/system_environment_inspector.md), [ContextService](/docs/architecture/core/services/context_service.md), [ProjectContext](/docs/architecture/core/domain/project_context.md)
- **Scope Slug:** `porcelain-status`

## Goal
Deliver branch, upstream, and ahead/behind state in the context payload. Remove Git instructional text and the redundant Git subprocess from every turn.

## Context
- `IEnvironmentInspector` declares `get_git_status` and `get_full_git_status`.
- `SystemEnvironmentInspector.get_git_status` runs `git status -s`. The badge parser consumes its output.
- `SystemEnvironmentInspector.get_full_git_status` runs `git status`. The Markdown section and the `ProjectContext.git_status` field consume its output.
- `ContextService.get_context` calls both methods on every turn and passes each result to a separate consumer.
- `git status --porcelain -b` emits a `## <branch>...<upstream> [ahead N, behind M]` header followed by two-column file lines. The command ignores user color and prefix configuration.
- The verified clean output is `## main...origin/main`.
- `ContextService._format_content` injects the status body as raw Markdown, so a porcelain `##` header would become a sibling H2 heading to `## Git Status`.
- `_parse_git_status` assumes that every line describes a file and reads the code from the first two columns.
- A porcelain rename line reads `R  old -> new`, so the parser must key the badge by the new path.
- The `ProjectContext.git_status` docstring claims that the field holds `git status -s` output.

## Scenarios
> As a developer, I want the context payload to show my branch and upstream tracking so that the agent knows when a push is pending.

```gherkin
Given a clean repository on a branch with an upstream
When the context payload is generated
Then the Git Status section starts with the branch and upstream header
And the section contains no file lines
```

> As a developer, I want one deterministic Git call per turn so that the payload carries no tutorial noise and the turn stays fast.

```gherkin
Given a working tree with staged, unstaged, and untracked changes
When the context payload is generated
Then the Git Status section lists one two-column line per changed file
And the context item badges match the same status codes
```

```gherkin
Given a repository on a branch without an upstream
When the context payload is generated
Then the Git Status section names the branch without an upstream suffix
```

## Edge Cases
- **Branch header line**: If a status line starts with `##`, then the badge parser skips it, because the line carries branch metadata instead of a file status.
- **Heading collision**: If the status body renders without a fence, then the porcelain `##` header becomes a sibling heading, because Markdown reads a leading `##` as a heading. The body must stay fenced.
- **Untracked files**: If porcelain reports `??`, then the badge code becomes `U`, because the existing untracked convention stays in place.
- **Renames**: If porcelain reports `R  old -> new`, then the parser keys the badge by `new`, because the context item path reflects the new name.
- **Detached HEAD**: If the repository is in detached HEAD, then the header reads `## HEAD (no branch)`, because porcelain reports that literal.
- **Unborn branch**: If the repository has no commits, then the header reads `## No commits yet on <branch>`, and the parser skips it.
- **Non-git directory**: If Git is missing or the directory is not a repository, then the inspector returns `None`, and the section renders no fence, as today.
- **Clean tree**: If the working tree is clean, then the fenced block holds only the header line, because porcelain omits unchanged files.
- **User Git config**: If the user sets color or short-status prefixes, then the output stays stable, because `--porcelain` ignores that configuration.

## Key Unknowns

**Format:**
- [x] [Technical] Clean-repo output: RESOLVED — the command prints `## main...origin/main`. Design Sensitivity: a different header would change the parser skip and the spec example.
- [x] [Technical] Config independence: RESOLVED — `--porcelain` guarantees stable uncolored output. Design Sensitivity: without the flag, terminal color and localization could leak into the payload.
- [x] [Domain] Scope: RESOLVED — the request covers branch and upstream context plus the verbose-output removal. Design Sensitivity: live CI status would need a network adapter and a different policy, so it stays out of scope.

## Impact
1. `[MIGRATE]` `SystemEnvironmentInspector.get_git_status` — Run `git status --porcelain -b` and return its output. Keep `get_full_git_status` until every caller migrates.
2. `[MIGRATE]` `ContextService` — Consume one status value for the Markdown section and the badge parser. Skip the branch header and key renames by the new path.
3. `[MIGRATE]` `tests/harness/setup/mocks.py` and the consumer tests — Remove `get_full_git_status` expectations and assert the unified status.
4. `[CONTRACT]` `IEnvironmentInspector.get_full_git_status` — Delete the method from the port and the adapter after the last caller migrates.
5. `[MIGRATE]` Component docs and the `ProjectContext` docstring — Describe the single porcelain contract.

## Deliverables
- [x] **Wiring** - Run `git status --porcelain -b` in `SystemEnvironmentInspector.get_git_status`, render the single result inside a fenced block in `ContextService._format_content`, feed the same result to the badge parser, skip the `##` header in `_parse_git_status`, and update the shared mock plus the directly affected tests so the suite stays green. Drive an acceptance test that asserts the fenced branch header in the generated payload.
- [x] **Logic** - Cover the inspector and parser with unit tests for clean, dirty, upstream-less, detached, renamed, and non-git states.
- [x] **Migration** - Update the remaining consumer tests that still reference `get_full_git_status`, including the caching and performance suites.
- [x] **Cleanup** - Remove `get_full_git_status` from the port and adapter. Align the `ProjectContext` docstring and the four component docs with the porcelain contract.

## Implementation Notes

### Wiring
- `SystemEnvironmentInspector.get_git_status` now runs `git status --porcelain -b` and returns its standard output. `get_full_git_status` stays on the port and adapter until the later Migration and Cleanup deliverables remove the remaining test references.
- `ContextService.get_context` calls `get_git_status` once. That single value feeds the Markdown body, the `ProjectContext.git_status` field, and the badge parser. Production no longer calls `get_full_git_status`.
- `ContextService._format_content` wraps the status body with `embed_in_fence(git_status, "")`. The empty language tag yields a plain triple-backtick fence, so the porcelain `##` header stays inside a code block and does not become a sibling heading.
- `ContextService._parse_git_status` skips every line that starts with `##` and keys a rename line by the new path after `" -> "`. The `??` to `U` mapping is unchanged.
- The new acceptance test `tests/suites/acceptance/test_context_git_status_header.py` drives `teddy context` and asserts the fenced branch header. The affected unit, acceptance, and integration tests now feed porcelain values and assert the single inspector call.

### Logic
- `tests/suites/unit/core/services/test_context_git_status_parsing.py` drives the public `get_context` path with a parametrized matrix. The cases cover a clean repository with an upstream, a branch without an upstream, `## HEAD (no branch)`, `## No commits yet on main`, a dirty tree with an untracked file, and a rename keyed by the new path.
- A separate case feeds `None` as the status and asserts the Git Status section stays unfenced with empty item badges, because the inspector returns `None` outside a repository.
- No inspector unit test was added. The porcelain command, the returned output, the non-git failure, and stdin isolation already carry integration coverage in `tests/suites/integration/adapters/outbound/test_system_environment_inspector.py`, so an inspector unit test would duplicate existing assertions.
- The parser rules already existed before the matrix, because the Wiring tracer bullet had to keep the acceptance test green. The matrix therefore locks the behavior instead of driving it, and the missing Red failure is explained rather than papered over.

### Migration
- `tests/suites/unit/core/services/test_context_service.py` no longer references `get_full_git_status`. Every fixture setup drops the stale default, and the session-history test now feeds a clean porcelain value to `get_git_status` alone.
- The truncated `test_get_context_populates_context_items_with_metadata` now ends with a porcelain status, an Act step that calls `get_context`, and assertions for the `M` and `U` badges plus the token counts.
- `tests/harness/setup/mocks.py` drops the obsolete `get_full_git_status` default from the shared `IEnvironmentInspector` mock, so a stray call would fail loudly instead of returning `None`.
- A `git grep "get_full_git_status" -- tests` returned no matches after the edits. The caching and performance suites never referenced the method, so they needed no change.
- `IEnvironmentInspector.get_full_git_status` and its adapter implementation stay in place. The Cleanup deliverable removes both after the last caller migration, as the user constrained.

### Cleanup
- The contract test now carries `test_environment_inspector_contract_excludes_full_git_status`. It asserts the method is absent from both `IEnvironmentInspector` and `SystemEnvironmentInspector.__dict__`. The Red run failed on the port assertion while the method survived.
- `IEnvironmentInspector.get_full_git_status` and `SystemEnvironmentInspector.get_full_git_status` are deleted. The adapter keeps only `get_git_status`, which runs `git status --porcelain -b`.
- The `ProjectContext.git_status` docstring now names the `git status --porcelain -b` output. The four component docs describe the single-call, single-method porcelain contract.
- A focused run over the contract, context service, and parser suites reported 26 passed. A scoped `git grep "get_full_git_status" -- src tests docs/architecture` returned only the two intentional absence assertions in the contract test.
- The full suite passed with 1866 passed and 5 skipped, so the removal is contained.

## Verification
1. **Clean repository header:**
   Run `teddy context` in the TeDDy repository.
   Verify the fenced body starts with `## main...origin/main` and contains no `On branch` or `(use "git ...")` text.
2. **Dirty working tree badges:**
   Stage one file and create one untracked file, then run `teddy context`.
   Verify the section lists `M  <file>` and `?? <file>` and the context item badges show the matching codes.
3. **Missing upstream:**
   Run `teddy context` in a temporary repository that has commits but no upstream.
   Verify the header shows the branch name without an `...origin/...` suffix.
4. **Fenced payload:**
   Run `teddy context` in the TeDDy repository.
   Verify the Git Status body sits inside a fenced block and the branch header does not render as a heading.
