import shlex
from typing import Optional, List
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.config_service import IConfigService


class ConsoleToolingHelper:
    def __init__(self, system_env: ISystemEnvironment, config_service: IConfigService):
        self._system_env = system_env
        self._config_service = config_service

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

    def find_editor(self) -> Optional[List[str]]:
        # 1. Check Config
        editor_str = self._config_service.get_setting("editor")

        # 2. Check Env
        if not editor_str:
            editor_str = self._system_env.get_env("VISUAL") or self._system_env.get_env(
                "EDITOR"
            )

        if editor_str:
            parts = shlex.split(editor_str)
            if tool_path := self._system_env.which(parts[0]):
                parts[0] = tool_path
                return parts

        # 3. Discovery Fallback
        for fallback in ["code", "nano", "vim"]:
            if path := self._system_env.which(fallback):
                return [path]

        return None
