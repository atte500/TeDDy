import subprocess
import sys

from typer.testing import CliRunner

runner = CliRunner()


def test_heavy_libraries_are_not_loaded_on_startup():
    """
    Scenario: Heavy libraries are lazy-loaded
    Given the teddy tool is installed
    When I run 'teddy --help'
    Then 'litellm' MUST NOT be in sys.modules
    And 'trafilatura' MUST NOT be in sys.modules
    And 'ddgs' MUST NOT be in sys.modules
    """
    # We use a subprocess to ensure we're checking the actual CLI startup process
    # and not the state of the current pytest process.
    # We use sys.executable to ensure we use the same virtualenv.
    cmd = [
        sys.executable,
        "-c",
        "import sys; from teddy_executor.__main__ import app; "
        "print('litellm' in sys.modules); "
        "print('trafilatura' in sys.modules); "
        "print('ddgs' in sys.modules)",
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, env={"PYTHONPATH": "src"}
    )

    if result.returncode != 0:
        print(result.stderr)

    assert result.returncode == 0
    outputs = result.stdout.strip().split("\n")

    # These should be False after the optimization
    assert outputs[0] == "False", (
        f"litellm should be lazy-loaded, but was found in sys.modules: {outputs[0]}"
    )
    assert outputs[1] == "False", (
        f"trafilatura should be lazy-loaded, but was found in sys.modules: {outputs[1]}"
    )
    assert outputs[2] == "False", (
        f"ddgs should be lazy-loaded, but was found in sys.modules: {outputs[2]}"
    )
