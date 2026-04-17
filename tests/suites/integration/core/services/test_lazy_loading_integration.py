import subprocess
import sys

import pytest
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
    And 'mistletoe' MUST NOT be in sys.modules
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
        "print('ddgs' in sys.modules); "
        "print('mistletoe' in sys.modules)",
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
    assert outputs[3] == "False", (
        f"mistletoe should be lazy-loaded, but was found in sys.modules: {outputs[3]}"
    )


def test_web_scraper_github_url_does_not_import_trafilatura():
    """
    Regression Test: Ensures that scraping a GitHub URL does NOT trigger
    the import of trafilatura (and its native lxml dependency).
    """
    # We use a subprocess to ensure a clean sys.modules state
    code = """
import sys
import responses
from teddy_executor.adapters.outbound.web_scraper_adapter import WebScraperAdapter

@responses.activate
def run():
    scraper = WebScraperAdapter()
    url = "https://github.com/octocat/Spoon-Knife/issues/1"
    responses.add(responses.GET, url, body="<html></html>", status=200)

    # Pre-check
    if "trafilatura" in sys.modules:
        sys.exit(2)

    scraper.get_content(url)

    if "trafilatura" in sys.modules:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    run()
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "src"},
    )

    exit_code_already_imported = 2
    exit_code_success = 0

    if result.returncode == exit_code_already_imported:
        pytest.fail("trafilatura was already in sys.modules before the test started.")

    assert result.returncode == exit_code_success, (
        "trafilatura was imported prematurely for a GitHub URL!"
    )
