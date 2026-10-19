"""Safe calculator: the LLM writes an expression, code computes the number.

Only arithmetic and a few finance helpers are allowed; names, attributes, calls to
anything else and very large powers are rejected, so model output can never execute
arbitrary code.
"""

import ast
import math
import operator
import re

BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def pct_change(old: float, new: float) -> float:
    """Percent change from old to new."""
    return (new - old) / abs(old) * 100


def cagr(start: float, end: float, years: float) -> float:
    """Compound annual growth rate, in percent."""
    return ((end / start) ** (1 / years) - 1) * 100


def ratio(a: float, b: float) -> float:
    return a / b


FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "pct_change": pct_change,
    "cagr": cagr,
    "ratio": ratio,
}


class CalcError(ValueError):
    pass


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int | float)
        and not isinstance(node.value, bool)
    ):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in BINARY:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise CalcError("exponent too large")
        try:
            return BINARY[type(node.op)](left, right)
        except ZeroDivisionError as exc:
            raise CalcError("division by zero") from exc
    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
        return UNARY[type(node.op)](_eval(node.operand))
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in FUNCTIONS
        and not node.keywords
    ):
        return FUNCTIONS[node.func.id](*[_eval(a) for a in node.args])
    raise CalcError(f"not allowed: {ast.dump(node)[:60]}")


def calculate(expression: str) -> float:
    if len(expression) > 500:
        raise CalcError("expression too long")
    try:
        # drop thousands separators ("1,234,567") but keep argument commas ("f(1, 2)")
        cleaned = THOUSANDS.sub("", expression).strip()
        tree = ast.parse(cleaned, mode="eval")
    except SyntaxError as exc:
        raise CalcError(f"syntax error: {exc.msg}") from exc
    return float(_eval(tree))
