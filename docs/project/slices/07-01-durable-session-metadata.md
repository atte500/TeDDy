# Slice: Durable Session Metadata Writes
- **Status:** Planned
- **Milestone:** [Milestone 7: Runtime Reliability & Boundary Purity](/docs/project/milestones/07-runtime-reliability.md)
- **Depends On:** [06-01-literal-helper-single-sourcing](./06-01-literal-helper-single-sourcing.md)
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [ISessionManager](/docs/architecture/core/ports/outbound/session_manager.md), [SessionService](/docs/architecture/core/services/session_service.md), [IFileSystemManager](/docs/architecture/core/ports/outbound/file_system_manager.md), [LocalFileSystemAdapter](/docs/architecture/adapters/outbound/local_file_system_adapter.md)
- **Scope Slug:** `durable-session-metadata`

## Goal
Make a hard kill during a metadata write leave either the previous file or the new one, never a truncated third state, so `teddy resume` cannot lose the cumulative cost ledger or fail on a `ParserError` it caused itself.

## Context
- The defect is measured: `SessionRepository.save_meta` (`session_repository.py:169`) serializes through `scrub_dict_for_serialization` and calls `self._file_system_manager.write_file(path, yaml.dump(serializable))`, while `LocalFileSystemAdapter.write_file` is a plain `Path.write_text`. There is no temp file and no rename, so the entire write is one uninterruptible window from the caller's point of view.
- Two distinct symptoms, both silent in different ways. A truncated YAML document raises `yaml.parser.ParserError` straight out of `teddy resume`, which is a crash on startup with no user-actionable message. A zero-length file is worse: `load_meta`'s fallback returns `{}`, so `cumulative_cost` and `cumulative_tokens` vanish and the Session Cost line reports a session that spent nothing — a wrong number presented confidently.
- `meta.yaml` also carries resume state and turn metadata, so the same corruption path changes what `resume` does rather than only what it reports. Slice [07-05](./07-05-resume-state-truth.md) records resume state in this file, which is why durable writes come first.
- Atomicity belongs on the port, not in the repository. `IFileSystemManager` is the only boundary that knows a disk exists, and the same window applies to every durable artifact written through it. The precedent is already in this codebase: the Web Content Cache law in `docs/architecture/ARCHITECTURE.md` mandates one locked read-modify-write with an atomic replace, so the pattern is established and this slice generalizes it rather than inventing it.
- Ordering against [06-01](./06-01-literal-helper-single-sourcing.md): the structural check below keys on the metadata artifact constant that slice introduces, and the repository's own path spellings move there in the same change. Ordering against [06-05](./06-05-domain-exception-hierarchy.md): that slice re-parents eleven bare raises inside this file, so a concurrent run needs a separate workspace and a rebase before merge.
- Sequencing constraint inherited from the milestone: do not fold the `execution.started` marker into this artifact until this slice lands, because the marker would sit inside the one file a hard kill actually corrupts and its absence would then misreport progress rather than merely losing a total.

## Scenarios

> As a user, I want a kill during a write to cost me nothing.

```gherkin
Given a metadata write that is interrupted after the temp file exists and before the rename
When the process is restarted and the session resumed
Then load_meta reads the previous, complete document
And the cumulative cost and token totals are the ones from before the write
```

> As a user, I want a corrupt file to be reported rather than crash the resume.

```gherkin
Given a metadata file truncated mid-document by a kill that predates the atomic write
When the session is resumed
Then a debug-level line names the file and the parse failure
And the corrupt file is preserved beside the original for inspection
And the session continues from defaults rather than raising a parser error
```

> As a maintainer, I want a bypass of the atomic path to fail the build.

```gherkin
Given a new call writing the session metadata through the non-atomic primitive
When the structural check runs
Then it exits non-zero naming the file and line
```

## Edge Cases
- **Same-directory temp file**: If the temp file is created in the system temp directory, then the rename crosses filesystems and degrades to a copy, which reintroduces the window; the temp file is created beside its target.
- **Durability versus atomicity**: If the rename succeeds but the directory entry is not synced, then a power loss can still lose the file; the adapter syncs the file before the rename and the directory after, and Windows documents `os.replace` as the boundary where that is best-effort.
- **Windows replace**: If the target is open by another process, then `os.replace` raises `PermissionError`; the adapter retries with a bounded backoff and raises a `TeddyError` subclass naming the path after the last attempt, because a silent failure here is the defect being fixed.
- **Permission preservation**: If the original file carried restrictive permissions, then the replacement inherits them rather than the process umask, because a metadata file readable by everyone is a new problem.
- **Leftover temp file**: If the process dies after the temp write, then a `<name>.tmp-<pid>` file survives; the next save removes stale siblings it owns, because accumulating debris in a session directory is its own failure mode.
- **Empty file**: If the file exists but is empty, then it is treated as corruption rather than as an empty document, because a legitimately empty metadata file is never written.
- **Quarantine naming**: If the corrupt file is preserved, then the copy carries a timestamp so two corruptions in one session do not overwrite each other's evidence.
- **In-memory double**: If the harness fake models the port, then it models the atomic operation with an injectable failure between the temp write and the rename, because a fake that only stores the final value cannot test the window.
- **Concurrent writers**: If two processes write the same session, then last-write-wins is accepted and documented, because session-level locking is outside this defect and pretending otherwise would overstate the guarantee.

## Key Unknowns
- [ ] [Technical] Whether `IFileSystemManager` should gain a separate atomic operation or every durable write should become atomic by default. Design Sensitivity: if the port gains one explicit atomic operation → the non-atomic primitive stays for genuinely disposable writes and the structural check distinguishes them, which is the more honest contract; if all durable writes become atomic by default → the cost is one extra rename per write and the check becomes unnecessary, but the in-memory fake and every adapter must model it, so the slice grows to touch each adapter's write path.

## Impact
1. `[NEW]` `IFileSystemManager.write_file_atomic` — with its preconditions, postconditions, and the failure it raises when the target cannot be replaced, documented on the port page.
2. `[MIGRATE]` `LocalFileSystemAdapter` — same-directory temp write, file sync, `os.replace`, directory sync, and bounded retry on a held target.
3. `[MIGRATE]` `SessionRepository.save_meta` — writes through the atomic operation.
4. `[MIGRATE]` `SessionRepository.load_meta` — a tolerant path that logs, quarantines a timestamped copy, and returns defaults instead of raising a parser error.
5. `[MIGRATE]` The in-memory filesystem fakes and the shared harness double — model the atomic operation and its injectable interruption.
6. `[NEW]` `.githooks/check_metadata_write_path.py` — a structural check failing on a non-atomic write of the session metadata artifact outside the repository.
7. `[MIGRATE]` `.pre-commit-config.yaml` and the `manual`-stage step list — register the new check.
8. `[NEW]` A unit test for the check covering the atomic call, a bypass, and an unrelated write to the same directory.
9. `[MIGRATE]` The four component pages above and `docs/architecture/ARCHITECTURE.md` — record the durability contract and the atomic-write law beside the existing Web Content Cache law.

## Deliverables
- [ ] **Env** — Add the metadata-write-path check, register it in the `manual` stage, and unit-test it against a bypass and an unrelated write.
- [ ] **Interface** — Land the atomic operation on the port with its durability contract, and state on the page which writes are disposable.
- [ ] **Harness** — Teach the shared filesystem double the atomic operation and the injectable interruption between its two stages.
- [ ] **Adapter** — Implement the atomic write with temp-in-place, sync, replace, and bounded retry.
- [ ] **Core** — Switch `save_meta` to the atomic operation and give `load_meta` its tolerant, logged, quarantining path.
- [ ] **Cleanup** — Record the durability contract on the four pages and in `ARCHITECTURE.md`, and confirm the stale temp-file sweep leaves no debris.

## Implementation Notes

## Verification
1. **Interruption:**
   Drive `save_meta` through the in-memory double with an injected failure between the temp write and the rename, then call `load_meta`.
   Verify the previous document is returned intact with its cost totals.
2. **Corruption tolerance:**
   Truncate a real `meta.yaml` mid-document inside a test workspace and resume the session.
   Verify a debug line names the parse failure, a timestamped copy exists beside the original, and the command does not raise.
3. **Check bites:**
   Add a `write_file` call on the metadata artifact to a scratch module and run `uv run python .githooks/check_metadata_write_path.py`.
   Verify it exits non-zero naming the file and line.
