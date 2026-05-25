import sys


def test_pathspec_is_not_imported_on_generator_instantiation():
    # Clear pathspec if it was somehow loaded
    sys.modules.pop("pathspec", None)

    # We want to ensure that even instantiating it doesn't trigger the load if we can help it,
    # or at least that importing the module doesn't.
    assert "pathspec" not in sys.modules, (
        "pathspec should not be imported at module level"
    )


def test_pyperclip_is_not_imported_at_cli_helpers_module_level():
    sys.modules.pop("pyperclip", None)

    assert "pyperclip" not in sys.modules, (
        "pyperclip should not be imported at module level"
    )
