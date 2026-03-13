import shlex
from typing import Optional, List
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


class ConsoleToolingHelper:
    def __init__(self, system_env: ISystemEnvironment):
        self._system_env = system_env

    def get_diff_viewer_command(self) -> Optional[List[str]]:
        custom_tool_str = self._system_env.get_env("TEDDY_DIFF_TOOL")
        if custom_tool_str:
            custom_tool_parts = shlex.split(custom_tool_str)
            tool_name = custom_tool_parts[0]
            if tool_path := self._system_env.which(tool_name):
                custom_tool_parts[0] = tool_path
                return custom_tool_parts
            return None

        if code_path := self._system_env.which("code"):
            return [code_path, "-r", "--diff"]
        return None

    def find_editor(self) -> Optional[str]:
        editor = self._system_env.get_env("VISUAL") or self._system_env.get_env(
            "EDITOR"
        )
        if not editor:
            for fallback in ["code", "nano", "vim"]:
                if self._system_env.which(fallback):
                    return fallback
        return editor
