import ast
import operator
from datetime import datetime

from zoneinfo import ZoneInfo

from agents import function_tool

@function_tool
def get_current_time(timezone: str = "Asia/Shanghai") -> str :
    """
    获取指定时区的当前时间
    Args:
        timezone: IANA 时区名称，例如Asia/Shanghai、UTC。
    :param timezone:
    :return:
    """
    try:
        now = datetime.now(ZoneInfo(timezone))
    except Exception:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        timezone = "Asia/Shanghai"

    return now.strftime(f"%Y-%m-%d %H:%M:%S {timezone}")


_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}



def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_eval_node(node.operand))

    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return _ALLOWED_OPERATORS[type(node.op)](left, right)

    raise ValueError("表达式只支持数字和 + - * / // % ** 运算")


@function_tool
def calculator(expression: str) -> str:
    """
    安全计算数学表达式。

    Args:
        expression: 数学表达式，例如 123 * 456 或 (1 + 2) * 3。
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree)
        return f"{expression} = {result}"
    except Exception as exc:
        return f"计算失败：{exc}"