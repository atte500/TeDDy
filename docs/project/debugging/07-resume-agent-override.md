# Bug: Resume `-a/--agent` override is not reflected in the Agent identity banner
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
Running `teddy resume -a prototyper` against an existing session displays the
session's STORED agent (e.g. `Agent: Pathfinder`) in the startup identity banner
instead of the requested override (`Agent: Prototyper`).

Expected: the banner reflects the `-a/--agent` value passed to `resume`.
Actual: the banner reflects the session's persisted `meta.yaml` `agent_name`.

The analogous `--model` override DOES display correctly (user-reported and
confirmed by code inspection).

Minimal reproduction:

```shell
teddy resume -a prototyper   # banner shows: Agent: Pathfinder
```

## Context & Scope
### Regressing Delta
Introduced by `620e6f2a` ("Revert fix", 2026-10-13). That commit added the
identity-banner call inside `_sync_and_display_session_meta`:

    _echo_config_success(container, agent=meta.get("agent_name"), model=model)

It passes the session's STORED `agent_name` and never threads the `resume`
`-a/--agent` override, so the banner cannot reflect the override. The model
argument IS forwarded (`model=model`), which is exactly why `--model` displays
correctly while `--agent` does not. (`_sync_and_display_session_meta` itself was
first introduced by `17838fba`; `620e6f2a` is the change that wired in the
stored-agent display.)

Faulty seam:
- `src/teddy_executor/adapters/inbound/session_cli_handlers.py`
  - `handle_resume_session` — step 3 calls `_sync_and_display_session_meta`
    WITHOUT forwarding the `agent` override.
  - `_sync_and_display_session_meta` — renders `agent=meta.get("agent_name")`.
  - `_echo_config_success` — already prefers a truthy `agent` argument (innocent).

### Environmental Triggers
Any OS/runtime. Occurs on `teddy resume` whenever `-a/--agent` is passed for a
session whose stored `agent_name` differs from the override.

### Ruled Out
- **Model override path:** verified correct — `handle_resume_session` forwards
  `model=model` into `_sync_and_display_session_meta`, which forwards it to
  `_echo_config_success`; `meta.pop("actual_model")` clears the stale serving
  model so the override/config value wins.
- **`_echo_config_success` itself:** already correct — it canonicalises and
  renders whatever truthy `agent` argument it receives.
- **CLI arg parsing:** `__main__.py` defines `-a/--agent` on `resume` and passes
  `agent=agent` into `handle_resume_session`.

## Diagnostic Analysis
### Causal Model
1. `teddy resume -a prototyper` → `resume` command → `handle_resume_session(agent="prototyper")`.
2. Step 3 calls `_sync_and_display_session_meta(container, session_name, model=model, api_key=api_key)` — the `agent` argument is NOT forwarded.
3. `_sync_and_display_session_meta` loads the latest turn's `meta.yaml`, pops
   `actual_model`, then calls `_echo_config_success(container, agent=meta.get("agent_name"), model=model)`.
   Here `agent` is the STORED session agent ("pathfinder"), not the override.
4. `_echo_config_success` prints `Agent: Pathfinder` (canonicalised stored value).
5. Only at step 5 — AFTER the banner — does `set_session_agent(session_name, agent)`
   persist the override, so the prompt actually used for the turn is correct;
   only the banner is stale.

### Discrepancies
- [x] Banner shows the stored agent instead of the `-a` override on resume (Resolved: `_sync_and_display_session_meta` never received the `agent` override; threading it and preferring it over `meta["agent_name"]` makes the banner show `Agent: Prototyper` — proven by the sandbox replica).
- [x] Model override displays correctly (Resolved: verified by code inspection — `model` is forwarded to the display path, `agent` is not).

### Investigation History
1. Investigated whether the CLI dropped `-a` on resume by grepping `__main__.py`
   and `session_cli_handlers.py`; observed `agent=agent` IS forwarded to
   `handle_resume_session`, ruling out CLI arg parsing.
2. Investigated where the `Agent:` line is produced by reading
   `_echo_config_success` / `_sync_and_display_session_meta`; observed the display
   path never receives the override and uses `meta.get("agent_name")`, isolating
   the seam to step 3 of `handle_resume_session`.
3. Reproduced the symptom live: the MRE drove the real `handle_resume_session`
   with `agent="prototyper"` against a session whose stored `agent_name` was
   `pathfinder`; the emitted banner read `Agent: Pathfinder`, exiting 1 (bug
   reproduced), confirming the display path ignores the override.
4. Isolated the regressing delta via `git log -S`: `620e6f2a` ("Revert fix")
   introduced the `agent=meta.get("agent_name")` banner call, which never
   receives the `-a` override.
5. Verified the fix in an isolated sandbox replica
   (`spikes/debug/resume-agent-override/replica_session_cli_handlers.py`): the
   replica threads the `agent` override into `_sync_and_display_session_meta`
   and prefers it over `meta["agent_name"]`. The replica-backed runner printed
   `Agent: Prototyper` (exit 0) while the untouched production MRE still printed
   `Agent: Pathfinder` (exit 1), proving the fix without modifying `src/`.
6. Systemic audit (`git grep`): `_echo_config_success` has exactly two callers —
   `handle_new_session` (line 597) passes the CLI `agent` directly (correct) and
   `_sync_and_display_session_meta` (line 1049) passed the persisted
   `meta["agent_name"]` (faulty). No other display site reads persisted
   `agent_name`, and `set_session_agent` is invoked only from the resume path.
   The defect is isolated to the single resume display call.
7. Applied the verified fix directly to
   `src/teddy_executor/adapters/inbound/session_cli_handlers.py` (per the user's
   request to change it directly). Updated the two monkeypatch lambdas in
   `test_session_cli_handlers.py` to mirror the new signature and added the
   regression test `test_resume_agent_override_display.py`. The affected inbound
   tests pass (`23 passed`) and the production MRE now prints
   `Agent: Prototyper` (exit 0).

### Systemic Audit
**Abstract category:** a display path reads persisted state instead of the
effective override. The mutation path (`set_session_agent`) already receives the
override; only the read-only display path drifted.

Audit of all callers of the affected helpers:

| Helper | Caller | Argument source | Verdict |
| --- | --- | --- | --- |
| `_echo_config_success` | `handle_new_session` (597) | CLI `agent` | correct |
| `_echo_config_success` | `_sync_and_display_session_meta` (1049) | persisted `meta["agent_name"]` | faulty |
| `set_session_agent` | `handle_resume_session` (1122) | CLI `agent` | correct |
| `canonical_agent_name` | banner (670), `PromptManager`, `SessionService` | effective/derived | correct |

No sibling instance exists. The fix is a bounded, non-breaking threading change
to `_sync_and_display_session_meta`; no port, signature, or data contract with
more than one consumer is modified.

## Solution
### Root Cause
`handle_resume_session` displays the identity banner at step 3 by calling
`_sync_and_display_session_meta(container, session_name, model=model,
api_key=api_key)` — the `-a/--agent` override is NOT forwarded. That helper
renders the session's persisted `meta["agent_name"]` via `_echo_config_success`,
so the banner shows the stored agent (e.g. `Pathfinder`) while the override is
only applied later at step 5 (`set_session_agent`). The model path is unaffected
because `model=model` IS forwarded and `meta.pop("actual_model")` clears the
stale serving model.

### Verified Fix (applied to `src/` and proven)
Thread the `agent` override into the display path and prefer it over the stored
value. Applied to `src/teddy_executor/adapters/inbound/session_cli_handlers.py`:

1. Added `agent: Optional[str] = None` to `_sync_and_display_session_meta`.
2. Render the override when present:
   `_echo_config_success(container, agent=agent or meta.get("agent_name"), model=model)`
3. Forwarded the override from the resume handler:
   `_sync_and_display_session_meta(container, session_name, model=model, api_key=api_key, agent=agent)`

The fix was first proven in an isolated sandbox replica and then applied to
production. Two monkeypatch lambdas in
`tests/suites/unit/adapters/inbound/test_session_cli_handlers.py` were updated
to mirror the new signature (additive `agent=None`).

Evidence:
- `spikes/debug/resume-agent-override/01-agent-override-display-mre.py` — production MRE; reproduced the bug before the fix (`Agent: Pathfinder`, exit 1) and now passes (`Agent: Prototyper`, exit 0).
- `spikes/debug/resume-agent-override/02-agent-override-display-mre.py` — replica-backed runner used to prove the fix before application (`Agent: Prototyper`, exit 0).
- `spikes/debug/resume-agent-override/replica_session_cli_handlers.py` — the sandbox replica carrying the three-line fix.
- `tests/suites/unit/adapters/inbound/test_resume_agent_override_display.py` — regression test pinning the override-vs-persisted contract.

### Preventative Measures
- **Contract:** the startup banner MUST reflect the effective agent (override if
  provided, else the stored value) — never a stale persisted value when an
  override is in effect.
- **Regression test:** added
  `tests/suites/unit/adapters/inbound/test_resume_agent_override_display.py`,
  which asserts `handle_resume_session(agent=X)` against a session whose stored
  `agent_name` is `Y` renders `Agent: <X>` in the banner (and falls back to the
  stored value when no override is given). This pins the override-vs-persisted
  contract so a future refactor cannot silently revert it.
- **Scope:** the systemic audit confirmed no sibling instances; no broader
  consolidation or port change is required.
