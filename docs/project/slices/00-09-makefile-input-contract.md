# Slice: Makefile Input Contract
- **Status:** Completed
- **Milestone:** None (ad-hoc slice, not tracked in the Roadmap)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** None
- **Scope Slug:** `makefile-args`

## Goal
Make every Makefile input an explicit named variable so a message word can never become a build goal. An unknown target and a missing input must fail loudly, and the advisory pre-commit pass must read in plain language.

## Context
Discovery measured each behavior on GNU Make 4.4.1 under Windows `cmd.exe` and Git Bash.

- `Makefile`: `commit`, `probe`, and `logs` capture arguments from `$(MAKECMDGOALS)`. The `commit` recipe runs `-uv run pre-commit run`, and the file ends with `%: ;`.
- GNU Make on Windows keeps one quoted argv element as one goal name. A POSIX shell strips the quotes before Make starts, so the same message becomes separate word goals.
- A word goal that names a real target runs that target. `make commit 'fix: probe test'` under Git Bash runs the `probe` target, which pushes a commit and dispatches a CI workflow.
- `%: ;` absorbs every unknown goal and exits 0 with `make: '<word>' is up to date.` A typo such as `make tset` therefore succeeds silently.
- Make preserves `#` inside a quoted command-line variable value. The probe printed `MSG=[fix: close #42]` intact.
- Make reports an ignored recipe failure on stderr as `make: [file:line: target] Error 1 (ignored)`.
- `SHELL := bash.exe` and `.SHELLFLAGS := -c` apply only when `OS` is `Windows_NT`. `_preflight` gates `ci-watch`, `probe`, and `logs`.
- `tests/suites/unit/test_default_make_targets.py` pins `.PHONY` membership, `_preflight` prerequisites, the `-uv run pre-commit run` line, cmd-safe recipes, ASCII output, and byte-identical makefile template copies.
- Two byte-identical makefile templates exist: `docs/templates/makefile.md` and `src/teddy_executor/resources/templates/makefile.md`.
- The command surface also appears in `src/teddy_executor/resources/MRP.md`, six agent prompts, `docs/templates/PROJECT.md`, `docs/templates/ARCHITECTURE.md`, `docs/templates/ci.md`, `docs/architecture/ARCHITECTURE.md`, `docs/project/PROJECT.md`, and the bundled copies under `src/teddy_executor/resources/`.
- No CI workflow, hook, or script calls the affected targets, so every consumer lives in tracked documentation and prompts.
- `ci-watch` already reads named variables (`COMMIT=`, `BASE=`), so the variable form matches the existing surface.

## Scenarios
Primary user journeys. These drive the End-to-End Acceptance Tests in the Wiring deliverable.

> As an agent, I want a commit message to arrive as data so that no word of it can run another target.

```gherkin
Given a clean worktree
When I run `make commit MSG="fix(quit-key): speed up quit"`
Then Make commits exactly that subject
And no other target runs
```

```gherkin
Given a message that names real targets
When I run `make commit MSG="fix: probe test"`
Then Make commits that subject
And neither `probe` nor `test` runs
```

> As a user, I want a typo and a missing input to fail loudly so that a broken command never looks successful.

```gherkin
Given a misspelled goal
When I run `make tset`
Then Make aborts with `Unknown target 'tset'`
And the exit code is non-zero
```

```gherkin
Given no goal
When I run `make`
Then Make prints the target list from the `help` target
```

> As an agent, I want the advisory pre-commit pass to explain itself so that a non-blocking failure is not mistaken for a defect.

```gherkin
Given the advisory pre-commit pass reports a problem
When `make commit MSG="..."` continues
Then one sentence states that auto-fixes were re-staged
And the commit proceeds
```

## Edge Cases
Boundary conditions and validation cases. These drive the granular Unit Tests in the Logic deliverables.

- **Comment character:** If a message contains `#`, then the full text reaches `git commit -m`, because Make preserves it inside a quoted variable value.
- **Extra goal:** If the caller appends a goal, then Make aborts before any recipe line runs, because a goal word can execute a real target.
- **Legacy positional form:** If the caller passes the message positionally, then Make aborts and names `MSG=`, because silent acceptance preserves the goal hazard.
- **Empty input:** If `MSG` is empty or whitespace, then Make aborts with a usage line, because Git rejects an empty subject.
- **Optional step:** If `STEP` is omitted, then `make logs RUN=<id>` extracts every failed step, because the step filter is optional.
- **Unknown target:** If a goal names no rule, then Make aborts with the goal name and a pointer to `make help`, because the current catch-all hides typos.
- **Default goal:** If Make runs with no goal, then it builds `help`, because `.DEFAULT_GOAL` names a real target.
- **Advisory pass:** If the first pre-commit pass exits non-zero, then one sentence reports the fallback, because `Error 1 (ignored)` reads as an unexplained failure.
- **Cmd safety:** If `commit`, `push`, or `test` run on `cmd.exe`, then they must not call `awk`, `sed`, `grep`, `command -v`, or `sleep`, because those programs are POSIX-only.
- **Expansion hazard:** If a value contains `$` or a backtick, then the documented guard still forbids it, because Make and the shell both expand those characters.
- **Template lockstep:** If a project regenerates templates, then the bundled and project makefile copies must match byte for byte, because a drift test pins them.
- **Local prompts:** If `.teddy/prompts/` exists, then it needs `teddy init prompts` to receive the new invocations, because init never overwrites on startup.

## Key Unknowns
None remain. The spike suite measured goal splitting, quoting, `#` preservation, unknown-target failure, help selection, and shell routing on GNU Make 4.4.1 under `cmd.exe` and Git Bash.

## Impact
Map every affected consumer through non-breaking steps.

1. `[EXPAND]` `Makefile.help` — Add a `help` target and set `.DEFAULT_GOAL := help`.
2. `[EXPAND]` `Makefile` named inputs — Add `MSG`, `REASON`, `RUN`, and `STEP` with native validation beside the existing positional capture.
3. `[MIGRATE]` `Makefile.commit` — Read `MSG` with a positional fallback, and replace the advisory `-` prefix with an explicit fallback report.
4. `[MIGRATE]` `Makefile.probe` and `Makefile.logs` — Read `REASON`, `RUN`, and `STEP` with a positional fallback.
5. `[MIGRATE]` `MRP.md` and the six agent prompts — Update every documented invocation to the variable form.
6. `[MIGRATE]` Template and documentation copies — Update both makefile templates, the PROJECT, ARCHITECTURE, and ci templates, the project dashboard, and the architecture document.
7. `[CONTRACT]` `%: ;` catch-all — Replace it with a pattern rule that aborts on an unknown target, and add the extra-goal guard to `commit`, once every consumer uses real targets.
8. `[CONTRACT]` Positional `MAKECMDGOALS` capture — Delete the target-specific `ARGS`, `REASON`, `LOGS_RUN`, and `LOGS_STEP` variables once the recipes read named inputs.

## Deliverables

- [x] **Wiring** - Add the `help` target and set `.DEFAULT_GOAL := help`, so a bare `make` prints the target list.
- [x] **Contract** - Introduce `MSG`, `REASON`, `RUN`, and `STEP` with native validation, and make `commit`, `probe`, and `logs` read them.
- [x] **Logic** - Pass the resolved message to `git commit -m`, replace the advisory `-` prefix with an explicit fallback report, and update the structural guard assertions in the same commit.
- [x] **Migration** - Update `MRP.md`, the makefile template copies, the PROJECT, ARCHITECTURE, and ci template copies, the project dashboard, the architecture document, the debugger prompt, and the affected case file to the variable form.
- [x] **Cleanup** - Delete the positional capture, replace the `%: ;` catch-all with a parse-time goal check and a real `help` target, and remove the stale advisory-prefix rationale.

## Implementation Notes
- Keep `make commit` usable at every commit, because the Developer records each deliverable with it. The positional capture must stay until the migration deliverable lands.
- The structural guard pins the advisory `-` prefix, so update its assertions inside the same deliverable that changes the recipe. Keep that module under the 300-line limit.
- Both makefile template copies must change byte for byte in one commit, because a drift test pins them.
- Local `.teddy/prompts/` copies never refresh on startup, so run `teddy init prompts` after the prompt migration.
- Recipe output must stay ASCII so a Windows console cannot mojibake the log.
- `commit`, `push`, and `test` must stay free of `awk`, `sed`, `grep`, `command -v`, and `sleep`.

## Verification
1. **Help default:**
   Run `make`.
   Verify the output lists `commit`, `push`, `test`, `probe`, and `logs`.
2. **Loud typo:**
   Run `make tset`.
   Verify the output names `tset` and points to `make help`, and the exit code is non-zero.
3. **Rejected legacy form:**
   Run `make commit 'fix: probe test'`.
   Verify Make aborts with the extra-goal message and that no probe or test recipe output appears.
4. **Message integrity:**
   Run `make commit MSG="test(scratch): verify #42"`.
   Run `git log -1 --pretty=%s`.
   Verify the subject reads `test(scratch): verify #42`, then run `git reset --hard HEAD~1`.
5. **Usage errors:**
   Run `make probe` and `make logs`.
   Verify both abort with a usage line naming `REASON=` and `RUN=`.
6. **Advisory replacement:**
   Run `git grep -n "uv run pre-commit run" -- Makefile`.
   Verify no recipe line starts with `-uv run`.
