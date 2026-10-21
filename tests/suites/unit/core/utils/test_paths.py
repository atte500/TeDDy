"""Unit tests for the shared pure path-normalization helper.

``normalize_resource_path`` single-sources the normalization pipeline that was
previously written inline (and is now delegated to from
``SessionService._extract_resource_path``): Markdown-link target extraction plus
backslash -> slash conversion, exact ``./`` prefix stripping, leading-slash
stripping (leading dots such as ``.hidden`` are preserved), and format-character
scrubbing, so a path never names a different file than the one it displays.
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


ZERO_WIDTH_SPACE = "\u200b"


def test_normalize_resource_path_scrubs_invisible_codepoints():
    assert normalize_resource_path(f"/{ZERO_WIDTH_SPACE}.gitignore") == ".gitignore"
    assert normalize_resource_path(f".{ZERO_WIDTH_SPACE}gitignore") == ".gitignore"
    assert (
        normalize_resource_path(
            f"[{ZERO_WIDTH_SPACE}.gitignore](/{ZERO_WIDTH_SPACE}.gitignore)"
        )
        == ".gitignore"
    )


def test_normalize_resource_path_preserves_shaping_joiners():
    emoji_sequence = "\U0001f469\u200d\U0001f4bb.md"
    assert normalize_resource_path(emoji_sequence) == emoji_sequence
