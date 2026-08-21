"""Tests for parameter coercion utility functions and parser integration."""

from teddy_executor.core.services.parser_infrastructure import (
    coerce_param,
    coerce_action_params,
)
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser


class TestCoerceParam:
    def test_int_from_clean_string(self):
        assert coerce_param("42", int) == 42

    def test_int_from_string_with_suffix(self):
        assert coerce_param("10 seconds", int) == 10

    def test_int_from_non_numeric_string(self):
        assert coerce_param("garbage", int) is None

    def test_int_from_none(self):
        assert coerce_param(None, int) is None

    def test_float_from_string_with_suffix(self):
        assert coerce_param("3.5 minutes", float) == 3.5

    def test_float_from_non_numeric_string(self):
        assert coerce_param("abc", float) is None

    def test_bool_from_true(self):
        assert coerce_param("true", bool) is True

    def test_bool_from_false(self):
        assert coerce_param("false", bool) is False


class TestCoerceActionParams:
    def test_timeout_string_coerced(self):
        result = coerce_action_params({"timeout": "10 seconds"}, {"timeout": int})
        assert result["timeout"] == 10

    def test_non_numeric_timeout_removed(self):
        result = coerce_action_params({"timeout": "garbage"}, {"timeout": int})
        assert "timeout" not in result

    def test_multiple_params(self):
        params = {"timeout": "30 seconds", "allow_failure": "true"}
        type_map = {"timeout": int, "allow_failure": bool}
        result = coerce_action_params(params, type_map)
        assert result["timeout"] == 30
        assert result["allow_failure"] is True


class TestParseExecuteActionWithStringTimeout:
    def test_string_timeout_parsed_as_int(self):
        plan_lines = [
            "# Test Plan",
            "- **Agent:** TestAgent",
            "",
            "## Rationale",
            "~~~~~~",
            "Rationale",
            "~~~~~~",
            "",
            "## Action Plan",
            "",
            "### `EXECUTE`",
            "- **Timeout:** 10 seconds",
            "",
            "~~~~~~shell",
            "echo hello",
            "~~~~~~",
        ]
        parser = MarkdownPlanParser()
        plan_str = "\n".join(plan_lines)
        result = parser.parse(plan_str)
        action = next(a for a in result.actions if a.type.upper() == "EXECUTE")
        t = action.params.get("timeout")
        assert isinstance(t, int), f"Expected int, got {type(t).__name__}: {t!r}"
        assert t == 10

    def test_non_numeric_timeout_removed(self):
        plan_lines = [
            "# Test Plan",
            "- **Agent:** TestAgent",
            "",
            "## Rationale",
            "~~~~~~",
            "Rationale",
            "~~~~~~",
            "",
            "## Action Plan",
            "",
            "### `EXECUTE`",
            "- **Timeout:** garbage",
            "",
            "~~~~~~shell",
            "echo hello",
            "~~~~~~",
        ]
        parser = MarkdownPlanParser()
        plan_str = "\n".join(plan_lines)
        result = parser.parse(plan_str)
        action = next(a for a in result.actions if a.type.upper() == "EXECUTE")
        assert "timeout" not in action.params
