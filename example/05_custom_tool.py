"""05 · Custom tool — implement your own `FlowToolCall`.

Subclass `FlowToolCall` to add a tool the model can call. This one is a local
arithmetic calculator: zero network, zero API keys beyond the LLM, fully
deterministic. The expression is parsed with `ast` and evaluated over a small
whitelist of operators, so there is no `eval` injection surface.

Run:
    python example/05_custom_tool.py

Needs an OpenAI-compatible key for the LLM (see ``_shared/provider.py``); the
tool itself needs nothing.
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Mapping
from typing import Any

from _shared import provider_from_env, stream_to_stdout
from pydantic import BaseModel, Field

from rath import flow
from rath.flow.tool import FlowToolCall
from rath.session import Session

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval(node: ast.AST) -> float:
    """Evaluate an arithmetic-only AST node; reject anything else."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("only +, -, *, /, //, %, ** over numbers are allowed")


class CalcInput(BaseModel):
    expression: str = Field(
        description="Arithmetic expression, e.g. '2 * (3 + 4) ** 2'.",
    )


class CalculatorTool(FlowToolCall):
    parallel_safe = True  # pure function, no shared state

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str | None:
        return "Evaluate an arithmetic expression and return the numeric result."

    @property
    def parameters(self) -> Mapping[str, Any]:
        return dict(CalcInput.model_json_schema())

    def __call__(
        self, session: Session, arguments: Mapping[str, Any]
    ) -> dict[str, Any]:
        model = CalcInput.model_validate(dict(arguments or {}))
        tree = ast.parse(model.expression, mode="eval")
        return {"expression": model.expression, "result": _safe_eval(tree)}


def main() -> None:
    agent = flow.Agent(
        "You can call the `calculator` tool for arithmetic. Use it instead of "
        "computing in your head, then state the answer in one short sentence.",
        provider_from_env(),
        tools=[CalculatorTool()],
        on_event=stream_to_stdout(),
    )

    user = Session.from_user_message(
        "What is (128 * 37) + (2 ** 10)? Use the calculator tool."
    ).to("local")

    agent(user)
    print()


if __name__ == "__main__":
    main()
