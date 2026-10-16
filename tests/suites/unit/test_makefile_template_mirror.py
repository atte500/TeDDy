"""Guard: the Makefile templates mirror the shipped ``ci-watch`` recipe.

Both ``docs/templates/makefile.md`` and the bundled
``src/teddy_executor/resources/templates/makefile.md`` are scaffolded into user
projects by ``teddy init templates``. They must stay byte-identical to each other
and must carry the corrected ``ci-watch`` recipe from the shipped ``Makefile``,
so a scaffolded project inherits the sound attribution logic. The shipped block
is extracted from the real ``Makefile``, so this guard tracks the source of truth
instead of a hardcoded copy.
"""

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SHIPPED_MAKEFILE = _PROJECT_ROOT / "Makefile"
_PROJECT_TEMPLATE = _PROJECT_ROOT / "docs" / "templates" / "makefile.md"
_BUNDLED_TEMPLATE = (
    _PROJECT_ROOT / "src" / "teddy_executor" / "resources" / "templates" / "makefile.md"
)

_RECIPE_START = "RETRY_POLLS ?= 10"
_RECIPE_END = "exit $$STATUS"


def _slice_between(text: str, start: str, end: str) -> str:
    assert start in text, f"missing start marker: {start!r}"
    assert end in text, f"missing end marker: {end!r}"
    begin = text.index(start)
    stop = text.index(end, begin) + len(end)
    return text[begin:stop]


def test_project_and_bundled_templates_are_byte_identical() -> None:
    assert _PROJECT_TEMPLATE.read_bytes() == _BUNDLED_TEMPLATE.read_bytes()


def test_templates_carry_the_shipped_ci_watch_recipe() -> None:
    shipped = _SHIPPED_MAKEFILE.read_text(encoding="utf-8")
    block = _slice_between(shipped, _RECIPE_START, _RECIPE_END)
    for template in (_PROJECT_TEMPLATE, _BUNDLED_TEMPLATE):
        assert block in template.read_text(encoding="utf-8"), (
            f"{template} does not mirror the shipped ci-watch recipe"
        )
