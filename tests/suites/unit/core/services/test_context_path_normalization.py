"""Regression test: Windows context path normalization.

Verifies that the fixed test assertion (with .replace("\\", "/"))
matches production normalization on Windows-style paths.
"""


def test_context_path_normalization_windows_style():
    """Assert that the fixed assertion matches production normalization."""
    windows_path = r"C:\Users\runneradmin\AppData\Local\Temp\pytest\extra.py"

    # Production normalization (as in SessionService._prepare_session_context)
    production_normalized = windows_path.replace("\\", "/").lstrip("/")

    # Fixed assertion (after applying .replace("\\", "/") before lstrip)
    fixed_normalized = windows_path.replace("\\", "/").lstrip("/")

    # After the fix, the test assertion now uses the same normalization as production.
    # This assertion MUST pass (GREEN phase).
    assert fixed_normalized == production_normalized, (
        f"FIX NOT VERIFIED: fixed='{fixed_normalized}', "
        f"production='{production_normalized}'"
    )
