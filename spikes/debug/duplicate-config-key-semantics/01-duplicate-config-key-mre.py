"""Minimal reproducible example for Case File 50.

The enforced policy: a repeated key in ``.teddy/config.yaml`` stops the load
with a ``ConfigurationError``, and ``set_setting`` honours the same exact
top-level dotted-key precedence as ``get_setting``.

Run with ``uv run python``. Exit code 0 means the policy holds; exit code 1
means the defect is back.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter
from teddy_executor.core.domain.models.exceptions import ConfigurationError


def _new_workspace(parent: Path, name: str) -> Path:
    root = parent / name
    (root / ".teddy").mkdir(parents=True)
    return root


def _write_config(root: Path, text: str) -> Path:
    path = root / ".teddy" / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _load(root: Path) -> YamlConfigAdapter:
    return YamlConfigAdapter(config_path=".teddy/config.yaml", root_dir=str(root))


def _report(title: str, lines: list[str], defect: bool) -> bool:
    print(f"{'DEFECT' if defect else 'OK'}: {title}")
    for line in lines:
        print(f"  {line}")
    print()
    return defect


def _expect_duplicate_rejected(root: Path, key: str) -> bool:
    path = root / ".teddy" / "config.yaml"
    try:
        adapter = _load(root)
    except ConfigurationError as exc:
        message = str(exc)
        return _report(
            f"repeated key {key!r} stops the load",
            [f"error: {message}"],
            defect=key not in message,
        )
    lines = path.read_text(encoding="utf-8").splitlines()
    return _report(
        f"repeated key {key!r} stops the load",
        [
            "no error raised",
            "file contents:",
            *(f"    {line}" for line in lines),
            f"resolved value: {adapter.get_setting(key)!r}",
        ],
        defect=True,
    )


def repeated_scalar_key(root: Path) -> bool:
    _write_config(root, "editor: first\neditor: second\n")
    return _expect_duplicate_rejected(root, "editor")


def repeated_mapping_key(root: Path) -> bool:
    _write_config(
        root,
        "execution:\n"
        "  max_output_lines: 5\n"
        "  similarity_threshold: 0.5\n"
        "execution:\n"
        "  similarity_threshold: 0.9\n",
    )
    return _expect_duplicate_rejected(root, "execution")


def flat_key_wins_the_write(root: Path) -> bool:
    path = _write_config(
        root,
        'llm:\n  model: nested-value\n"llm.model": flat-value\n',
    )
    adapter = _load(root)
    before = adapter.get_setting("llm.model")
    adapter.set_setting("llm.model", "new")
    after_text = path.read_text(encoding="utf-8")
    reloaded = _load(root).get_setting("llm.model")
    return _report(
        "flat top-level dotted key wins the write",
        [
            f"value before write: {before!r}",
            "file after set_setting:",
            *(f"    {line}" for line in after_text.splitlines()),
            f"value after reload: {reloaded!r} (expected 'new')",
        ],
        defect=before != "flat-value" or reloaded != "new",
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="teddy-duplicate-key-") as tmp:
        base = Path(tmp)
        defects = [
            repeated_scalar_key(_new_workspace(base, "scalar")),
            repeated_mapping_key(_new_workspace(base, "mapping")),
            flat_key_wins_the_write(_new_workspace(base, "flat")),
        ]
    print(f"Policy holds for {len(defects) - sum(defects)} of {len(defects)} scenarios.")
    return 1 if any(defects) else 0


if __name__ == "__main__":
    sys.exit(main())