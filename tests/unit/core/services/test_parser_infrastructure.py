from teddy_executor.core.services.parser_infrastructure import translate_setup_commands


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
