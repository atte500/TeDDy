from teddy_executor.core.services.parser_infrastructure import (
    normalize_link_target,
    normalize_path,
    strip_format_characters,
    translate_setup_commands,
)


def test_translate_setup_commands_with_cd():
    setup_str = "cd src"
    cwd, env = translate_setup_commands(setup_str, None, None)
    assert cwd == "src"
    assert env is None


def test_translate_setup_commands_with_export():
    setup_str = "export FOO=bar"
    cwd, env = translate_setup_commands(setup_str, None, None)
    assert env == {"FOO": "bar"}
    assert cwd is None


def test_translate_setup_commands_with_mixed_and_chained():
    setup_str = 'cd src && export FOO=bar && export BAZ="qux"'
    cwd, env = translate_setup_commands(setup_str, None, None)
    assert cwd == "src"
    assert env == {"FOO": "bar", "BAZ": "qux"}


def test_translate_setup_commands_preserves_initial():
    setup_str = "export NEW=val"
    cwd, env = translate_setup_commands(setup_str, "init_cwd", {"INIT": "1"})
    assert cwd == "init_cwd"
    assert env == {"INIT": "1", "NEW": "val"}


ZERO_WIDTH_SPACE = "\u200b"


def test_strip_format_characters_removes_invisible_codepoints():
    assert strip_format_characters(f"{ZERO_WIDTH_SPACE}.gitignore") == ".gitignore"
    assert strip_format_characters("\ufeff.env") == ".env"
    assert strip_format_characters("src/app.py") == "src/app.py"


def test_normalize_path_removes_invisible_codepoints():
    assert normalize_path(f"{ZERO_WIDTH_SPACE}.gitignore") == ".gitignore"
    assert normalize_path(f".{ZERO_WIDTH_SPACE}gitignore") == ".gitignore"


def test_normalize_path_removes_percent_encoded_invisible_codepoints():
    assert normalize_path(".%E2%80%8Bgitignore") == ".gitignore"


def test_normalize_link_target_removes_invisible_codepoints():
    assert normalize_link_target(f"/{ZERO_WIDTH_SPACE}.gitignore") == ".gitignore"
    assert normalize_link_target(f"{ZERO_WIDTH_SPACE}/.gitignore") == ".gitignore"
    assert normalize_link_target("/.gitignore") == ".gitignore"


def test_strip_format_characters_preserves_shaping_joiners():
    emoji_sequence = "\U0001f469\u200d\U0001f4bb.md"
    assert strip_format_characters(emoji_sequence) == emoji_sequence
    joined_word = "a\u200cb.py"
    assert strip_format_characters(joined_word) == joined_word
