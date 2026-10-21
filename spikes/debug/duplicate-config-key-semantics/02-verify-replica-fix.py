"""Proof: the replica rejects duplicate keys and honours exact-key precedence.

The replica lives beside this script. It is imported by file path so the
verification never touches production code. Exit code 0 means every check
passed.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _PROJECT_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from teddy_executor.core.domain.models.exceptions import ConfigurationError

_REPLICA_PATH = Path(__file__).with_name("replica_yaml_config_adapter.py")
_spec = importlib.util.spec_from_file_location("replica_yaml_adapter", _REPLICA_PATH)
assert _spec is not None and _spec.loader is not None
_replica = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_replica)
ReplicaAdapter = _replica.YamlConfigAdapter


def _workspace(base: Path, name: str) -> Path:
    root = base / name
    (root / ".teddy").mkdir(parents=True)
    return root


def _write(root: Path, text: str) -> Path:
    path = root / ".teddy" / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _load(root: Path) -> ReplicaAdapter:
    return ReplicaAdapter(config_path=".teddy/config.yaml", root_dir=str(root))


def duplicate_scalar_rejected(root: Path) -> bool:
    _write(root, "editor: first\neditor: second\n")
    try:
        _load(root)
    except ConfigurationError as exc:
        message = str(exc)
        return "editor" in message and "line 2" in message
    return False


def duplicate_mapping_rejected(root: Path) -> bool:
    _write(
        root,
        "execution:\n"
        "  max_output_lines: 5\n"
        "execution:\n"
        "  similarity_threshold: 0.9\n",
    )
    try:
        _load(root)
    except ConfigurationError as exc:
        return "execution" in str(exc)
    return False


def duplicate_nested_rejected(root: Path) -> bool:
    _write(
        root,
        "execution:\n"
        "  max_output_lines: 5\n"
        "  max_output_lines: 9\n",
    )
    try:
        _load(root)
    except ConfigurationError as exc:
        return "max_output_lines" in str(exc)
    return False


def exact_key_write(root: Path) -> bool:
    path = _write(root, 'llm:\n  model: nested-value\n"llm.model": flat-value\n')
    adapter = _load(root)
    if adapter.get_setting("llm.model") != "flat-value":
        return False
    adapter.set_setting("llm.model", "new")
    text = path.read_text(encoding="utf-8")
    return (
        '"llm.model": new' in text
        and "model: nested-value" in text
        and adapter.get_setting("llm.model") == "new"
        and _load(root).get_setting("llm.model") == "new"
    )


def nested_write(root: Path) -> bool:
    path = _write(root, "llm:\n  model: old\n")
    adapter = _load(root)
    adapter.set_setting("llm.model", "new")
    return (
        "model: new" in path.read_text(encoding="utf-8")
        and adapter.get_setting("llm.model") == "new"
        and _load(root).get_setting("llm.model") == "new"
    )


def comments_survive(root: Path) -> bool:
    text = '# keep me\neditor: "" # inline\nexecution:\n  max_output_lines: 100\n'
    path = _write(root, text)
    _load(root).set_setting("editor", "nvim")
    expected = text.replace('editor: ""', "editor: nvim")
    return path.read_text(encoding="utf-8") == expected


def unique_config_loads(root: Path) -> bool:
    _write(root, "editor: nvim\nexecution:\n  max_output_lines: 7\n")
    adapter = _load(root)
    return (
        adapter.get_setting("editor") == "nvim"
        and adapter.get_setting("execution.max_output_lines") == 7
    )


def baseline_only(root: Path) -> bool:
    value = _load(root).get_setting("execution.max_output_lines")
    return isinstance(value, int)


def unhashable_key_is_ignored(root: Path) -> bool:
    _write(root, "? [a, b]\n: value\n")
    value = _load(root).get_setting("execution.max_output_lines")
    return isinstance(value, int)


def quoted_nested_key_rewritten(root: Path) -> bool:
    path = _write(root, 'llm:\n  "model": old\n')
    adapter = _load(root)
    adapter.set_setting("llm.model", "new")
    return (
        '"model": new' in path.read_text(encoding="utf-8")
        and adapter.get_setting("llm.model") == "new"
        and _load(root).get_setting("llm.model") == "new"
    )


CHECKS = [
    ("duplicate scalar key raises ConfigurationError", duplicate_scalar_rejected),
    ("duplicate mapping key raises ConfigurationError", duplicate_mapping_rejected),
    ("duplicate nested key raises ConfigurationError", duplicate_nested_rejected),
    ("exact top-level dotted key wins the write", exact_key_write),
    ("nested-only key still writes nested", nested_write),
    ("comment-preserving write is byte-exact", comments_survive),
    ("unique config loads normally", unique_config_loads),
    ("baseline-only load still works", baseline_only),
    ("unhashable key falls back to an empty user config", unhashable_key_is_ignored),
    ("quoted nested key is rewritten in place", quoted_nested_key_rewritten),
]


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory(prefix="teddy-duplicate-key-replica-") as tmp:
        base = Path(tmp)
        for index, (name, check) in enumerate(CHECKS):
            root = _workspace(base, f"case-{index:02d}")
            ok = check(root)
            print(f"{'PASS' if ok else 'FAIL'}: {name}")
            failures += 0 if ok else 1
    print(f"{len(CHECKS) - failures} of {len(CHECKS)} checks passed.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())