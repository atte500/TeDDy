# Slice: Editor Seam Injection
- **Status:** Planned
- **Milestone:** [Milestone 7: Runtime Reliability & Boundary Purity](/docs/project/milestones/07-runtime-reliability.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [TextualPlanReviewer](/docs/architecture/adapters/inbound/textual_plan_reviewer.md), [ConsoleInteractorAdapter](/docs/architecture/adapters/outbound/console_interactor.md), [TestComposition](/docs/architecture/tests/setup/composition.md)
- **Scope Slug:** `editor-seam`

## Goal
Replace the six production reads of the test-only `TEDDY_TEST_MOCK_EDITOR_OUTPUT` variable with an injected editor-launch port, so no adapter in `src/` branches on harness state while the suite keeps every handover it currently observes.

## Context
- Six reads, measured. In `src/teddy_executor/adapters/inbound/textual_plan_reviewer_editor.py`: line 240 in `handle_mock_diff(p_file)`, which receives a path, writes the canned body into it, and returns whether it did; lines 280-281 in `launch_editor`, which short-circuits the entire async handover; and line 400 in `handle_mock_editor`, the helper `launch_editor` calls to write the body into the temp file it just created. In `src/teddy_executor/adapters/outbound/console_interactor.py`: line 68 in `prompt_for_message`, which returns a body with no file involved at all; and line 114 in `_launch_editor_synchronous`, which short-circuits its own temp-file-plus-subprocess path.
- The roles differ, so the replacement cannot be a single env-var-free branch. Two sites answer "produce a body" (`launch_editor`, `prompt_for_message`), one answers "produce a body, but into this path you were given" (`handle_mock_diff`), and one is the write half of the first (`handle_mock_editor`).
- The collaborators a real adapter needs are already injected on both sides: `launch_editor` resolves its temp path through `app._system_env.create_temp_file(suffix=...)` and its command through `app._console_tooling.find_editor()`, while `ConsoleInteractor` uses `self._system_env` and `self._tooling` the same way. `launch_editor` also accepts `persistent_path`, which edits a read-only manifest in place instead of a temp file, and `skip_confirm`, which skips the confirmation screen.
- Three behaviours must survive the move verbatim. `None` means dismissed and an empty string means the buffer was emptied, which is why the gate tests the variable's presence rather than its truthiness; the caller in `textual_plan_reviewer_editor.py` distinguishes the two so an emptied buffer clears the parameter and a dismissal leaves it untouched. The confirm gate reads `app.is_headless or skip_confirm` and must stay reachable. And the editor-availability check precedes `create_temp_file` deliberately, because creating a temp file first fails on Windows where `/tmp` does not exist; `_launch_editor_synchronous` mirrors this by returning `""` with a log line when the editor is disabled.
- The harness owns the variable's lifetime today. `tests/conftest.py`'s autouse `clean_test_env` deletes it before and after every test; `TuiDriver._install_mock_editor` sets it, swaps `create_temp_file.side_effect` for a real file under a `tempfile.mkdtemp()` directory, and records each requested suffix; and `tests/suites/acceptance/test_tui_edit_workflow.py` sets it twice through `monkeypatch.setenv`.

## Scenarios

> As a reviewer, I want my editor handover served by an injected seam instead of an environment variable.

```gherkin
Given a parameter value that needs the external editor
When I select it in the parameter list
Then the injected editor port receives the value and the requested suffix
And the body it returns is written back through the existing write path
```

> As a user replying to a message, I want the console prompt served by the same seam.

```gherkin
Given a prompt for a free-text message
When the editor port returns a body
Then the prompt returns that body without launching a process
And it creates no temp file, because the console path answers with text alone
```

> As a maintainer, I want a test that forgets to inject the double to fail loudly.

```gherkin
Given a test that composes the reviewer without injecting the editor double
When a handover occurs
Then the real adapter path runs and the test fails on its assertion
And no environment variable can make the launch silently succeed
```

## Edge Cases
- **Emptied buffer versus dismissal**: If the port returns an empty string, then the parameter is cleared, and if it returns `None`, then the parameter is untouched, because the two outcomes are different user intentions and the existing branch already distinguishes them by testing presence rather than truthiness.
- **Confirmation declined**: If the user rejects the confirmation screen, then the handover returns `None`, because a declined edit must be inert exactly as it is today.
- **Headless and `skip_confirm`**: If either flag is set, then no confirmation screen is pushed, because the manifest edit path depends on skipping it and the headless reviewer has nobody to ask.
- **No editor configured**: If no editor command resolves, then the handover returns `None` with a notification and creates no temp file, because the availability check must stay ahead of `create_temp_file` for Windows.
- **In-place path**: If a `persistent_path` is supplied, then the port edits that file and no temp file is created or harvested, because a session or turn manifest is edited where it lives.
- **Diff-preview answer**: If a caller supplies a path and asks for the body to be written into it, then the port's implementation writes it there, because the mock's whole purpose was to simulate a user having saved an edit into the after-file.
- **Suffix fidelity**: If a caller requests a suffix, then the port receives it verbatim, because the harness currently asserts on `.md` for messages and `.txt` for parameters and those assertions must keep meaning something.
- **Return value of the synchronous path**: If the console editor is disabled, then the synchronous path returns an empty string rather than `None`, because the existing message-reply flow treats the empty string as an abandoned reply rather than a dismissal.
- **No env fallback**: If the variable is set while the real adapter is composed, then nothing changes, because keeping a fallback would leave the test hook alive and defeat the slice.
- **Harness cleanup**: If the variable is deleted from `src/`, then `clean_test_env` keeps its CWD-restoration and detritus duties and drops only the variable branch, because those two duties guard a different failure mode.

## Key Unknowns
- [ ] [Harness] Whether one injected seam can serve all three observed roles — the async launch, the body-without-file console prompt, and the write-into-this-path diff answer — through a harness double without reintroducing global patching, given that `launch_editor` also carries the `None`/`""` distinction and the confirm gate while `handle_mock_diff` carries a path to write into. Design Sensitivity: if one port covers all three → one port, one real adapter, one double, and the six reads collapse to one collaborator on each side; if the diff-write role is genuinely a file write rather than an editor handover → that site consumes the existing `IFileSystemManager` double instead, the port covers only the two launch shapes, and one method disappears from the port.

## Impact
1. `[NEW]` The editor-launch port in `core/ports/outbound/` — an edit operation taking initial content, an optional suffix, and an optional in-place path, returning either the edited body or a dismissal, with the contract stating the `None` versus empty-string meaning.
2. `[NEW]` A real adapter implementing it over the injected shell executor, console tooling, and system environment, absorbing both launch bodies currently living inside the two adapters.
3. `[NEW]` An in-memory fake in `tests/harness/setup/` that records each handover and answers with an injected body, including the write-into-this-path case.
4. `[MIGRATE]` `textual_plan_reviewer_editor.py` — the four reads become one injected collaborator; `handle_mock_diff` and `handle_mock_editor` lose their reason to exist once the fake answers the handover.
5. `[MIGRATE]` `console_interactor.py` — the two reads become the same injected collaborator, keeping the empty-string return for a disabled editor.
6. `[MIGRATE]` The composition root — register the port and its real adapter, and thread the port into both adapters' constructors.
7. `[MIGRATE]` The harness — `TuiDriver._install_mock_editor` becomes constructor injection of the fake while `editor_launch_suffixes` keeps reporting what was requested; the two `monkeypatch.setenv` sites in the acceptance module switch to the fake; `clean_test_env` drops only the variable branch.
8. `[PRUNE]` The mock helpers in the editor module once nothing legitimate calls them.
9. `[MIGRATE]` The three component pages above plus `docs/architecture/ARCHITECTURE.md` — record the port in the Component Map and state on the reviewer page that parameter editing routes through it.
10. `[NEW]` A structural hook beside the existing `.githooks/check_*.py` family — exit non-zero when any module under `src/` reads a `TEDDY_TEST_*` variable, so the cleanliness this slice proves by grep becomes a rule the next adapter cannot quietly break.

## Deliverables
- [ ] **Interface** — Land the editor-launch port with its contract tests, stating the dismissal-versus-empty distinction and the in-place path semantics.
- [ ] **Harness** — Land the in-memory fake with recorded handovers, and rewire `TuiDriver` onto constructor injection while keeping its recorded suffixes observable.
- [ ] **Adapter** — Implement the real adapter over the injected collaborators, driven by a scripted editor command in a temporary directory so the launch is proven without a human editor.
- [ ] **Migration** — Point both adapters and the composition root at the port, convert the two acceptance tests onto the fake, and narrow `clean_test_env` to its CWD and detritus duties.
- [ ] **Cleanup** — Delete the mock helpers, verify no `TEDDY_TEST_MOCK_EDITOR_OUTPUT` read survives in `src/`, and update the component pages and the Component Map.
- [ ] **Env** — Add the `src/` test-hook structural hook, landing last rather than first because it can only exit zero once the reads are gone, with a unit case proving it fails on a scratch `TEDDY_TEST_*` read.

## Implementation Notes

## Verification
1. **Reviewer handover:**
   Start a session with a plan holding a multiline EXECUTE command and select the command in the parameter list.
   Verify your editor opens with the command and the edited body lands back in the parameter list.
2. **Hook is gone:**
   Run `git grep -n TEDDY_TEST_MOCK_EDITOR_OUTPUT -- src`.
   Verify it returns nothing, while `git grep` over `tests/` still finds nothing that depends on the variable.
3. **Console prompt:**
   Run `teddy resume -m ""` at a terminal and confirm the editor opens, then run it in a pipeline context and confirm it prompts nothing.
4. **The ratchet bites:**
   Add a scratch module under `src/` that reads `os.environ["TEDDY_TEST_DEMO"]` and run the new structural hook.
   Verify it exits non-zero naming that file, then delete it and verify the hook exits zero again.
