import subprocess
from teddy.core.domain.models import CommandResult
from teddy.core.ports.outbound.shell_executor import ShellExecutor


class ShellAdapter(ShellExecutor):
    def run(self, command: str) -> CommandResult:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=False,  # `check=False` prevents raising an exception on non-zero exit codes
        )
        return CommandResult(
            stdout=result.stdout, stderr=result.stderr, return_code=result.returncode
        )
