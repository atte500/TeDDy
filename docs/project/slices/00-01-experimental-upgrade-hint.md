# Slice: Follow the Experimental Channel via `uv tool upgrade`
- **Status:** Completed
- **Milestone:** None (ad-hoc slice)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `experimental-hint`

## Goal
Point the experimental upgrade hint at `uv tool upgrade teddy-cli --prerelease allow` instead of a forced reinstall, so users following the pre-release channel keep the install source recorded in their tool receipt. Use the documented `--prerelease` spelling wherever the experimental channel is described, replacing the help-hidden `--pre`, and split the README's experimental section into distinct install and upgrade commands.

## Context
- `teddy update` (`src/teddy_executor/__main__.py`): resolves `latest = fetch_latest_version(index_url, stable_only=not experimental)`. The `elif experimental:` branch now emits `uv tool upgrade teddy-cli --prerelease allow`; it was the only hint in the command that could safely change.
- Stable hint as it stood for this slice: the `else` branch emitted `uv tool upgrade teddy-cli`, and the two other branches kept `--force`. The `is_prerelease(current)` half of that reading was wrong and slice `00-02-stable-channel-upgrade-hint.md` superseded it; only `is_channel_switch` still keeps `--force`.
- Update checker (`src/teddy_executor/adapters/inbound/session_cli_handlers.py`): reads a stable-only cache, because `background_check` calls `fetch_latest_version(index_url)` with the default `stable_only=True`. This slice treated its `is_prerelease(current)` branch as out of scope on the mistaken reading that it was a downgrade; `compare_versions` requires `latest > current`, so it is a forward move, and slice `00-02-stable-channel-upgrade-hint.md` retargets it.
- `uv tool` receipts: `uv-receipt.toml` records `requirements` (name plus optional specifier), `entrypoints`, and `[tool.options]`. Verified on uv 0.11.28: `uv tool install teddy-cli --prerelease allow` writes `prerelease = "allow"`, `uv tool install teddy-cli --default-index ...` writes `index = [{ url = ..., default = true }]`, and a bare `uv tool upgrade` leaves both intact. A forced reinstall from the default index discards a git or private-index source that `README.md` documents as supported.
- `uv tool upgrade`: accepts `<NAME>...`, `--prerelease <allow|disallow|...>`, `--reinstall`, and `--all`, and re-resolves the recorded requirement rather than a caller-supplied one. `uv tool upgrade teddy-cli --prerelease allow` parses and runs; on an already-current tool it reports `Nothing to upgrade`.
- Exact pins block upgrades: a receipt recording `specifier = "==0.2.2"` yields `Nothing to upgrade` with a `uv tool install teddy-cli@latest` hint even when a looser specifier is passed on the upgrade command. Neither the hint nor the README records an exact pin, so this constrains the design rather than blocking it.
- `--pre` on `uv tool install`: still accepted in uv 0.11.28 as a help-hidden alias (`--help` short-circuits argument validation, but an offline install reached the resolver rather than failing argument parsing). The previous hint was therefore runnable, not broken; its defect was that `--force` rewrote the recorded source and that `--pre` is undocumented while `--prerelease allow` is the documented spelling on both verbs. The upgrade form addresses both.
- Upgrade-time prerelease is honoured and persisted: on uv 0.11.28, a specifier-free `litellm` tool receipt at stable `1.110.3` upgraded to `1.112.0.dev2` under `uv tool upgrade litellm --prerelease allow`, and the receipt gained `[tool.options] prerelease = "allow"`. The identical install upgraded without the flag reported `Nothing to upgrade` and stayed on `1.110.3`. The flag therefore reaches resolution and self-sustains later bare upgrades.
- PEP 440 boundary semantics explain the one negative probe: a receipt recording `specifier = "<0.2.3"` excludes every `0.2.3.devNNNN` release, because an exclusive ordered comparison does not admit pre-releases of its own boundary version unless the specifier itself carries a pre-release. There the specifier blocked resolution, not the flag. Neither the recommended install shapes nor the hints record a specifier.

## Scenarios
> As a developer tracking the experimental channel, I want to upgrade to the newest pre-release with a single command so that a fork or private-index install keeps the source it was installed from.

```gherkin
Given a teddy-cli install following the experimental channel
When teddy update --experimental reports a newer pre-release
Then it prints "To upgrade, run: uv tool upgrade teddy-cli --prerelease allow"
And the printed command upgrades from the recorded requirement instead of reinstalling from the default index
```

> As a user on the stable channel, I want the plain update hint to keep telling me to upgrade in place so that I never have to reinstall to move forward.

```gherkin
Given a teddy-cli install on the stable channel
When teddy update reports a newer stable version
Then it prints "To upgrade, run: uv tool upgrade teddy-cli"
And it does not print a forced reinstall command
```

## Edge Cases
- **Receipt already records the policy**: If the install was made with `--prerelease allow`, then the receipt carries `prerelease = "allow"` and a bare `uv tool upgrade teddy-cli` would already follow pre-releases; the explicit flag stays in the hint because the same string must also serve a stable install that ran `teddy update --experimental`.
- **Git or private-index install**: If the tool was installed from a git URL or a private index, then the hint must preserve that source, because `--force` re-resolves from the default index and the README documents both shapes as supported.
- **Exact-pin receipt**: If a receipt carried an exact specifier, then the upgrade would refuse to move and print a reinstall hint, because the recorded specifier governs resolution. Neither the hint nor the README creates that shape, so it must not be produced by this change.
- **Specifier-aware receipt**: If a receipt carried a range specifier excluding pre-releases of its boundary version (for example `<0.2.3` against `0.2.3.devNNNN`), then the upgrade reports `Nothing to upgrade` regardless of `--prerelease allow`, because PEP 440 exclusive ordering does not admit those pre-releases. The hint cannot help that shape, so neither it nor the README may encourage installs with a bounded or pinned specifier.
- **Pre-release install with a newer stable**: If the current version is a pre-release and a newer stable exists, then the receipt's `prerelease = "allow"` makes a bare upgrade overshoot to a newer dev release, so the hint needs an explicit channel rather than a bare upgrade. Superseded by slice `00-02-stable-channel-upgrade-hint.md`, which uses `uv tool upgrade teddy-cli --prerelease disallow`; `--force` remains only for the case where no newer stable exists at all.
- **Flagged experimental from a stable install**: If a stable install runs `teddy update --experimental`, then the hint must still carry `--prerelease allow`, because that receipt records no prerelease policy and a bare upgrade would never select a pre-release.

## Key Unknowns
None. The upgrade-time prerelease question resolved in favour of persistence (see Context), which is the branch that lets the README state that later bare upgrades keep following pre-releases. Confirming it on `teddy-cli`'s own receipt is a manual verification step, not an open unknown.

## Impact
1. `[EXTEND]` `src/teddy_executor/__main__.py` — replace the experimental branch's hint string; no branch condition changes.
2. `[MIGRATE]` `tests/suites/acceptance/test_experimental_wiring.py` and `tests/suites/acceptance/test_update_command_actually_upgrades.py` — retarget the two assertions that pin the old experimental string.
3. `[MIGRATE]` `README.md` — split the experimental section into separate install and upgrade commands, use the documented `--prerelease allow` spelling in both, and state that upgrades re-resolve the recorded install source and that the recorded policy keeps later bare upgrades on the pre-release channel.

## Deliverables
- [x] **Wiring** - Replace the experimental hint in `__main__.py` with `uv tool upgrade teddy-cli --prerelease allow` and retarget the two pinned assertions so the suite stays green.
- [x] **Migration** - Rewrite the README's "Installing Experimental Versions" section as distinct install (`uv tool install teddy-cli --prerelease allow`) and upgrade (`uv tool upgrade teddy-cli --prerelease allow`) commands, documenting that upgrades re-resolve the recorded source.

## Implementation Notes
The upgrade-time persistence probe ran twice. On `litellm`, a specifier-free receipt at stable `1.110.3` moved to `1.112.0.dev2` and gained `prerelease = "allow"`. Repeated on `teddy-cli` itself, which needed a `UV_EXCLUDE_NEWER` cap so an unversioned requirement could install an older release: `0.2.2` moved to `0.2.3.dev1527` under the same flag, and the receipt gained `prerelease = "allow"` beside the recorded `exclude-newer`. The README claim therefore rests on the artifact this project ships, not only on a third-party proxy.

When retargeting `test_update_command_actually_upgrades.py`, note that Milestone 5 consolidates the redundant `teddy update` notification tests and currently names three tests in that file, none of which is the experimental hint test; the consolidation should inherit the retargeted assertion rather than re-deriving the string.

Superseded branch: this slice also kept `uv tool install teddy-cli --force` on the two forward-move hints, on the reading that a pre-release receipt cannot reliably reach stable. That reading conflated a channel switch with a forward move. `compare_versions` requires `latest > current`, so both hints announce an upgrade, and `uv tool upgrade teddy-cli --prerelease disallow` performs it while preserving the recorded install source. Slice `00-02-stable-channel-upgrade-hint.md` delivered that correction; `--force` survives only on the `is_channel_switch` branch, where no newer stable exists.

## Verification
1. **Experimental hint text:**
   Run `uv run teddy update --experimental` against a version where a newer pre-release exists.
   Verify the output contains `uv tool upgrade teddy-cli --prerelease allow`.
2. **Stable hint unchanged:**
   Run `uv run teddy update`.
   Verify the output contains `uv tool upgrade teddy-cli` and does not contain `uv tool install teddy-cli --force`.
3. **Printed command validity and policy persistence:**
   Run `uv tool upgrade teddy-cli --prerelease allow`.
   Verify it reports an upgrade or `Nothing to upgrade` without an argument error.
   Locate the tool environment with `uv tool dir`, then read `teddy-cli/uv-receipt.toml` inside it.
   Verify `[tool.options]` contains `prerelease = "allow"`.
4. **README section:**
   Read the "Installing Experimental Versions" section.
   Confirm install and upgrade appear as separate commands and that the recorded-source behaviour is stated.
