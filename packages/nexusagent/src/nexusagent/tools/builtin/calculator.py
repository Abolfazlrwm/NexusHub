"""Calculator tool with a safe, AST-based expression evaluator.

The model-controlled expression is parsed with :mod:`ast` and evaluated
against an explicit whitelist of operators, functions and constants —
``eval``/``exec`` are never used, attribute access is structurally
impossible, and anything outside the whitelist fails with a message the
model can correct from.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Callable
from typing import Any, ClassVar

from ...exceptions import ToolExecutionError
from ..base import Tool

_MAX_EXPRESSION_LENGTH = 500
_MAX_EXPONENT = 10_000


def _format_number(value: int | float) -> str:
    """Render integers without a trailing ``.0``."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


class CalculatorTool(Tool):
    """Evaluate arithmetic expressions with whitelisted math functions."""

    name = "calculator"
    description = (
        "Evaluate a mathematical expression. Supports +, -, *, /, //, %, **, "
        "parentheses, unary minus, the functions abs, round, min, max, pow, "
        "sqrt, exp, log, log2, log10, sin, cos, tan, floor, ceil, and "
        "the constants pi, e, tau."
    )
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "The arithmetic expression to evaluate, e.g. 'sqrt(16) + 2**8'.",
            },
        },
        "required": ["expression"],
    }

    _FUNCTIONS: ClassVar[dict[str, Callable[..., int | float]]] = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "pow": pow,
        "sqrt": math.sqrt,
        "exp": math.exp,
        "log": math.log,
        "log2": math.log2,
        "log10": math.log10,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "floor": math.floor,
        "ceil": math.ceil,
    }
    _CONSTANTS: ClassVar[dict[str, float]] = {
        "pi": math.pi,
        "e": math.e,
        "tau": math.tau,
    }

    async def execute(self, **kwargs: Any) -> str:
        expression = str(kwargs.get("expression") or "").strip()
        if not expression:
            raise ToolExecutionError(
                "calculator requires a non empty 'expression' argument", tool=self.name
            )
        if len(expression) > _MAX_EXPRESSION_LENGTH:
            raise ToolExecutionError(
                f"expression longer than {_MAX_EXPRESSION_LENGTH} characters", tool=self.name
            )

        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ToolExecutionError(f"invalid expression: {exc.msg}", tool=self.name) from exc

        try:
            value = self._evaluate(tree.body)
        except ToolExecutionError:
            raise
        except ZeroDivisionError as exc:
            raise ToolExecutionError("division by zero", tool=self.name) from exc
        except (ArithmeticError, ValueError, TypeError) as exc:
            raise ToolExecutionError(
                f"cannot evaluate expression: {exc}", tool=self.name
            ) from exc
        return _format_number(value)

    # -- safe AST walker ------------------------------------------------------

    def _evaluate(self, node: ast.expr) -> int | float:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ToolExecutionError(
                    "only numeric literals are allowed", tool=self.name
                )
            return node.value

        if isinstance(node, ast.Name):
            if node.id in self._CONSTANTS:
                return self._CONSTANTS[node.id]
            raise ToolExecutionError(
                f"'{node.id}' is not an allowed constant", tool=self.name
            )

        if isinstance(node, ast.BinOp):
            left = self._evaluate(node.left)
            right = self._evaluate(node.right)
            return self._apply_operator(node.op, left, right)

        if isinstance(node, ast.UnaryOp):
            operand = self._evaluate(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
            raise ToolExecutionError("unsupported unary operator", tool=self.name)

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in self._FUNCTIONS:
                raise ToolExecutionError(
                    "only whitelisted math functions may be called", tool=self.name
                )
            if node.keywords:
                raise ToolExecutionError(
                    "keyword arguments are not supported", tool=self.name
                )
            arguments = [self._evaluate(arg) for arg in node.args]
            return self._FUNCTIONS[node.func.id](*arguments)

        raise ToolExecutionError(
            f"unsupported syntax: {type(node).__name__}", tool=self.name
        )

    def _apply_operator(
        self, op: ast.operator, left: int | float, right: int | float
    ) -> int | float:
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.Div):
            return left / right
        if isinstance(op, ast.FloorDiv):
            return left // right
        if isinstance(op, ast.Mod):
            return left % right
        if isinstance(op, ast.Pow):
            if abs(right) > _MAX_EXPONENT:
                raise ToolExecutionError(
                    f"exponent magnitude above {_MAX_EXPONENT} is not allowed",
                    tool=self.name,
                )
            return left**right
        raise ToolExecutionError("unsupported binary operator", tool=self.name)
