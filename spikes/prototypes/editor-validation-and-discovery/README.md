# Spike: Editor Validation & Discovery (Slice 03-01 Technical Key Unknowns)

Standalone probe for the three unresolved `[Technical]` Key Unknowns of
Slice 03-01. It imports production code read-only (never modifies `src/`).

## Run

```
uv run python spikes/prototypes/editor-validation-and-discovery/spike.py
```

Exit code 0 == all assertions pass; raw evidence is printed to stdout.

## What each probe verifies

- **KU1** (`set_setting` path handling): proves that (a) the spec's proposed
  implementation raises `FileNotFoundError` when the `root_dir`-based parent
  directory is missing, (b) the in-memory cache is stale after a disk-only
  write, and (c) a corrected shadow implementation (with `os.makedirs` +
  cache update) persists and reloads for both `root_dir` and plain paths.
- **KU2** (JetBrains bare `diff` flag): drives the real
  `get_diff_viewer_command()` against a fake launcher and confirms the bare
  `"diff"` token is transmitted as a discrete `argv` element through
  `subprocess.run`; then simulates the spec's added JetBrains entries.
- **KU3** (TUI unknown-editor routing): drives the real
  `preview_edit_diff_viewer()` with a stub app and observes which branch is
  taken (annotated diff vs GUI before/after) for a CLI editor, a known GUI
  editor, and an unknown editor; validates the proposed routing predicate.

## Knobs

- Edit the `added` dict in `probe_ku2` to try different JetBrains flag values.
- Edit `original` / `proposed` in `probe_ku3` to vary the diff content.
- Add names to `_make_fake_launcher` calls to probe additional editors.

## Files

- `spike.py` — the probe + assertions (self-verifying).
- `set_setting_shadow.py` — shadow `set_setting` implementation (spec-proposed
  and corrected variants).