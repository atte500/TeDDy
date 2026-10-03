import os
import shlex
from typing import Optional, List
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.config_service import IConfigService


class ConsoleToolingHelper:
    # Curated list of known editor executables scanned by discover_editors().
    # Ordered: modern terminal editors first, then GUI/IDE editors.
    KNOWN_EDITORS: list[str] = [
        # Terminal editors (modern)
        "nvim",
        "vim",
        "vi",
        "helix",
        "hx",
        "nano",
        "micro",
        "kak",
        "emacs",
        "ne",
        "joe",
        "ed",
        "ex",
        "mg",
        "zee",
        "amp",
        # GUI editors
        "code",
        "codium",
        "cursor",
        "zed",
        "sublime_text",
        "subl",
        "atom",
        "pulsar",
        "brackets",
        "idea",
        "idea.sh",
        "webstorm",
        "phpstorm",
        "pycharm",
        "rubymine",
        "goland",
        "clion",
        "fleet",
        "eclipse",
        "netbeans",
        "bluefish",
        "gedit",
        "gnome-text-editor",
        "kate",
        "kwrite",
        "mousepad",
        "xed",
        "pluma",
        "leafpad",
        "geany",
        "notepadqq",
        "notepad++",
        "notepad",
        "wordpad",
        "vimr",
        "macvim",
        "textmate",
        "bbedit",
        "ultraedit",
        "windsurf",
        "tabnine",
        "tea",
        "cot",
        "textastic",
        "nova",
        "xcode",
        "android-studio",
    ]

    # Translation table mapping editor basenames to their diff viewer flags.
    # Only vim/nvim support the universal `-d` flag; GUI editors use their own.
    # Editors not in this table fall back to returning None (no diff viewer).
    _DIFF_FLAGS: dict[str, list[str]] = {
        "vim": ["-d"],
        "vi": ["-d"],
        "nvim": ["-d"],
        "code": ["--diff"],
        "cursor": ["--diff"],
        "codium": ["--diff"],
        "zed": ["--diff"],
        "idea": ["diff"],
    }

    def __init__(self, system_env: ISystemEnvironment, config_service: IConfigService):
        self._system_env = system_env
        self._config_service = config_service

    def discover_editors(self) -> list[tuple[str, str]]:
        """Scans PATH for known editors.

        Returns a list of ``(basename, resolved_path)`` pairs, deduplicated by
        resolved path (the same binary reachable under different aliases is
        reported once, under its first ``KNOWN_EDITORS`` name) and ordered by
        the ``KNOWN_EDITORS`` list.
        """
        found: list[tuple[str, str]] = []
        seen: set[str] = set()
        for editor in self.KNOWN_EDITORS:
            resolved = self._system_env.which(editor)
            if resolved and resolved not in seen:
                seen.add(resolved)
                found.append((editor, resolved))
        return found

    def get_diff_viewer_command(self) -> Optional[List[str]]:
        custom_tool_str = self._system_env.get_env("TEDDY_DIFF_TOOL")
        if custom_tool_str:
            custom_tool_parts = shlex.split(custom_tool_str)
            tool_name = custom_tool_parts[0]
            if tool_path := self._system_env.which(tool_name):
                custom_tool_parts[0] = tool_path
                return custom_tool_parts
            return None

        # Resolve editor from config or env directly
        editor_str = self._config_service.get_setting("editor")
        if not editor_str:
            editor_str = self._system_env.get_env("VISUAL") or self._system_env.get_env(
                "EDITOR"
            )

        if editor_str:
            parts = shlex.split(editor_str)
            tool_path = self._system_env.which(parts[0])
            if tool_path:
                basename = os.path.basename(tool_path).lower()
                if flags := self._DIFF_FLAGS.get(basename):
                    return [tool_path] + flags
        return None

    def find_editor(self) -> Optional[List[str]]:
        editor_str = self._config_service.get_setting("editor")

        # 0. "disabled" sentinel: the user explicitly disabled the editor.
        #    Return None immediately WITHOUT falling back to VISUAL/EDITOR
        #    env vars (case- and whitespace-insensitive).
        if editor_str and editor_str.strip().lower() == "disabled":
            return None

        # 1. Check Config
        if cmd := self._resolve_editor_cmd(editor_str):
            return cmd

        # 2. Check Env
        env_editor = self._system_env.get_env("VISUAL") or self._system_env.get_env(
            "EDITOR"
        )
        if cmd := self._resolve_editor_cmd(env_editor):
            return cmd

        return None

    def _resolve_editor_cmd(self, editor_str: Optional[str]) -> Optional[List[str]]:
        """Parses a command string and resolves the executable path."""
        if not editor_str:
            return None
        parts = shlex.split(editor_str)

        if tool_path := self._system_env.which(parts[0]):
            parts[0] = tool_path
            return parts
        return None
