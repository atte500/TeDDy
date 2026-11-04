"""Canonical EDIT scenarios for matcher and validator tests.

One source of truth for the EDIT scenarios: composable builders that produce the
canonical content and the FIND block a test drives them with, plus five named
``EditScenario`` bundles that pair content with its FIND block. A matcher or
validator test reads a named scenario instead of re-authoring fixture text.

The module is data only. It imports no matcher code, so it cannot couple tests to
the implementation they exercise.
"""

from typing import NamedTuple

SIBLING_BODY = (
    "    total = 0\n"
    "    for value in items:\n"
    "        if value > 0:\n"
    "            total += value\n"
    "        else:\n"
    "            total -= value\n"
    "    return total\n"
)


class EditScenario(NamedTuple):
    """A canonical EDIT scenario: the file content and the FIND block."""

    content: str
    find: str


def sibling_function(name: str) -> str:
    """An accumulator whose body is byte-identical across every sibling."""
    return f"def {name}(items):\n{SIBLING_BODY}"


def two_sibling_functions(first: str = "compute", second: str = "compote") -> str:
    """Two functions sharing one body, differing only in their def name."""
    return sibling_function(first) + "\n" + sibling_function(second)


def fuzzy_find(name: str) -> str:
    """The sibling block carrying a one-character typo in its def line."""
    return sibling_function(name)


def repeated_function(name: str, copies: int) -> str:
    """``copies`` byte-identical blocks, so every window ties exactly."""
    return "\n".join(sibling_function(name) for _ in range(copies))


DUPLICATE_BLOCK = "if ready:\n    process(items)\n    finalize()\n"


def duplicate_block_file() -> str:
    """One block repeated twice under surrounding setup and teardown calls."""
    return f"setup()\n\n{DUPLICATE_BLOCK}\nteardown()\n\n{DUPLICATE_BLOCK}\n"


REPEATED_LINE_BLOCK = (
    "def process(items):\n"
    '    log("step")\n'
    '    log("step")\n'
    '    log("step")\n'
    "    return True\n"
)


def repeated_line_file() -> str:
    """One block whose inner lines repeat inside a plain file."""
    return "prefix = 1\n\n" + REPEATED_LINE_BLOCK + "\nsuffix = 2\n"


def fuzzy_repeated_line_find() -> str:
    """The repeating-line block with a one-character typo in its def line."""
    return REPEATED_LINE_BLOCK.replace("def process(", "def proces(")


INDENTED_BLOCK = "def compute(items):\n    a = 1\n    b = 2\n    return a + b\n"


def indented_duplicate_file() -> str:
    """Two byte-identical indented blocks under different function names."""
    return INDENTED_BLOCK + "\n" + INDENTED_BLOCK.replace("compute", "compote")


def unindented_duplicate_find() -> str:
    """Indentation-only drift at both locations, so both promote to 1.0."""
    return "a = 1\nb = 2\nreturn a + b\n"


HANDLER_BLOCK = (
    "def process(items):\n"
    "    handle(items)\n"
    "    handle(items)\n"
    "    handle(items)\n"
    "    handle(items)\n"
    "    handle(items)\n"
    "    return True\n"
)


def handler_block_file() -> str:
    """One block whose inner lines repeat, so shifted starts stay similar."""
    return "prefix = 0\n\n" + HANDLER_BLOCK + "\nsuffix = 1\n"


def handler_tail_duplicate_file() -> str:
    """The block followed by its own tail, so a later start shares most lines."""
    return handler_block_file() + "\n" + "    handle(items)\n" * 3 + "suffix = 2\n"


def fuzzy_handler_find() -> str:
    """The handler block with a one-character typo in its def line."""
    return HANDLER_BLOCK.replace("def process(", "def proces(")


VERBATIM_VS_NEAR_DUPLICATE = EditScenario(
    content=two_sibling_functions(),
    find=sibling_function("compute"),
)

FUZZY_NEAR_TIE = EditScenario(
    content=two_sibling_functions(),
    find=fuzzy_find("computa"),
)

VERBATIM_DUPLICATE = EditScenario(
    content=duplicate_block_file(),
    find=DUPLICATE_BLOCK,
)

INDENTATION_ONLY_DUPLICATE = EditScenario(
    content=indented_duplicate_file(),
    find=unindented_duplicate_find(),
)

REPEATING_INNER_LINE = EditScenario(
    content=handler_block_file(),
    find=fuzzy_handler_find(),
)
