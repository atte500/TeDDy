import subprocess


def test_vulture_passes_with_whitelist_only():
    """
    Verifies that Vulture reports zero unused items when running with the
    whitelist file and WITHOUT the brittle ignore_names in pyproject.toml.

    This test is intended to be a 'Ratchet' that ensures the transition
    is complete and correct.
    """
    # Note: In the final state, pyproject.toml won't have ignore_names.
    # For now, we expect this to FAIL until the implementation is done.
    result = subprocess.run(
        ["vulture", "src", "tests/harness/vulture_whitelist.py"],
        capture_output=True,
        text=True,
    )

    # We expect some failures initially as the whitelist doesn't exist yet.
    assert result.returncode == 0, f"Vulture found unused code: {result.stdout}"
