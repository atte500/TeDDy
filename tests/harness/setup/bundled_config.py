"""Shared loader for the bundled config.yaml.

Contract tests assert shipped values from the bundled file. This module keeps
one loader so the resource location has a single source of truth.
"""

from importlib import resources
from typing import Any

import yaml


def load_bundled_config() -> dict[str, Any]:
    """Load the bundled config.yaml as a parsed mapping from the package resource."""
    resource = resources.files("teddy_executor.resources.config").joinpath(
        "config.yaml"
    )
    return yaml.safe_load(resource.read_text(encoding="utf-8"))
