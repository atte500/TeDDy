# Prototype: Editor Validation & Discovery (Slice 03-01)

Standalone prototype for Slice 03-01. `spike.py` resolves the three
`[Technical]` Key Unknowns; `editors_demo.py` resolves the `[Functional]`
console editor-selection UI Key Unknown. Both import production code
read-only and never modify `src/` or `tests/`.

## Run

### Technical-key-unknown probe (`spike.py`)

```
uv run python spikes/prototypes/editor-validation-and-discovery/spike.py
```

Exit code 0 == all assertions pass; raw evidence is printed to stdout.

### Console editor-selection UI demo (`editors_demo.py`)

Interactive — tune the rendered preflight UI exactly as a user would see it:

```
uv run python spikes/prototypes/editor-validation-and-discovery/editors_demo.py
```

Self-verifying battery (18 assertions):

```
uv run python spikes/prototypes/editor-validation-and-discovery/editors_demo.py --selftest
```

Scripted / non-TTY (feed canned inputs, comma-separated; an empty segment == Enter):

```
uv run python spikes/prototypes/editor-validation-and-discovery/editors_demo.py --inputs "99,2"
```

Knobs: `--list-format {bare,bracket}`, `--show-paths`, `--no-color`, `--prompt`,
`--invalid-mode {silent,message}`, `--header`, `--discovery-mode
{missing,unconfigured}`, `--no-editors-found`, `--which-map`, `--editors`.

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

- `spike.py` — the Technical probe + assertions (self-verifying).
- `set_setting_shadow.py` — shadow `set_setting` implementation (spec-proposed
  and corrected variants).
- `editors_demo.py` — interactive console editor-selection UI demo + `--selftest`.