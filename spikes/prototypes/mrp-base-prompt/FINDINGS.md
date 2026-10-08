# Spike Findings: `importlib.resources` Loading of the Bundled `MRP.xml`

- **Slice:** [03-02-mrp-base-prompt](/docs/project/slices/03-02-mrp-base-prompt.md)
- **Key Unknown resolved:** `[Technical]` — the `importlib.resources` API for loading MRP.xml
- **Spike run date:** 2026-10-08
- **Result:** ✅ VERIFIED — all three assertions PASS

## Mission

Empirically prove the `importlib.resources` API for loading
`src/teddy_executor/resources/MRP.xml` from the `teddy_executor.resources`
package, so `PromptManager.fetch_system_prompt()` can append the shared MRP
protocol block without ever touching `.teddy/prompts/`.

## Environment

| Item | Value |
| --- | --- |
| Python | 3.13.14 (`uv run python`) |
| Install mode | Source checkout via `uv` (editable), so `files()` yields a real `pathlib.PosixPath` |
| Resource under test | `src/teddy_executor/resources/MRP.xml` (16,662 chars) |
| Package | `teddy_executor.resources` (a plain package with `__init__.py`) |

## Reproduction

```shell
uv run python spikes/prototypes/mrp-base-prompt/probe_importlib_resources.py
```

Exits `0` when all assertions pass, `1` otherwise.

## Assertions & Evidence

### 1. `files(...) / "MRP.xml"` resolves to a readable Traversable

```text
package root  : PosixPath('.../src/teddy_executor/resources')
type(root)    : PosixPath
resource      : PosixPath('.../src/teddy_executor/resources/MRP.xml')
type(resource): PosixPath
[PASS] resource exposes Traversable API (is_file + read_text)
[PASS] resource.is_file() is True
```

**Finding:** The `files() / "name"` operator returns a path object whose
`is_file()` is `True` and which exposes the full `Traversable` API
(`read_text`, `read_bytes`, `joinpath`, …). In a source/editable install this
concrete type is `pathlib.PosixPath`; under a zip/wheel install it would be a
`zipfile.Path`. Both satisfy the `Traversable` contract, so production code
MUST rely only on the documented `Traversable` methods (`is_file`,
`read_text`) and never on `Path`-specific attributes.

### 2. `.read_text(encoding="utf-8")` returns the file contents

```text
length        : 16662
head          : '<mrp>\n  <general_rules>\n    <description>All rules in this s'
[PASS] content is non-empty
[PASS] content starts with '<mrp>'
[PASS] content contains '<response_format>'
[PASS] content contains 'State Transition Protocol'
```

**Finding:** `read_text(encoding="utf-8")` returns the full MRP document. The
content is non-empty and contains the expected markers. Always pass
`encoding="utf-8"` explicitly (project invariant).

### 3. A missing `MRP.xml` raises `FileNotFoundError`

```text
natural read_text raised FileNotFoundError: [Errno 2] No such file or directory: '.../MRP.absent.xml'
[PASS] natural read_text on missing file raises FileNotFoundError
guarded loader raised FileNotFoundError: Bundled MRP.xml not found at .../does-not-exist.../sub/MRP.xml
[PASS] explicit is_file() guard raises FileNotFoundError
```

**Finding:** Both paths raise `FileNotFoundError`:

- The **natural** path — `(files(pkg) / name).read_text(...)` on a
  non-existent name — raises `FileNotFoundError` directly.
- The **guarded** path — an explicit `if not resource.is_file(): raise
  FileNotFoundError(...)` — raises the same exception type with a clear,
  domain-specific message.

## Recommended Production Pattern

`PromptManager.fetch_system_prompt()` should adopt the explicit, fail-fast
guard so protocol degradation is never silent:

```python
import importlib.resources as resources

_MRP_PACKAGE = "teddy_executor.resources"
_MRP_FILENAME = "MRP.xml"


def _load_mrp_base_prompt() -> str:
    resource = resources.files(_MRP_PACKAGE) / _MRP_FILENAME
    if not resource.is_file():
        raise FileNotFoundError(
            f"Bundled MRP base prompt not found at {resource}. "
            "The package resource 'teddy_executor.resources/MRP.xml' is missing."
        )
    return resource.read_text(encoding="utf-8")
```

Notes:

- This bypasses `.teddy/prompts/` entirely — MRP.xml is never user-editable and
  MUST never be copied into `.teddy/`.
- The `is_file()` guard converts an obscure downstream parse failure into an
  explicit, actionable `FileNotFoundError` at the point of load.
- The "empty MRP.xml" edge case is intentionally NOT guarded here: an existing
  but zero-length file returns `""` (`read_text` succeeds), matching the slice's
  edge case which requires append-empty rather than error.

## Conclusion

All three required behaviors are **VERIFIED** against the real environment. The
`[Technical]` Key Unknown about the `importlib.resources` API is resolved: use
`importlib.resources.files("teddy_executor.resources") / "MRP.xml"` with an
explicit `is_file()` guard and `read_text(encoding="utf-8")`.