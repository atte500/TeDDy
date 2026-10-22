"""Acceptance coverage for the fail-fast typed-config boundary.

The public ``teddy start`` entry point must reject a config value that cannot
be coerced to its declared type. The run fails fast with exit code 1 and a
clear error line naming the offending key, before any planning happens.
"""

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


OFFENDING_KEY = "execute.max_output_lines"
OFFENDING_VALUE = "one hundred"


def _write_invalid_config(tmp_path) -> None:
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(exist_ok=True)
    (teddy_dir / "config.yaml").write_text(
        "execute:\n"
        f'  max_output_lines: "{OFFENDING_VALUE}"\n'
        "workspace:\n"
        "  init: false\n"
        "  pre-commit: false\n"
        "  pull: false\n",
        encoding="utf-8",
    )


def test_start_fails_fast_on_an_uncoercible_typed_value(tmp_path, monkeypatch):
    """A non-integer capacity value stops the run with a clean error line."""
    # Arrange
    (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_filesystem()
        .with_real_init_service()
        .with_real_config()
    )
    _write_invalid_config(tmp_path)
    (tmp_path / "README.md").write_text("# Workspace\n", encoding="utf-8")
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Act
    result = adapter.run_cli_command(
        ["start", "typed-config", "-a", "developer", "-m", "Test typed config"],
        input="n\n",
    )

    # Assert
    output = result.stdout + result.stderr
    assert result.exit_code == 1, output
    assert OFFENDING_KEY in output, output
    assert OFFENDING_VALUE in output, output
