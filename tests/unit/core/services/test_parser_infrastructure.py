from teddy_executor.core.services.parser_infrastructure import extract_posix_headers


def test_extract_posix_headers_preserves_multiline_commands():
    """
    Given a command string with multiple lines but no directives,
    When extract_posix_headers is called,
    Then it should return the original multiline command string.
    """
    command_str = "echo 'hello'\necho 'world'"
    final_command, cwd, env = extract_posix_headers(command_str, None, None)

    assert final_command == command_str
    assert cwd is None
    assert env is None
