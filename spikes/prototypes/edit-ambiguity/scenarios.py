"""Canonical EDIT scenarios for the slice 00-16 ambiguity prototypes."""

from __future__ import annotations

SIBLING_BODY = [
    "    total = 0",
    "    for value in items:",
    "        if value > 0:",
    "            total += value",
    "        else:",
    "            total -= value",
    "    return total",
]


def sibling_function(name: str) -> str:
    """An accumulator whose body is byte-identical across every sibling."""
    return "\n".join([f"def {name}(items):", *SIBLING_BODY]) + "\n"


def two_sibling_functions(first: str = "compute", second: str = "compote") -> str:
    return sibling_function(first) + "\n" + sibling_function(second)


def fuzzy_find(name: str) -> str:
    """The sibling block carrying a one-character typo in its def line."""
    return sibling_function(name)


def repeated_function(name: str, copies: int) -> str:
    """`copies` byte-identical blocks, so every window ties exactly."""
    return "\n".join(sibling_function(name) for _ in range(copies))


DUPLICATE_BLOCK = "if ready:\n    process(items)\n    finalize()\n"


def duplicate_block_file() -> str:
    return f"setup()\n\n{DUPLICATE_BLOCK}\nteardown()\n\n{DUPLICATE_BLOCK}\n"


REPEATED_LINE_BLOCK = (
    "def process(items):\n"
    '    log("step")\n'
    '    log("step")\n'
    '    log("step")\n'
    "    return True\n"
)


def repeated_line_file() -> str:
    return "prefix = 1\n\n" + REPEATED_LINE_BLOCK + "\nsuffix = 2\n"


def fuzzy_repeated_line_find() -> str:
    return REPEATED_LINE_BLOCK.replace("def process(", "def proces(")


INDENTED_BLOCK = (
    "def compute(items):\n"
    "    a = 1\n"
    "    b = 2\n"
    "    return a + b\n"
)


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
    return HANDLER_BLOCK.replace("def process(", "def proces(")
