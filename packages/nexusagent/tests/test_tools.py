"""Tests for the tool registry and built-in tools."""

from __future__ import annotations

from datetime import datetime

import pytest

from nexusagent.exceptions import ToolExecutionError, ToolNotFoundError
from nexusagent.tools import (
    CalculatorTool,
    CurrentDateTimeTool,
    ToolRegistry,
    UuidTool,
    register_builtin_tools,
)


class TestToolRegistry:
    def test_register_and_get(self) -> None:
        registry = ToolRegistry()
        tool = registry.register(CalculatorTool())
        assert tool is not None
        assert "calculator" in registry
        assert len(registry) == 1
        assert isinstance(registry.get("calculator"), CalculatorTool)

    def test_duplicate_registration_raises(self) -> None:
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(CalculatorTool())

    def test_get_unknown_tool_returns_none(self) -> None:
        assert ToolRegistry().get("nope") is None

    def test_require_unknown_tool_raises(self) -> None:
        with pytest.raises(ToolNotFoundError):
            ToolRegistry().require("nope")

    def test_unregister(self) -> None:
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        registry.unregister("calculator")
        registry.unregister("calculator")  # idempotent
        assert len(registry) == 0

    def test_openai_schemas_sorted_and_shaped(self) -> None:
        registry = register_builtin_tools(ToolRegistry())
        schemas = registry.openai_schemas()
        assert [s["function"]["name"] for s in schemas] == [
            "calculator",
            "current_datetime",
            "generate_uuid",
        ]
        for schema in schemas:
            assert schema["type"] == "function"
            assert schema["function"]["description"]
            assert schema["function"]["parameters"]["type"] == "object"

    def test_iteration_yields_tools(self) -> None:
        registry = register_builtin_tools(ToolRegistry())
        assert {tool.name for tool in registry} == {
            "calculator",
            "current_datetime",
            "generate_uuid",
        }


class TestCalculatorTool:
    @pytest.fixture
    def calculator(self) -> CalculatorTool:
        return CalculatorTool()

    async def test_operator_precedence(self, calculator: CalculatorTool) -> None:
        assert await calculator.execute(expression="2+2*10") == "22"

    async def test_parentheses(self, calculator: CalculatorTool) -> None:
        assert await calculator.execute(expression="(2+2)*10") == "40"

    async def test_float_result(self, calculator: CalculatorTool) -> None:
        assert await calculator.execute(expression="10/4") == "2.5"

    async def test_integer_result_has_no_decimal(self, calculator: CalculatorTool) -> None:
        assert await calculator.execute(expression="sqrt(16)") == "4"

    async def test_functions_and_constants(self, calculator: CalculatorTool) -> None:
        result = await calculator.execute(expression="sqrt(16) + pi")
        assert float(result) == pytest.approx(4 + 3.141592653589793)

    async def test_power(self, calculator: CalculatorTool) -> None:
        assert await calculator.execute(expression="2**10") == "1024"

    async def test_unary_minus(self, calculator: CalculatorTool) -> None:
        assert await calculator.execute(expression="-(3+4)") == "-7"

    async def test_division_by_zero_is_soft_error(self, calculator: CalculatorTool) -> None:
        with pytest.raises(ToolExecutionError, match="division by zero"):
            await calculator.execute(expression="1/0")

    async def test_empty_expression_rejected(self, calculator: CalculatorTool) -> None:
        with pytest.raises(ToolExecutionError, match="non empty"):
            await calculator.execute(expression="   ")

    async def test_missing_argument_rejected(self, calculator: CalculatorTool) -> None:
        with pytest.raises(ToolExecutionError, match="non empty"):
            await calculator.execute()

    async def test_import_injection_blocked(self, calculator: CalculatorTool) -> None:
        with pytest.raises(ToolExecutionError):
            await calculator.execute(expression="__import__('os').system('echo hi')")

    async def test_attribute_access_blocked(self, calculator: CalculatorTool) -> None:
        with pytest.raises(ToolExecutionError):
            await calculator.execute(
                expression="().__class__.__mro__[1].__subclasses__()"
            )

    async def test_unknown_name_blocked(self, calculator: CalculatorTool) -> None:
        with pytest.raises(ToolExecutionError, match="not an allowed constant"):
            await calculator.execute(expression="os + 1")

    async def test_string_literal_blocked(self, calculator: CalculatorTool) -> None:
        with pytest.raises(ToolExecutionError, match="numeric literals"):
            await calculator.execute(expression="'abc'")

    async def test_keyword_arguments_blocked(self, calculator: CalculatorTool) -> None:
        with pytest.raises(ToolExecutionError, match="keyword arguments"):
            await calculator.execute(expression="sqrt(x=16)")

    async def test_huge_exponent_blocked(self, calculator: CalculatorTool) -> None:
        with pytest.raises(ToolExecutionError, match="exponent"):
            await calculator.execute(expression="2**99999999")


class TestCurrentDateTimeTool:
    @pytest.fixture
    def clock(self) -> CurrentDateTimeTool:
        return CurrentDateTimeTool()

    async def test_default_utc(self, clock: CurrentDateTimeTool) -> None:
        result = await clock.execute()
        parsed = datetime.fromisoformat(result)
        assert parsed.utcoffset().total_seconds() == 0

    async def test_tehran_timezone(self, clock: CurrentDateTimeTool) -> None:
        result = await clock.execute(timezone="Asia/Tehran")
        parsed = datetime.fromisoformat(result)
        assert parsed.utcoffset().total_seconds() == 3.5 * 3600

    async def test_unknown_timezone(self, clock: CurrentDateTimeTool) -> None:
        with pytest.raises(ToolExecutionError, match="unknown timezone"):
            await clock.execute(timezone="Nowhere/Nothing")


class TestUuidTool:
    @pytest.fixture
    def uuids(self) -> UuidTool:
        return UuidTool()

    async def test_single_uuid(self, uuids: UuidTool) -> None:
        result = await uuids.execute()
        assert len(result) == 36
        assert result.count("-") == 4
        assert result[14] == "4"  # UUID4 marker

    async def test_multiple_uuids(self, uuids: UuidTool) -> None:
        result = await uuids.execute(count=5)
        lines = result.splitlines()
        assert len(lines) == 5
        assert len(set(lines)) == 5  # all unique

    async def test_count_bounds(self, uuids: UuidTool) -> None:
        with pytest.raises(ToolExecutionError, match="between 1 and 32"):
            await uuids.execute(count=0)
        with pytest.raises(ToolExecutionError, match="between 1 and 32"):
            await uuids.execute(count=33)

    async def test_non_integer_count(self, uuids: UuidTool) -> None:
        with pytest.raises(ToolExecutionError, match="must be an integer"):
            await uuids.execute(count="many")


def test_builtin_registration_helper_is_idempotent_per_registry() -> None:
    registry = register_builtin_tools(ToolRegistry())
    assert len(registry) == 3
    with pytest.raises(ValueError):
        register_builtin_tools(registry)
