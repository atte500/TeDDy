#!/usr/bin/env python3
"""Spike 00-20 / Unknown 2: persistent OpenRouter registry cache design.

Decisions under test:
  - Storage format: JSON at `.teddy/.model_registry_cache.json`
    (dotfile = machine state, alongside .update_cache.json precedent).
    Payload: {"version": 1, "fetched_at_epoch": <int>, "models": [...]}.
  - TTL default: 7 days (604800s). Rationale: catalog/pricing drift is
    slow; bounded worst case = one 10s-timeout fetch per week per
    project, paid on the first turn after expiry.
  - Corrupt/missing/expired cache -> treated as empty -> refetch
    (never produce wrong telemetry).

Evidence produced:
  A. Round-trip save/load.
  B. TTL expiry -> refetch decision.
  C. Corrupt file -> empty (never wrong data).
  D. Missing file -> empty.
  E. Atomic write leaves no temp residue.
  F. `git check-ignore` proves the cache path is covered by the
     shipped .teddy/.gitignore template in a real git repo.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GITIGNORE_TEMPLATE = (
    REPO_ROOT / "src" / "teddy_executor" / "resources" / "config" / ".gitignore"
)
CACHE_FILENAME = ".model_registry_cache.json"
DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 days

failures = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" -- {detail}" if detail else ""))
    if not condition:
        failures.append(label)


def save_cache(path, models, fetched_at=None):
    payload = {
        "version": 1,
        "fetched_at_epoch": fetched_at if fetched_at is not None else int(time.time()),
        "models": models,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, path)  # atomic on POSIX and Windows


def load_cache(path, ttl_seconds=DEFAULT_TTL_SECONDS, now=None):
    now = now if now is not None else int(time.time())
    if not path.exists():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        models = payload["models"]
        fetched = int(payload["fetched_at_epoch"])
    except (ValueError, KeyError, TypeError):
        return None, "corrupt"
    if now - fetched >= ttl_seconds:
        return None, "expired"
    return models, "fresh"


def main():
    sample = [{"id": "openrouter/deepseek/deepseek-v4-flash", "context_length": 164000}]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cache = root / ".teddy" / CACHE_FILENAME

        # A. Round-trip.
        save_cache(cache, sample, fetched_at=int(time.time()))
        models, state = load_cache(cache)
        check("round-trip save/load", models == sample and state == "fresh", state)

        # B. TTL expiry.
        stale_time = int(time.time()) - DEFAULT_TTL_SECONDS - 1
        save_cache(cache, sample, fetched_at=stale_time)
        models, state = load_cache(cache)
        check("expired TTL -> refetch decision", models is None and state == "expired", state)

        # Boundary: exactly at TTL is expired (>=), one second before is fresh.
        save_cache(cache, sample, fetched_at=int(time.time()) - DEFAULT_TTL_SECONDS + 1)
        _, state = load_cache(cache)
        check("boundary: inside TTL stays fresh", state == "fresh", state)

        # C. Corrupt file.
        cache.write_text("{not json at all", encoding="utf-8")
        models, state = load_cache(cache)
        check("corrupt cache -> treated as empty", models is None and state == "corrupt", state)

        # D. Missing file.
        models, state = load_cache(root / ".teddy" / "absent.json")
        check("missing cache -> treated as empty", models is None and state == "missing", state)

        # E. Atomic write leaves no residue.
        save_cache(cache, sample)
        residue = list(cache.parent.glob("*.tmp"))
        check("atomic write leaves no .tmp residue", not residue, str(residue))

    # F. gitignore coverage with the REAL shipped template, in a real repo.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        teddy = repo / ".teddy"
        teddy.mkdir()
        (teddy / ".gitignore").write_text(
            GITIGNORE_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (teddy / CACHE_FILENAME).write_text("{}", encoding="utf-8")
        res = subprocess.run(
            ["git", "check-ignore", "-v", f".teddy/{CACHE_FILENAME}"],
            cwd=str(repo), capture_output=True, text=True,
        )
        check(
            f".teddy/{CACHE_FILENAME} is git-ignored by shipped template",
            res.returncode == 0,
            res.stdout.strip(),
        )

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)}): {failures}")
        return 1
    print("RESULT: ALL PASS — JSON cache design validated; path is git-ignored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())