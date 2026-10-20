# Bug: Subprocess Output Decode Failure Leaks Traceback
- **Status:** Resolved
- **Milestone:** N/A (harness defect)
- **Vertical Slice:** N/A
- **Specs:** [report-format.md](/docs/project/specs/report-format.md)

## Symptoms
On Windows, extracting failed CI step logs with `make logs 39429003074` printed a `UnicodeDecodeError` traceback from `subprocess._readerthread` on the cp1252 codec. The EXECUTE action still reported SUCCESS with return code 0, but its captured stdout was `None`. Expected behavior: the adapter decodes the GitHub log payload as UTF-8 and returns it in the report. Actual behavior: the reader thread dies, the traceback leaks to the console, and the action loses the output.

Minimal reproduction steps:
1. On Windows in a cp1252 locale, execute a command that writes the UTF-8 bytes `c4 90` to stdout through `ShellAdapter`.
2. Observe the reader-thread `UnicodeDecodeError` and the empty captured stdout.

## Context & Scope
### Regressing Delta
The `text=True` spawn without an explicit encoding is long-standing, so no single commit regressed it. The trigger is data-dependent: the first log payload containing a byte that is undefined in the active locale codec, such as UTF-8 byte `0x90` under cp1252.

### Environmental Triggers
Windows with the cp1252 locale. A child command whose stdout contains UTF-8 bytes undefined in cp1252, for example `0x90`. GitHub Actions failed-step logs contain such bytes.

### Ruled Out
- `truncate_lines` as the source of the `None` payload. It returns `""` for empty input, so the loss happened earlier in `communicate()`.
- A payload-type mismatch in the adapter test doubles. Every double returns a plain `str` tuple, which the decode helper passes through unchanged.
- A recent regressing commit. The `text=True` literal is long-standing, so the defect is latent and data-triggered.

## Diagnostic Analysis
### Causal Model
`ShellAdapter._prepare_subprocess_kwargs` sets `text=True` without `encoding`. `subprocess.Popen` therefore decodes both pipes with `locale.getpreferredencoding(False)`, which is cp1252 on Windows. `communicate()` drains the pipes in reader threads. A byte that cp1252 cannot decode raises `UnicodeDecodeError` inside the reader thread. Python's `threading.excepthook` writes the traceback directly to the harness process stderr, which sits outside the EXECUTE capture, so the traceback leaks to the console. The dead reader thread leaves the captured stdout unset, and the adapter builds a `ShellOutput` with `stdout=None` and return code 0.

### Discrepancies
- [x] A decode failure in the capture layer must not escape to the console. (Resolved: draining the pipes in bytes mode moves decoding off the reader thread, so no reader thread can die.)
- [x] An EXECUTE action must not report SUCCESS while it drops the captured output. (Resolved: `_decode_stream` always yields a string, so the payload is preserved or replaced rather than lost.)
- [x] The adapter must decode GitHub log output deterministically across platforms. (Resolved: strict UTF-8 first, locale fallback with replacement second, verified side-by-side against the replica.)
- [x] The Git status read must not hide pending changes on a non-UTF-8 path byte. (Resolved: the inspector requests explicit UTF-8 decoding with replacement.)
- [x] The hooks resolver must not force a reinstall on a non-UTF-8 path byte. (Resolved: the resolver requests explicit UTF-8 decoding with replacement and accepts an injected runner.)

### Investigation History
1. Read `src/teddy_executor/adapters/outbound/shell_adapter.py`. Observed `text=True` with no explicit encoding in `_prepare_subprocess_kwargs`. Read `shell_command_builder.py`. Observed only command wrapping and no stream encoding policy.
2. Built the MRE `spikes/debug/subprocess-output-decode-leak/01-subprocess-decode-leak-mre.py` with the child `emit_invalid_byte.py`, which writes byte `0x90`. Observed kwargs keys `['cwd', 'env', 'shell', 'stderr', 'stdin', 'stdout', 'text']` with no `encoding` and no `errors`. The adapter returned `stdout=None`, `stderr=''`, and `return_code=0`, and the process captured one `UnicodeDecodeError`. This proves the whole causal model in a single deterministic run on this host.
3. Read `.githooks/check_explicit_utf8.py`. Observed that it scans only `open()` and `read_text`/`write_text` calls, so subprocess text mode is unguarded and the defect class cannot be caught by that hook.
4. Built the side-by-side verification `spikes/debug/subprocess-output-decode-leak/02-verify-replica-fix.py` against the replica and the production adapter. Production returned cp1252 mojibake for the valid UTF-8 payload and `stdout=None` with a `UnicodeDecodeError` for the invalid byte. The replica returned `'\u2705 utf8 ok\n'` and `'\ufffd\n'` respectively, always a string, no reader-thread exception. This proves the bytes-capture decode policy fixes both payload shapes.
5. Applied the proven diff to `src/teddy_executor/adapters/outbound/shell_adapter.py` and added `tests/suites/unit/adapters/outbound/test_shell_adapter_output_decoding.py`. The regression module passed all seven tests, and `make test` reported 1846 passed and 36 skipped, so the bytes-mode switch disturbed no existing adapter double or acceptance flow.
6. Extended the defect-class sweep to the two remaining runtime `text=True` spawns. The inspector catches only `CalledProcessError` and `FileNotFoundError`, so a decode `ValueError` escapes; the hooks resolver catches `ValueError`, so a decode failure becomes `None` and forces a needless reinstall. Applied explicit `encoding="utf-8"` with `errors="replace"` to both, added an optional injected runner to the resolver, and added one regression test per adapter. `make test` reported 1848 passed and 36 skipped.

## Solution
### Root Cause
Verified. `text=True` without an explicit encoding makes `subprocess.Popen` decode the child pipes with the locale codec. A byte undefined in that codec kills the reader thread mid-`communicate()`, the traceback leaks via `threading.excepthook`, and the payload is lost as `stdout=None` at return code 0. The fix captures raw bytes and decodes each stream explicitly: strict UTF-8 first, then the locale codec with `errors="replace"`, then universal-newline normalisation. The same defect class lived in the two finite `subprocess.run` spawns, where text-mode decode raised on the same bytes; both now request `encoding="utf-8"` with `errors="replace"`. Proven side-by-side in the sandbox replica, then applied directly to `src/` with permanent regression modules. `make test` reports 1848 passed and 36 skipped.

### Affected Components
- `src/teddy_executor/adapters/outbound/shell_adapter.py`: carries the fix. The spawn requests bytes mode, and the new `_decode_stream` helper decodes every captured stream at all four capture sites.
- `tests/suites/unit/adapters/outbound/test_shell_adapter_output_decoding.py`: holds the new regression tests, including a real-child case for the undecodable byte.
- `docs/architecture/adapters/outbound/shell_adapter.md`: records the `stream_decoding` invariant and lists the decode helper.
- Adapter test doubles in `test_shell_adapter_interrupt.py`, `test_shell_adapter_timeout.py`, `test_shell_adapter_windows_interactive.py`, and `test_shell_adapter_background.py`: unchanged. They return `str` tuples, which pass through the helper untouched.
- `IShellExecutor` and `ShellOutput`: unchanged. Both streams remain `str`, so the port contract and every consumer stay valid.
- `src/teddy_executor/adapters/outbound/system_environment_inspector.py`: requests `encoding="utf-8"` with `errors="replace"` on the Git status spawn instead of bare text mode.
- `tests/suites/integration/adapters/outbound/test_system_environment_inspector.py`: adds a regression test that pins the explicit decoding kwargs.
- `docs/architecture/adapters/outbound/system_environment_inspector.md`: records the `explicit_stream_decoding` invariant.
- `src/teddy_executor/adapters/inbound/session_cli_handlers.py`: the hooks resolver requests explicit UTF-8 decoding and accepts an optional injected runner, so tests need no module patching.
- `tests/suites/unit/adapters/inbound/test_precommit_hook_skip_guard.py`: adds a resolver regression test that drives the injected runner.
- `resources/templates/pre-commit.md`: the bundled hook example keeps the bare `text=True` pattern and remains a documented follow-up, because it is documentation rather than runtime code.
