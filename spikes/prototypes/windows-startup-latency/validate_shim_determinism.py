#!/usr/bin/env python3
"""Spike 00-20 / Unknown 1: pre-commit shim determinism.

Empirically answers: is property-checking (shim existence + declared
--hook-type= values + --config= + INSTALL_PYTHON path exists) sufficient
to safely skip `pre-commit install`, versus brittle byte-comparison?

Evidence produced:
  A. Real shims from THIS repo parsed -> properties extracted.
  B. pre-commit's shim template located + extracted from the installed
     package (self-locating: grep for the "start templated" marker,
     NOT a hardcoded module name — the module name drifted in 4.6.0).
  C. Shim bytes reconstructed from template + parsed properties ->
     byte-identical to the real shims (determinism proof).
  D. Install-method simulation (pipx / uv / pip): regenerated shims
     differ byte-wise (different INSTALL_PYTHON) but ALL pass the
     property check -> property-check robust, byte-compare brittle.
  E. Fallback triggers verified: missing shim, dead interpreter,
     foreign content -> property check fails (real install must run).
"""

import hashlib
import importlib.util
import re
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / ".git" / "hooks"
REQUESTED_HOOK_TYPES = ("pre-commit", "post-commit")
CONFIG_FLAG = "--config=.pre-commit-config.yaml"

failures = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" -- {detail}" if detail else ""))
    if not condition:
        failures.append(label)


def parse_shim(text):
    props = {}
    m = re.search(r"^INSTALL_PYTHON=(.+)$", text, re.MULTILINE)
    props["install_python"] = m.group(1).strip() if m else None
    m = re.search(r"^ARGS=\((.*)\)$", text, re.MULTILINE)
    props["args"] = m.group(1).strip() if m else None
    m = re.search(r"^# ID: ([0-9a-f]{32})$", text, re.MULTILINE)
    props["template_id"] = m.group(1) if m else None
    props["is_bash"] = text.startswith("#!/usr/bin/env bash")
    props["has_fallback"] = "command -v pre-commit" in text
    return props


def property_check(path, hook_type):
    """Candidate skip-guard logic (the proposal under test).

    REAL pre-commit anatomy (empirically confirmed): ONE shim per hook
    type, each declaring only its OWN --hook-type=. So the guard checks
    each requested hook type's shim independently.
    """
    if not path.exists():
        return False, "shim missing"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"unreadable: {exc}"
    props = parse_shim(text)
    ip = props["install_python"]
    if not ip:
        return False, "no INSTALL_PYTHON line"
    if not Path(ip).exists():
        return False, f"dead interpreter: {ip}"
    args = props["args"] or ""
    if "hook-impl" not in args:
        return False, "not a pre-commit shim (foreign content)"
    if CONFIG_FLAG not in args:
        return False, f"missing {CONFIG_FLAG}"
    if f"--hook-type={hook_type}" not in args:
        return False, f"shim does not declare --hook-type={hook_type}"
    return True, "valid"


TEMPLATE_START = "# start templated"
TEMPLATE_END = "# end templated"


def locate_template_files():
    """Find installed pre-commit files containing the shim template."""
    import os

    import pre_commit

    pkg_dir = os.path.dirname(pre_commit.__file__)
    res = subprocess.run(
        ["grep", "-rl", TEMPLATE_START, pkg_dir], capture_output=True, text=True
    )
    files = [f for f in res.stdout.splitlines() if f.strip()]
    return files


def load_template_text(files):
    """Read the shim template.

    In pre-commit 4.6.0 the template lives in the package resource file
    `resources/hook-tmpl` (NOT a Python module — importing it as one
    crashed the previous run with AttributeError on spec.loader).
    """
    for f in files:
        path = Path(f)
        if path.name == "hook-tmpl":
            return path.read_text(encoding="utf-8")
    # Fallback: a .py module constant containing the template.
    for f in files:
        path = Path(f)
        if path.suffix != ".py":
            continue
        spec = importlib.util.spec_from_file_location("pc_template_mod", path)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in dir(mod):
            value = getattr(mod, name)
            if isinstance(value, str) and TEMPLATE_START in value:
                return value
    return None


def rebuild_shim(template_text, install_python, args):
    """Reconstruct shim bytes by splicing the templated block — the
    mechanism pre-commit's install_uninstall.py itself uses."""
    before = template_text.index(TEMPLATE_START)
    after = template_text.index(TEMPLATE_END) + len(TEMPLATE_END)
    block = (
        f"{TEMPLATE_START}\n"
        f"INSTALL_PYTHON={install_python}\n"
        f"ARGS=({args})\n"
        f"{TEMPLATE_END}"
    )
    return template_text[:before] + block + template_text[after:]


def main():
    print(f"pre-commit version: ", end="")
    res = subprocess.run(
        ["uv", "run", "python", "-c",
         "from importlib.metadata import version; print(version('pre-commit'))"],
        capture_output=True, text=True,
    )
    print(res.stdout.strip())

    # A. Parse the real shims in this repo.
    real = {}
    for ht in REQUESTED_HOOK_TYPES:
        path = HOOKS_DIR / ht
        text = path.read_text(encoding="utf-8")
        real[ht] = {"path": path, "text": text, "props": parse_shim(text)}
        props = real[ht]["props"]
        print(f"--- real shim {ht} ---")
        print(f"    INSTALL_PYTHON: {props['install_python']}")
        print(f"    ARGS:           {props['args']}")
        print(f"    template ID:    {props['template_id']}")
        ok, why = property_check(path, ht)
        check(f"property_check passes on real {ht} shim", ok, why)

    # B. Locate + extract the installed template (resource file hook-tmpl).
    files = locate_template_files()
    check("template source file located in installed package", bool(files), str(files))
    template = load_template_text(files)
    check("bash shim template extracted", template is not None)

    # C. Reconstruct shim bytes by splicing the templated block (the same
    # mechanism pre-commit uses) -> determinism proof.
    if template:
        for ht in REQUESTED_HOOK_TYPES:
            try:
                rebuilt = rebuild_shim(
                    template,
                    real[ht]["props"]["install_python"],
                    real[ht]["props"]["args"],
                )
                check(
                    f"reconstructed {ht} shim byte-identical to real shim",
                    rebuilt == real[ht]["text"],
                    "deterministic function of (template, INSTALL_PYTHON, args)",
                )
            except (ValueError, IndexError) as exc:
                check(
                    f"reconstructed {ht} shim byte-identical to real shim",
                    False,
                    f"splice failed: {exc} (property evidence still stands)",
                )

    # D. Simulate install methods: bytes differ, properties hold.
    # Real installs (pipx/uv/pip) all embed a LIVE interpreter path; the
    # previous run used nonexistent /home/user/... paths, so the guard
    # correctly rejected them as "dead interpreter" (exactly section E's
    # fallback behavior, not a guard deficiency). Here each simulated
    # install method gets an EXISTING interpreter file so the property
    # check under test isolates the install-method dimension alone.
    digests = set()
    if template:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            dummy_bin = tmpdir / "bin"
            dummy_bin.mkdir()
            for name in ("uv-python", "pip-python"):
                (dummy_bin / name).write_text("", encoding="utf-8")
            sim_paths = {
                "pipx (actual)": real["pre-commit"]["props"]["install_python"],
                "uv tool": str(dummy_bin / "uv-python"),
                "pip venv": str(dummy_bin / "pip-python"),
            }
            for method, ip in sim_paths.items():
                content = rebuild_shim(
                    template, ip, real["pre-commit"]["props"]["args"]
                )
                sim_file = tmpdir / "pre-commit"
                sim_file.write_text(content, encoding="utf-8")
                digests.add(hashlib.sha256(content.encode()).hexdigest())
                ok, why = property_check(sim_file, "pre-commit")
                check(f"property_check passes for {method} shim", ok, why)
            check(
                "byte-comparison is brittle across install methods",
                len(digests) == len(sim_paths),
                f"{len(digests)} distinct byte hashes across {len(sim_paths)} valid shims",
            )

    # E. Fallback triggers: guard must FAIL -> real install runs.
    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "absent"
        ok, why = property_check(missing, "pre-commit")
        check("missing shim fails property check", not ok, why)

        dead = Path(tmp) / "dead"
        dead.write_text(
            real["pre-commit"]["text"].replace(
                real["pre-commit"]["props"]["install_python"],
                "/nonexistent/venv/bin/python",
            ),
            encoding="utf-8",
        )
        ok, why = property_check(dead, "pre-commit")
        check("dead interpreter fails property check", not ok, why)

        foreign = Path(tmp) / "foreign"
        foreign.write_text("#!/bin/sh\necho not-pre-commit\n", encoding="utf-8")
        ok, why = property_check(foreign, "pre-commit")
        check("foreign content fails property check", not ok, why)

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)}): {failures}")
        return 1
    print("RESULT: ALL PASS — property-check is sufficient; byte-comparison is brittle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())