# Slice: Ad-Hoc Context Selection for the Context Command
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc slice)
- **Depends On:** N/A
- **Specs:** [Manual CLI Workflow](/docs/project/specs/manual-cli-workflow.md), [Teddy Directory Structure](/docs/project/specs/teddy-directory-structure.md)
- **Prototype:** N/A
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md), [ContextService](/docs/architecture/core/services/context_service.md), [IGetContextUseCase](/docs/architecture/core/ports/inbound/get_context_use_case.md)
- **Scope Slug:** `context-file-selection`

## Goal
Let `teddy context` accept explicit files, directories, URLs, or a list file through a repeatable `-c/--context` flag. Explicit values extend the default `.teddy/*.context` set, and a `--only` flag suppresses the defaults for a single run.

## Context
- `src/teddy_executor/__main__.py` `context` command: The command exposes only `--no-copy` and calls `handle_context_gathering(container, no_copy)`.
- `src/teddy_executor/__main__.py` `start` command: The command exposes repeatable `-c/--context`, splits each occurrence on commas, and strips whitespace inline.
- `src/teddy_executor/adapters/inbound/session_cli_handlers.py` `handle_context_gathering`: The handler calls `detect_session_context()` and passes the result as `context_files` to `get_context`.
- `handle_context_gathering` composition: Additive export keeps the detected scopes and adds an `Explicit` scope. Outside a session the defaults come from `IFileSystemManager.get_context_paths()`, which expands the `.teddy/*.context` manifests.
- `ContextService._resolve_scoped_paths`: A falsy `context_files` value triggers the `.teddy/*.context` glob. An explicit list is wrapped under the `Default` scope and bypasses the glob.
- `ContextService._resolve_files_to_paths`: The service expands any path ending in `.context`, named `context`, or ending in `/context` as a manifest. The service expands directories recursively, then deduplicates while preserving order.
- `IFileSystemManager.resolve_paths_from_files`: The adapter reads a manifest line by line, ignores blank lines and `#` comments, skips entries with illegal filename characters, and returns a sorted deduplicated list.
- The `.context` suffix is the established manifest convention for `init.context` and `session.context`.

## Scenarios
> As a developer, I want to export an ad-hoc file set so that I can bundle context for a web chat without editing `.teddy/init.context`.

```gherkin
Given a project whose .teddy/init.context lists docs/ARCHITECTURE.md
When I run teddy context -c README.md -c src/app.py --no-copy
Then the payload lists README.md, src/app.py, and docs/ARCHITECTURE.md under Resource Contents
```

```gherkin
Given a project with README.md and docs/project/PROJECT.md
When I run teddy context -c "README.md,docs/project/PROJECT.md" --no-copy
Then the payload lists both files under Resource Contents
```

> As a developer, I want to keep my file list in a reusable manifest so that I can repeat the same export.

```gherkin
Given a file named review.context that lists README.md and docs/project/PROJECT.md
When I run teddy context -c review.context --no-copy
Then the payload lists both files named inside the manifest
```

```gherkin
Given a directory named docs/project
When I run teddy context -c docs/project --no-copy
Then the payload lists every file under that directory
```

> As a developer, I want the existing default behavior to stay stable so that current workflows keep working.

```gherkin
Given a project with .teddy/init.context listing README.md
When I run teddy context --no-copy
Then the payload includes README.md
```

> As a developer, I want a minimal payload so that I can paste only the files I choose.

```gherkin
Given a project whose .teddy/init.context lists docs/ARCHITECTURE.md
When I run teddy context --only -c README.md --no-copy
Then the payload lists README.md under Resource Contents
And the payload does not list docs/ARCHITECTURE.md
```

## Edge Cases
- **Explicit values extend defaults**: If any `-c` value is present, then the command exports the default set plus the requested entries, because the handler adds an `Explicit` scope beside the detected scopes.
- **Default set outside a session**: If an additive run happens outside a session, then the handler reads the defaults through `IFileSystemManager.get_context_paths()`, because `detect_session_context()` returns `None` there.
- **Default set inside a session**: If an additive run happens inside a session, then the Turn and Session scopes stay in place, because the handler keeps the detected map.
- **Suppression**: If `--only` is present, then the command exports the explicit entries alone, because the handler drops every other scope.
- **Suppression without values**: If `--only` is present without any `-c` value, then the command exits with a usage error, because an empty explicit set would drop every file.
- **No flags**: If no `-c` value is present, then `detect_session_context()` supplies the list as today, because the handler keeps its current fallback.
- **Comments and blank lines**: If a manifest line starts with `#` or is empty, then the reader skips the line, because `resolve_paths_from_files` ignores both.
- **Nested manifests**: If a manifest references another `.context` file, then the service expands the nested file recursively, because `processed_manifests` guards against cycles.
- **Missing path**: If a requested file does not exist, then the payload shows `--- FILE NOT FOUND ---`, because the formatter keeps its current missing-content branch.
- **Illegal filename characters**: If a manifest line contains `*?"<>|`, then the reader skips the line, because the adapter treats those characters as invalid.
- **Comma in a path**: If a single path contains a comma, then the flag splits it into two entries, because the normalization matches the existing `start` grammar.
- **URL values**: If a value starts with `http://` or `https://`, then the service passes it through unchanged and fetches it, because URL detection runs before filesystem resolution.
- **Duplicate values**: If the same file appears twice, then the payload lists it once, because path collection deduplicates.
- **Session directory**: If the command runs inside a session and receives `-c` values, then the explicit values join the Turn and Session scopes, because the handler adds an `Explicit` scope.
- **Shared paths across scopes**: If a path appears in both the default set and the explicit list, then the payload lists it once, because item collection deduplicates by path.

## Key Unknowns

**Format:**
- [x] [Domain] Scope: RESOLVED — the request targets the `context` command. The `start` command already supports `-c`. Design Sensitivity: none, because no session code changes.
- [x] [Technical] List-file format: RESOLVED — list files must use the `.context` suffix, because that is the only manifest convention the service recognizes. Design Sensitivity: arbitrary filenames would need a separate `--context-from` flag, which the user declined.
- [x] [Functional] Flag grammar: RESOLVED — mirror `start`: repeatable and comma-separated. Design Sensitivity: a different grammar would diverge from the documented `start` behavior.
- [x] [Domain] Precedence: RESOLVED — explicit values extend the default set, and `--only` suppresses the defaults. Design Sensitivity: additive merging needs a second scope plus a default lookup outside sessions.
- [x] [Functional] Suppression flag: RESOLVED — `--only` is a boolean option on `context`, because additive export needs an escape hatch. Design Sensitivity: a different flag name would change only the README wording.

## Impact
1. `[EXPAND]` `handle_context_gathering` — Add optional `context_files` and `only` parameters. Compose the detected scopes, the default glob, and the explicit list into one scope map, then forward it to the use case.
2. `[EXPAND]` `context` CLI command — Add the repeatable `-c/--context` option and the `--only` flag, then pass the normalized values to the handler.
3. `[REFACTOR]` `src/teddy_executor/__main__.py` — Extract the repeatable and comma-separated normalization into a shared helper and use it in `start` and `context`.
4. `[MIGRATE]` README and `docs/project/specs/manual-cli-workflow.md` — Document the flag, the `--only` escape hatch, and the `.context` list-file convention.
5. No contract changes. `IGetContextUseCase`, `ContextService`, and `IFileSystemManager` stay untouched.

## Deliverables
- [x] **Wiring** - Add `-c/--context` and `--only` to the `context` command and pass the normalized list to `handle_context_gathering`. The handler composes an `Explicit` scope beside the detected scopes, or beside the `.teddy/*.context` defaults outside a session. Drive an acceptance test that asserts the requested file and an `init.context` entry appear together.
- [x] **Logic** - Cover the composition matrix through the public command: additive beside `init.context` outside a session, additive beside the Turn and Session scopes inside a session, `--only` suppression, `--only` without `-c`, manifest expansion, directory expansion, and a missing path.
- [ ] **Refactor** - Extract the repeatable and comma-separated normalization helper and reuse it in `start`. Keep the existing `start` behavior and tests green.
- [ ] **Cleanup** - Document the usage concisely in the README. Add an `### Exporting Context` subsection under Usage covering the additive default, the `--only` escape hatch, and the `.context` manifest requirement. Update the `context` row in the Command Reference and the `context` description in `docs/project/specs/manual-cli-workflow.md`.

## Implementation Notes

**Wiring (deliverable 1):**
- The `context` command accepts repeatable `-c/--context` and the `--only` flag.
- Comma splitting stays inline in `__main__.py`, mirroring `start`. Extracting the shared helper remains the Refactor deliverable.
- `handle_context_gathering` adds an `Explicit` scope beside the detected Turn and Session scopes.
- Outside a session `detect_session_context()` returns `None`. The handler then resolves the defaults through `IFileSystemManager.get_context_paths()`.
- The handler resolves the defaults itself because `ContextService._resolve_scoped_paths` globs `.teddy/*.context` only when the whole scope map is falsy.
- `--only` without a `-c` value raises `typer.BadParameter` before any scope work happens.
- The acceptance test in `tests/suites/acceptance/test_context_file_selection.py` asserts that the `init.context` entry and the explicit file both appear under `## Resource Contents`.
- The global suite passes with 1944 passed and 5 skipped.

**Logic (deliverable 2):**
- The composition matrix is covered through the `context` command in `tests/suites/acceptance/test_context_file_selection.py`.
- The six new tests cover additive export inside a session, `--only` suppression, `--only` without `-c`, manifest expansion, directory expansion, and a missing path.
- The Wiring deliverable already satisfied that matrix, so all six tests passed on the first run and lock the behavior as regression coverage.
- `detect_session_context()` returns a Turn and Session map only when `turn.context`, `../session.context`, and `meta.yaml` all exist. Every other location returns `None`.
- `--only` without a `-c` value exits with the Click usage code 2 before any scope work happens.
- Manifest expansion, directory recursion, and the missing-path renderer stay covered at the service layer, so the command-level tests assert only the rendered paths.
- The repeated arrange block moved into the file-local `_run_context` helper, which drives the real filesystem and the real init service.
- The global suite passes with 1950 passed and 5 skipped.

## Verification
1. **Additive direct files:**
   Run `teddy context -c README.md -c pyproject.toml --no-copy`.
   Verify both files and the existing `init.context` entries appear under `## Resource Contents`.
2. **Suppression:**
   Run `teddy context --only -c README.md --no-copy`.
   Verify `README.md` appears and no `init.context` entry appears.
3. **Comma-separated values:**
   Run `teddy context -c "README.md,pyproject.toml" --no-copy`.
   Verify both files appear under `## Resource Contents`.
4. **List file:**
   Create `review.context` with two project-relative paths on separate lines, then run `teddy context -c review.context --no-copy`.
   Verify the payload contains both files named in the manifest beside the `init.context` entries.
5. **Non-manifest file:**
   Create `files.txt` with two paths, then run `teddy context -c files.txt --no-copy`.
   Verify the payload embeds the literal text of `files.txt` instead of the paths written inside it.
6. **Default behavior:**
   Run `teddy context --no-copy`.
   Verify the payload matches the current output and includes the `init.context` entries.
