"""Inspect model registration and tokenizer cost for the live session model.

Reads the latest session model from disk, checks whether its served and
actual IDs resolve against the LiteLLM cost registry, times
``litellm.token_counter`` on a payload near the live context size, and
reports the tiktoken encoding cache location and freshness.
"""

import importlib.metadata as metadata
import sys
import tempfile
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path("src").resolve()))


def latest_turn() -> Path:
    """Resolve the newest session and its highest-numbered turn directory."""
    sessions = sorted(
        [p for p in Path(".teddy/sessions").iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
    )
    session = sessions[-1]
    turns = sorted(
        [p for p in session.iterdir() if p.is_dir() and p.name.isdigit()],
        key=lambda p: p.name,
    )
    return turns[-1]


def main() -> None:
    turn = latest_turn()
    meta = yaml.safe_load((turn / "meta.yaml").read_text(encoding="utf-8"))
    served = str(meta.get("model") or "")
    actual = str(meta.get("actual_model") or "")

    import litellm

    print("litellm", metadata.version("litellm"))
    candidates = (
        ("served", served),
        ("actual", actual),
        ("served-bare", served.removeprefix("openrouter/")),
    )
    for label, model_id in candidates:
        print(f"{label}: {model_id!r} registered={model_id in litellm.model_cost}")

    payload = [
        {"role": "system", "content": "word " * 5000},
        {"role": "user", "content": "line " * 80000},
    ]
    for model_id in (served, actual):
        for attempt in ("first", "second"):
            start = time.perf_counter()
            try:
                count = litellm.token_counter(model=model_id, messages=payload)
                elapsed = time.perf_counter() - start
                print(f"token_counter model={model_id!r} {attempt}: {elapsed:.3f}s tokens={count}")
            except Exception as error:
                elapsed = time.perf_counter() - start
                print(
                    f"token_counter model={model_id!r} {attempt}: "
                    f"failed after {elapsed:.3f}s {type(error).__name__}: {error}"
                )

    cache = Path(tempfile.gettempdir()) / "data-gym-cache"
    print("tiktoken cache dir", cache, "exists", cache.exists())
    if cache.exists():
        for item in cache.glob("*"):
            age_days = (time.time() - item.stat().st_mtime) / 86400
            print(f"  {item.name[:20]} bytes={item.stat().st_size} age_days={age_days:.2f}")


if __name__ == "__main__":
    main()