"""Shared harness for the configurable update-source acceptance tests.

Both acceptance modules need a bare ``punq.Container`` whose ``IConfigService``
reads a temp-rooted ``.teddy/config.yaml``. The builder and the minimal config
writer live here so the two tests cannot drift apart.
"""

from pathlib import Path

import punq

from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter
from teddy_executor.core.ports.outbound.config_service import IConfigService


def write_update_config(workspace: Path, index_url: str) -> Path:
    """Write a minimal user config carrying ``update.index_url`` under ``workspace``."""
    teddy_dir = workspace / ".teddy"
    teddy_dir.mkdir(exist_ok=True)
    config_path = teddy_dir / "config.yaml"
    config_path.write_text(f'update:\n  index_url: "{index_url}"\n', encoding="utf-8")
    return config_path


def container_with_config(config_path: Path) -> punq.Container:
    """Build a container whose config service reads ``config_path``.

    An uncreated path falls back to the bundled defaults, which is how the
    official-endpoint case exercises the default route.
    """
    container = punq.Container()
    container.register(
        IConfigService,
        factory=lambda: YamlConfigAdapter(config_path=str(config_path)),
    )
    return container
