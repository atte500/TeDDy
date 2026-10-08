"""De-risking spike: importlib.resources loading of the bundled MRP.xml.

Proves the three assumptions the "MRP Base Prompt" slice (03-02) depends on:

  1. resources.files("teddy_executor.resources") / "MRP.xml" resolves to a
     readable Traversable (is_file() True).
  2. .read_text(encoding="utf-8") returns the file's contents.
  3. Loading a missing MRP.xml raises FileNotFoundError -- both via the
     natural read_text() error and via the explicit is_file()-guarded
     fail-fast pattern the production code will adopt.

Run with:
    uv run python spikes/prototypes/mrp-base-prompt/probe_importlib_resources.py

Exits 0 when all assertions pass, 1 otherwise.
"""

from __future__ import annotations

import importlib.resources as resources
import sys
from typing import Any

PKG = "teddy_executor.resources"
RESOURCE_NAME = "MRP.xml"

_failures = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _failures
    if not condition:
        _failures += 1
    status = "PASS" if condition else "FAIL"
    line = f"[{status}] {label}"
    if detail:
        line += f" -- {detail}"
    print(line)


def load_mrp(root: Any) -> str:
    """The recommended fail-fast production pattern (explicit guard)."""
    resource = root / RESOURCE_NAME
    if not resource.is_file():
        raise FileNotFoundError(f"Bundled {RESOURCE_NAME} not found at {resource}")
    return resource.read_text(encoding="utf-8")


def main() -> int:
    # -- Assertion 1: resolution to a readable Traversable -----------------
    print("== Assertion 1: files() / name resolves to a readable Traversable ==")
    pkg_root = resources.files(PKG)
    print(f"  package root  : {pkg_root!r}")
    print(f"  type(root)    : {type(pkg_root).__name__}")
    traversable = pkg_root / RESOURCE_NAME
    print(f"  resource      : {traversable!r}")
    print(f"  type(resource): {type(traversable).__name__}")
    check(
        "resource exposes Traversable API (is_file + read_text)",
        hasattr(traversable, "is_file") and hasattr(traversable, "read_text"),
    )
    check("resource.is_file() is True", bool(traversable.is_file()))

    # -- Assertion 2: read_text returns the contents ----------------------
    print("\n== Assertion 2: read_text(encoding='utf-8') returns contents ==")
    text = traversable.read_text(encoding="utf-8")
    print(f"  length        : {len(text)}")
    print(f"  head          : {text[:60]!r}")
    check("content is non-empty", len(text) > 0)
    check("content starts with '<mrp>'", text.lstrip().startswith("<mrp>"))
    check("content contains '<response_format>'", "<response_format>" in text)
    check(
        "content contains 'State Transition Protocol'",
        "State Transition Protocol" in text,
    )

    # -- Assertion 3: missing resource raises FileNotFoundError -----------
    print("\n== Assertion 3: missing MRP.xml raises FileNotFoundError ==")
    missing = pkg_root / "MRP.absent.xml"
    natural_error = None
    try:
        missing.read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # noqa: BLE001 - spike diagnostic
        natural_error = exc
        print(f"  natural read_text raised FileNotFoundError: {exc}")
    except Exception as exc:  # noqa: BLE001 - spike diagnostic
        print(f"  natural read_text raised unexpected {type(exc).__name__}: {exc}")
    check("natural read_text on missing file raises FileNotFoundError", natural_error is not None)

    guarded_error = None
    try:
        load_mrp(pkg_root / "does-not-exist-because-we-point-elsewhere" / "sub")
    except FileNotFoundError as exc:  # noqa: BLE001 - spike diagnostic
        guarded_error = exc
        print(f"  guarded loader raised FileNotFoundError: {exc}")
    except Exception as exc:  # noqa: BLE001 - spike diagnostic
        print(f"  guarded loader raised unexpected {type(exc).__name__}: {exc}")
    check("explicit is_file() guard raises FileNotFoundError", guarded_error is not None)

    print("\nRESULT:", "ALL PASS" if _failures == 0 else f"{_failures} FAILURE(S)")
    return 0 if _failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())