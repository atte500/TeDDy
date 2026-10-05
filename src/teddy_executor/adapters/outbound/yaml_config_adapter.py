import os
import re
from importlib import resources
from typing import Any, Dict, Optional
import yaml
from dotenv import dotenv_values, set_key
from teddy_executor.core.ports.outbound.config_service import IConfigService

_INTERPOLATION_PATTERN = re.compile(
    r"\$\$|\$\{([_A-Za-z][_A-Za-z0-9]*)(?::-([^}]*))?\}"
)


class YamlConfigAdapter(IConfigService):
    """
    Implements IConfigService by reading configuration from a YAML file.
    """

    def __init__(
        self, config_path: str = ".teddy/config.yaml", root_dir: Optional[str] = None
    ):
        if root_dir:
            self._config_path = os.path.join(root_dir, config_path)
        else:
            self._config_path = config_path
        self._config: Dict[str, Any] = self._load_layered_config()

    def _load_layered_config(self) -> Dict[str, Any]:
        """Loads the baseline config and merges it with the user config."""
        # 1. Load Bundled Baseline
        config = self._load_baseline()

        # 2. Load User Overrides
        user_config = self._load_user_config()

        # 3. Simple Deep Merge (Layered)
        self._merge_dicts(config, user_config)

        return config

    def _load_baseline(self) -> Dict[str, Any]:
        """Loads the bundled baseline config from package resources."""
        try:
            resource_path = resources.files("teddy_executor.resources.config").joinpath(
                "config.yaml"
            )
            with resource_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except (yaml.YAMLError, OSError, ImportError, AttributeError):
            return {}

    def _load_user_config(self) -> Dict[str, Any]:
        """Loads the user-specific YAML configuration file if it exists."""
        if not os.path.exists(self._config_path):
            return {}

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except (yaml.YAMLError, OSError):
            return {}

    def _merge_dicts(self, base: Dict[str, Any], overrides: Dict[str, Any]) -> None:
        """Recursively merges overrides into base. Prunes keys set to None."""
        for key, value in overrides.items():
            if value is None:
                if key in base:
                    del base[key]
            elif isinstance(value, dict):
                if key not in base or not isinstance(base[key], dict):
                    base[key] = {}
                self._merge_dicts(base[key], value)
            else:
                base[key] = value

    def get_setting(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        Retrieves a configuration value by its key from the loaded YAML.
        Supports nested keys using dot notation (e.g., 'outer.inner').
        """
        if not key:
            return default

        # 1. Try exact match first (highest priority: top-level user overrides)
        if key in self._config:
            return self._maybe_interpolate(self._config[key])

        # 2. Try nested resolution (standard hierarchical structure)
        parts = key.split(".")
        result = self._resolve_nested(parts)

        if result is not None:
            return self._maybe_interpolate(result)

        return default

    def get_config_path(self) -> str:
        """Returns the path to the configuration file."""
        return self._config_path

    def _env_file_path(self) -> str:
        """Returns the path to the ``.env`` file inside the config directory."""
        return os.path.join(os.path.dirname(self._config_path), ".env")

    def set_env_variable(self, name: str, value: str) -> None:
        """Persists a secret to the ``.env`` file WITHOUT mutating ``os.environ``.

        Writing via ``dotenv.set_key`` (never ``load_dotenv``) keeps the secret
        out of the process environment, so it cannot leak into the shell child
        processes that ``EXECUTE`` actions spawn inside the user's repo.
        """
        env_path = self._env_file_path()
        parent_dir = os.path.dirname(env_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        set_key(env_path, name, value, quote_mode="always")

    def _build_interpolation_env(self) -> Dict[str, str]:
        """Build the lookup table used to resolve ``${VAR}`` tokens.

        Values from ``.teddy/.env`` are layered UNDER ``os.environ`` so a real
        shell environment variable wins over the file. ``.env`` is read FRESH on
        every call (never cached), which is what keeps a key written mid-run live
        across the transient ``IConfigService`` instances.
        """
        env: Dict[str, str] = {}
        for name, value in dotenv_values(self._env_file_path()).items():
            if value is not None:
                env[name] = value
        env.update(os.environ)
        return env

    def _interpolate(self, text: str) -> str:
        """Resolve ``${VAR}`` / ``${VAR:-default}`` tokens in ``text``.

        ``$$`` collapses to a literal ``$`` and consumes the following text so it
        is not re-interpolated. An unresolved token without a default becomes the
        empty string. Text with no ``${`` is returned unchanged.
        """
        if "${" not in text:
            return text
        env = self._build_interpolation_env()

        def _replace(match: "re.Match[str]") -> str:
            if match.group(0) == "$$":
                return "$"
            name, default = match.group(1), match.group(2)
            value = env.get(name)
            if value is not None:
                return value
            return default if default is not None else ""

        return _INTERPOLATION_PATTERN.sub(_replace, text)

    def _maybe_interpolate(self, value: Any) -> Any:
        """Recursively interpolate string values containing ``${VAR}`` tokens.

        Handles nested dicts, lists, and plain strings. Non-string leaf values
        are returned unchanged. The caller is responsible for providing a
        deep copy if the source should not be mutated.
        """
        if isinstance(value, str):
            if "${" in value:
                return self._interpolate(value)
            return value
        if isinstance(value, dict):
            return {k: self._maybe_interpolate(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._maybe_interpolate(item) for item in value]
        return value

    def _resolve_nested(self, parts: list[str]) -> Optional[Any]:
        """Iteratively resolves nested keys."""
        current = self._config
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def set_setting(self, key: str, value: Any) -> None:
        """Persist ONLY the target key's value, preserving all other bytes.

        Comments, key ordering, blank lines and inline comments are retained
        because the file is edited as raw text rather than round-tripped
        through a data-only loader (``yaml.safe_load``/``yaml.dump``), which
        would strip all comments and reformat the document.

        Supports dot-notation for nested keys. The user config file and its
        parent directory are created if they do not exist. After writing, the
        in-memory merged cache is updated so a subsequent ``get_setting()`` on
        THIS adapter reflects the change without a reload.
        """
        # 1. Ensure the parent directory exists.
        parent_dir = os.path.dirname(self._config_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # 2. Read the current user config as raw text.
        text = ""
        if os.path.exists(self._config_path):
            with open(self._config_path, "r", encoding="utf-8") as f:
                text = f.read()

        # 3. Surgically rewrite ONLY the target value token.
        key_path = key.split(".")
        text = self._surgically_set(text, key_path, value)

        with open(self._config_path, "w", encoding="utf-8") as f:
            f.write(text)

        # 4. Synchronize the in-memory merged cache so a subsequent
        #    get_setting() on THIS adapter reflects the change.
        cache = self._config
        for part in key_path[:-1]:
            nxt = cache.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                cache[part] = nxt
            cache = nxt
        cache[key_path[-1]] = value

    def _scalar_repr(self, value: Any) -> str:
        """Render a scalar value as YAML text with no document-end marker."""
        dumped = yaml.safe_dump(value, default_flow_style=True, allow_unicode=True)
        return dumped.replace("\n...\n", "").replace("\n...", "").strip()

    def _find_key_line(self, lines: list[str], key_path: list[str]) -> Optional[int]:
        """Locate the line index defining ``key_path`` via an indent-aware scan."""
        stack: list[tuple[int, str]] = []
        for idx, raw in enumerate(lines):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("- "):
                continue
            if ":" not in stripped:
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            key_part = stripped.split(":", 1)[0].strip()
            while stack and stack[-1][0] >= indent:
                stack.pop()
            current = [k for _, k in stack] + [key_part]
            if current == key_path:
                return idx
            stack.append((indent, key_part))
        return None

    def _surgically_set(self, text: str, key_path: list[str], value: Any) -> str:
        """Rewrite only the value token of ``key_path``, or append the key."""
        lines = text.split("\n")
        value_str = self._scalar_repr(value)

        idx = self._find_key_line(lines, key_path)
        if idx is not None:
            raw = lines[idx]
            colon = raw.index(":")
            after = raw[colon + 1 :]
            comment = ""
            m = re.search(r"\s+#", after)
            if m:
                comment = after[m.start() :]
            lines[idx] = f"{raw[: colon + 1]} {value_str}{comment}"
            return "\n".join(lines)

        lines = self._strip_degenerate_root(lines)
        return self._insert_key(lines, key_path, value_str)

    def _strip_degenerate_root(self, lines: list[str]) -> list[str]:
        """Remove a lone flow/empty-root token ('{}', 'null', '~').

        A file whose entire (non-comment, non-blank) content is a degenerate
        empty-root token would otherwise produce invalid YAML when a block
        mapping key is appended after it (appending 'editor: nvim' after a bare
        '{}' line raises a YAML parse error). Comment lines are preserved.
        """
        content = [
            (i, ln)
            for i, ln in enumerate(lines)
            if ln.strip() and not ln.strip().startswith("#")
        ]
        if len(content) == 1:
            i, ln = content[0]
            if ln.strip() in ("{}", "null", "~"):
                del lines[i]
        return lines

    def _find_ancestor(
        self, lines: list[str], key_path: list[str]
    ) -> tuple[int, Optional[int], int]:
        """Find the deepest existing ancestor of ``key_path``.

        Returns ``(ancestor_len, ancestor_idx, ancestor_indent)``: the number of
        leading key segments already present (0 when none), the ancestor's line
        index (None when absent) and its indentation (-1 when absent).
        """
        for n in range(len(key_path) - 1, 0, -1):
            idx = self._find_key_line(lines, key_path[:n])
            if idx is not None:
                indent = len(lines[idx]) - len(lines[idx].lstrip(" "))
                return n, idx, indent
        return 0, None, -1

    def _render_key_lines(
        self, missing: list[str], base_indent: int, value_str: str
    ) -> list[str]:
        """Render block-mapping lines for the missing key segments."""
        last = len(missing) - 1
        new_lines: list[str] = []
        for i, seg in enumerate(missing):
            indent = " " * (base_indent + 2 * i)
            suffix = f" {value_str}" if i == last else ""
            new_lines.append(f"{indent}{seg}:{suffix}")
        return new_lines

    def _find_insertion_point(
        self, lines: list[str], ancestor_idx: Optional[int], ancestor_indent: int
    ) -> int:
        """Compute where to splice new key lines so they nest correctly."""
        if ancestor_idx is None:
            insert_at = len(lines)
            while insert_at > 0 and lines[insert_at - 1].strip() == "":
                insert_at -= 1
            return insert_at
        insert_at = ancestor_idx + 1
        while insert_at < len(lines):
            s = lines[insert_at]
            st = s.strip()
            if st == "" or st.startswith("#"):
                insert_at += 1
                continue
            ind = len(s) - len(s.lstrip(" "))
            if ind > ancestor_indent:
                insert_at += 1
                continue
            break
        return insert_at

    def _insert_key(self, lines: list[str], key_path: list[str], value_str: str) -> str:
        """Append ``key_path`` (creating parent mappings) at the right indent."""
        ancestor_len, ancestor_idx, ancestor_indent = self._find_ancestor(
            lines, key_path
        )
        missing = key_path[ancestor_len:]
        base_indent = ancestor_indent + 2 if ancestor_idx is not None else 0
        new_lines = self._render_key_lines(missing, base_indent, value_str)
        insert_at = self._find_insertion_point(lines, ancestor_idx, ancestor_indent)
        lines[insert_at:insert_at] = new_lines
        return "\n".join(lines)
