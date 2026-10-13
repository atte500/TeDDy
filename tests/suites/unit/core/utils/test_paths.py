"""Unit tests for the shared pure path-normalization helper.

``normalize_resource_path`` single-sources the normalization pipeline that was
previously written inline (and is now delegated to from
``SessionService._extract_resource_path``): Markdown-link target extraction plus
backslash -> slash conversion, exact ``./`` prefix stripping, and leading-slash
stripping (leading dots such as ``.hidden`` are preserved).
"""

import pytest

from teddy_executor.core.utils.paths import normalize_resource_path


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Markdown-link target extraction (forward- and back-slash targets).
        ("[file](src/logic.py)", "src/logic.py"),
        ("[file](src\\logic.py)", "src/logic.py"),
        ("[file](\\src/mixed\\path.py)", "src/mixed/path.py"),
        # Raw paths: backslash normalization, leading-slash strip, ./ strip.
        ("docs\\spec.md", "docs/spec.md"),
        ("/abs/path/file.md", "abs/path/file.md"),
        ("./docs/readme.md", "docs/readme.md"),
        # Leading dot (hidden file) must survive the ./ strip rule.
        (".hidden/file.md", ".hidden/file.md"),
        # Surrounding whitespace on a raw path is trimmed.
        ("  docs/readme.md  ", "docs/readme.md"),
        # Empty input is a valid degenerate case.
        ("", ""),
    ],
)
def test_normalize_resource_path(raw, expected):
    assert normalize_resource_path(raw) == expected
