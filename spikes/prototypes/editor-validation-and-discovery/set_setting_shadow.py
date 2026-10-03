"""Shadow implementation of YamlConfigAdapter.set_setting() for Slice 03-01 KU1.

Mirrors the body proposed in docs/project/specs/editor-validation-and-discovery.md
(§3) and a corrected variant that adds the two fixes the prototype proved
necessary:
  1. os.makedirs(parent_dir, exist_ok=True) before writing
  2. in-memory cache update so get_setting() reflects the new value immediately

Spike-local artifact; NOT imported by production code.
"""
from __future__ import annotations

import os
from typing import Any

import yaml


def set_setting_spec_proposed(config_path: str, key: str, value: Any) -> None:
    """Verbatim re-implementation of the spec's proposed set_setting body.

    Deliberately lacks directory creation and cache update so the spike can
    demonstrate the two gaps empirically.
    """
    user_config: dict = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}

    keys = key.split(".")
    current = user_config
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(user_config, f, default_flow_style=False, allow_unicode=True)


def set_setting_shadow(adapter: Any, key: str, value: Any) -> None:
    """Corrected shadow implementation: directory creation + cache update."""
    config_path = adapter._config_path
    parent = os.path.dirname(config_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    user_config: dict = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}

    keys = key.split(".")
    current = user_config
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(user_config, f, default_flow_style=False, allow_unicode=True)

    # Update the in-memory merged cache so subsequent get_setting() sees it.
    cache = adapter._config
    for k in keys[:-1]:
        cache = cache.setdefault(k, {})
    cache[keys[-1]] = value