"""Contract coverage for the shared canonical EDIT scenario harness.

``tests.harness.setup.edit_scenarios`` provides one source of truth for the
EDIT matcher scenarios: composable builders that produce the canonical content
and the FIND block a test drives them with. Each bundle is a content/find pair,
so a matcher or validator test reads a named scenario instead of re-authoring
ten lines of fixture text.
"""

from tests.harness.setup.edit_scenarios import (
    DUPLICATE_BLOCK,
    FUZZY_NEAR_TIE,
    INDENTATION_ONLY_DUPLICATE,
    REPEATING_INNER_LINE,
    VERBATIM_DUPLICATE,
    VERBATIM_VS_NEAR_DUPLICATE,
    EditScenario,
    fuzzy_find,
    repeated_function,
    sibling_function,
    two_sibling_functions,
)


def test_sibling_function_wraps_the_shared_body_under_a_named_def():
    block = sibling_function("compute")

    assert block.startswith("def compute(items):\n")
    assert block.endswith("    return total\n")


def test_two_sibling_functions_holds_both_named_defs():
    content = two_sibling_functions()

    assert content.count("def compute(items):") == 1
    assert content.count("def compote(items):") == 1


def test_fuzzy_find_carries_the_sibling_body_under_a_slipped_name():
    find = fuzzy_find("computa")

    assert find == sibling_function("computa")


def test_repeated_function_generates_the_requested_copy_count():
    for copies in (2, 3, 5, 7):
        content = repeated_function("compute", copies)

        assert content.count("def compute(items):") == copies


def test_verbatim_duplicate_scenario_repeats_one_block_twice():
    assert VERBATIM_DUPLICATE.content.count(DUPLICATE_BLOCK) == 2
    assert VERBATIM_DUPLICATE.find == DUPLICATE_BLOCK


def test_verbatim_vs_near_duplicate_finds_the_exact_sibling():
    content = VERBATIM_VS_NEAR_DUPLICATE.content
    find = VERBATIM_VS_NEAR_DUPLICATE.find

    assert content.count(find) == 1


def test_fuzzy_near_tie_find_is_not_verbatim_but_shares_the_body():
    content = FUZZY_NEAR_TIE.content
    find = FUZZY_NEAR_TIE.find

    assert find not in content
    assert find.replace("computa", "compute") in content


def test_indentation_only_duplicate_find_is_the_unindented_body():
    content = INDENTATION_ONLY_DUPLICATE.content
    find = INDENTATION_ONLY_DUPLICATE.find

    assert find not in content
    assert content.count("    a = 1\n") == 2


def test_repeating_inner_line_find_is_not_verbatim():
    content = REPEATING_INNER_LINE.content
    find = REPEATING_INNER_LINE.find

    assert find not in content
    assert find.replace("def proces(", "def process(") in content


def test_canonical_scenarios_are_content_find_pairs():
    scenarios = [
        VERBATIM_VS_NEAR_DUPLICATE,
        FUZZY_NEAR_TIE,
        VERBATIM_DUPLICATE,
        INDENTATION_ONLY_DUPLICATE,
        REPEATING_INNER_LINE,
    ]

    for scenario in scenarios:
        assert isinstance(scenario, EditScenario)
        assert scenario.content
        assert scenario.find
