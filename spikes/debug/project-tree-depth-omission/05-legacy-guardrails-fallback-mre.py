"""Probe: the typed schema may make the legacy guardrails fallback unreachable.

The guard reads ``guardrails.<key>`` with an unset sentinel and consults
``yolo_guardrails.<key>`` only when the sentinel survives. A declared key
always resolves through the typed schema, so the sentinel may never survive,
which would silently ignore a migrated user config.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

LEGACY_TURNS = 3
_UNSET = object()


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="teddy-guardrails-legacy-"))
    config_dir = root / ".teddy"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        f"yolo_guardrails:\n  max_turns: {LEGACY_TURNS}\n", encoding="utf-8"
    )

    from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter

    config = YamlConfigAdapter(config_path=".teddy/config.yaml", root_dir=str(root))

    renamed = config.get_setting("guardrails.max_turns", _UNSET)
    legacy = config.get_setting("yolo_guardrails.max_turns", _UNSET)

    print(f"legacy configured turns: {LEGACY_TURNS}")
    print(f"renamed key read: {renamed!r}")
    print(f"sentinel survived renamed read: {renamed is _UNSET}")
    print(f"legacy key read: {legacy!r}")
    print(f"legacy override honoured: {renamed == LEGACY_TURNS}")
    return 0 if renamed == LEGACY_TURNS else 1


if __name__ == "__main__":
    raise SystemExit(main())