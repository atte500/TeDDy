# Slice: Deliver the Stable Upgrade Hint Without a Forced Reinstall
- **Status:** Completed
- **Milestone:** None (ad-hoc slice)
- **Depends On:** [00-01-experimental-upgrade-hint.md](/docs/project/slices/00-01-experimental-upgrade-hint.md)
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `stable-channel-hint`

## Goal
Point both forward-move update hints at `uv tool upgrade teddy-cli --prerelease disallow`, so a pre-release install told that a newer stable exists can reach it without discarding the install source that a forced reinstall resets.

## Context
- `compare_versions(current, latest)` returns `Version(latest) > Version(current)`, so every branch printing a "new version" hint announces a strictly forward move. A stable `latest` against a pre-release `current` is an upgrade, not a downgrade.
- Two producers printed `uv tool install teddy-cli --force` on that forward move: `teddy update`'s non-experimental `else` branch (`src/teddy_executor/__main__.py`) and the startup notice `_display_update_notification` (`src/teddy_executor/adapters/inbound/session_cli_handlers.py`). A forced reinstall re-resolves from the default index, so a git or private-index install loses its source, and it writes `prerelease = "disallow"` into the receipt without saying so.
- The update cache is stable-only: `background_check` calls `fetch_latest_version(index_url)` with the default `stable_only=True`, so the announced `latest` is always a stable release.
- A receipt following the experimental channel records `[tool.options] prerelease = "allow"`, so a bare `uv tool upgrade teddy-cli` resolves the newest version including pre-releases and can overshoot the announced stable. That overshoot is the bug #20 shape the forced reinstall was originally introduced to prevent.
- `uv tool upgrade teddy-cli --prerelease disallow` lands on the announced stable and leaves the recorded `index` untouched. It rewrites the receipt's `prerelease` policy to `disallow`, which is the honest consequence of accepting a stable release rather than a hidden side effect of a reinstall.
- `--force` remains correct only at `is_channel_switch` in `teddy update`: the installed pre-release is newer than the newest stable, so the announced move is to an older version, and `uv tool upgrade` has no downgrade form.
- `pyproject.toml` records `version = "0.2.3"`, so unit tests see a stable installed version unless one is injected explicitly.

## Scenarios
> As a developer following the experimental channel, I want the startup notice to name a command that reaches the announced stable so that I do not lose the source my tool was installed from.

```gherkin
Given a teddy-cli install on a pre-release version
And the cached latest stable version is newer than the installed version
When the session starts and the update notice fires
Then it prints "To upgrade, run: uv tool upgrade teddy-cli --prerelease disallow"
And it does not print a forced reinstall command
```

> As a developer running `teddy update` without `--experimental`, I want both producers to agree on that command.

```gherkin
Given a teddy-cli install on a pre-release version
When teddy update finds a newer stable version
Then it prints "To upgrade, run: uv tool upgrade teddy-cli --prerelease disallow"
And it does not print a forced reinstall command
```

## Edge Cases
- **Stable install**: If the installed version is stable, then both hints keep printing `uv tool upgrade teddy-cli`, because the receipt records no pre-release policy to suppress.
- **Overshoot prevention**: If the receipt records `prerelease = "allow"`, then `--prerelease disallow` is required, because a bare upgrade would resolve a newer dev release instead of the announced stable.
- **Channel switch**: If the installed version is a pre-release and no newer stable exists, then `teddy update` keeps the `uv tool install teddy-cli --force` hint, because the announced move is to an older version and `uv tool` has no downgrade verb.
- **Policy rewrite**: If the user runs the suggested command, then the receipt's `[tool.options] prerelease` becomes `disallow`, so later bare upgrades follow the stable channel. That is the intended meaning of accepting a stable release.
- **Injected version**: If a caller supplies `current_version`, then the notice uses it instead of the installed distribution metadata, so the channel branch is pinnable without patching module state. The parameter is keyword-only and defaults to `None`, leaving production behaviour unchanged.

## Key Unknowns
None. The forward-move reading follows directly from `compare_versions`, and the command's behaviour on an experimental receipt was verified on uv 0.11.28 before the change was made.

## Impact
1. `[EXTEND]` `src/teddy_executor/adapters/inbound/session_cli_handlers.py` — retarget the `is_prerelease(current)` hint, refresh its comment, and add the keyword-only `current_version` seam.
2. `[MIGRATE]` `src/teddy_executor/__main__.py` — retarget `teddy update`'s non-experimental pre-release hint to the same command and refresh its comment.
3. `[MIGRATE]` `tests/suites/acceptance/test_update_command_experimental_channel_fix.py` — rename the module, the test, and its assertions around the new command.
4. `[EXTEND]` `tests/suites/unit/adapters/inbound/test_session_notification_toggles.py` — add a startup-notice pin for the pre-release branch.

## Deliverables
- [x] **Wiring** - Retarget both forward-move hints to `uv tool upgrade teddy-cli --prerelease disallow` with comments that state the overshoot and recorded-source reasons, and add the keyword-only `current_version` seam the notice uses.
- [x] **Migration** - Rename and retarget the bug #20 acceptance test, and add a startup-notice unit case proving the pre-release branch emits the new command and no forced reinstall.

## Implementation Notes
The `current_version` seam exists because the project forbids global module patching in unit tests. The notice reads `get_current_version()` at call time; the keyword-only override lets a test drive the channel branch with an explicit pre-release string while every production caller continues to pass two positional arguments, so runtime behaviour is byte-identical.

`--prerelease allow` was considered and rejected for this branch: it would let an experimental receipt resolve a newer dev release than the one the notice names, restoring the bug #20 confusion. `--force` was rejected because it discards a git or private-index install source and rewrites the receipt policy silently. `--prerelease disallow` delivers exactly the announced version and is the narrowest honest choice.

Deliberately left alone: `teddy update`'s `is_channel_switch` branch still prints `uv tool install teddy-cli --force`. There the installed pre-release is newer than the newest stable, so the move is backwards, and `uv tool` offers no downgrade verb. Whether `uv tool upgrade teddy-cli --prerelease disallow` performs that downgrade is unproven, because the only probe available moved between versions of the same release (`0.2.3.dev1527` to `0.2.3`), which PEP 440 orders as an upgrade. Settling that question would retire the last `--force` on the update surface.

## Verification
1. **Startup notice on a pre-release install:**
   Install a pre-release, start a session, and wait for a newer stable to be announced.
   Verify the notice reads `To upgrade, run: uv tool upgrade teddy-cli --prerelease disallow`.
2. **`teddy update` agreement:**
   Run `uv run teddy update`.
   Verify the same command appears and that `uv tool install teddy-cli --force` does not.
3. **Stable installs unchanged:**
   Run `uv run teddy update` from a stable install with a newer stable available.
   Verify the hint is still `uv tool upgrade teddy-cli`.
4. **Command validity:**
   Run `uv tool upgrade teddy-cli --prerelease disallow` from a pre-release install.
   Verify it lands on the announced stable without an argument error, and that `uv tool dir`'s `teddy-cli/uv-receipt.toml` keeps its recorded `index` while showing `prerelease = "disallow"`.
