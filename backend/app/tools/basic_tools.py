import ast
import operator
from datetime import datetime

from zoneinfo import ZoneInfo

from agents import RunContextWrapper, function_tool
import json

from backend.app.agents.context import AppRunContext

@function_tool
def get_current_time(
    context: RunContextWrapper[AppRunContext],
    timezone: str = "Asia/Shanghai",
) -> str:
    """
    获取指定时区的当前时间
    Args:
        timezone: IANA 时区名称，例如Asia/Shanghai、UTC。
    :param timezone:
    :return:
    """
    context.context.require_permission("tool.basic")
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

SENSITIVE_WORDS = {
    "最强": {
        "risk_type": "夸大宣传",
        "suggestion": "建议替换为“强劲”“表现突出”“优选”等更稳妥表达",
    },
    "第一": {
        "risk_type": "绝对化用语",
        "suggestion": "建议替换为“靠前”“热销”“受欢迎”等表达",
    },
    "根治": {
        "risk_type": "医疗化/功效承诺",
        "suggestion": "建议替换为“改善”“缓解”“帮助处理”等表达",
    },
    "永久": {
        "risk_type": "绝对承诺",
        "suggestion": "建议替换为“持久”“长效”“一段时间内”等表达",
    },
    "100%": {
        "risk_type": "绝对化承诺",
        "suggestion": "建议替换为“有效减少”“帮助改善”等表达",
    },
    "绝对": {
        "risk_type": "绝对化用语",
        "suggestion": "建议删除或替换为“更”“较为”“有助于”等表达",
    },
    "全网最低": {
        "risk_type": "价格绝对化",
        "suggestion": "建议替换为“高性价比”“实惠之选”等表达",
    },
}


@function_tool
def check_sensitive_words(
    context: RunContextWrapper[AppRunContext],
    text: str,
) -> str:
    """
    检查电商文案中的常见风险词，并给出替代表达建议。

    Args:
        text: 需要检查的商品标题、主图文案或详情页文案。
    """
    context.context.require_permission("tool.basic")
    items = []

    for word, rule in SENSITIVE_WORDS.items():
        if word in text:
            items.append({
                "word": word,
                "risk_type": rule["risk_type"],
                "suggestion": rule["suggestion"],
            })

    result = {
        "has_risk": len(items) > 0,
        "risk_count": len(items),
        "items": items,
        "safe_text_suggestion": text,
    }

    return json.dumps(result, ensure_ascii=False)

ERROR_RULES = [
    {
        "keyword": "ModuleNotFoundError",
        "error_type": "模块未安装或导入路径错误",
        "reason": "Python 找不到指定模块，常见原因是依赖未安装、虚拟环境选错、包名写错。",
        "steps": [
            "确认当前 Python 解释器是否是项目 .venv",
            "执行 uv pip list 或 pip list 检查依赖是否存在",
            "确认 import 的包名和安装包名是否一致",
            "检查项目中是否存在同名 .py 文件导致模块遮蔽",
        ],
    },
    {
        "keyword": "ImportError",
        "error_type": "导入失败",
        "reason": "模块存在，但目标类、函数或变量无法导入，可能是版本不匹配或导入路径错误。",
        "steps": [
            "打印模块路径确认导入的是哪个包",
            "检查包版本是否符合文档要求",
            "检查是否安装了同名错误包",
        ],
    },
    {
        "keyword": "TypeError",
        "error_type": "类型错误",
        "reason": "函数参数类型、参数数量或对象调用方式不符合预期。",
        "steps": [
            "检查函数签名",
            "打印变量类型 type(value)",
            "确认是否把协程对象当普通结果使用",
        ],
    },
    {
        "keyword": "SyntaxError",
        "error_type": "语法错误",
        "reason": "Python 代码语法不合法，例如缩进、括号、冒号或 await 使用位置错误。",
        "steps": [
            "检查报错行附近的缩进",
            "确认 async 函数外没有直接使用 await",
            "检查括号、引号、冒号是否闭合",
        ],
    },
    {
        "keyword": "401",
        "error_type": "认证失败",
        "reason": "API Key 缺失、错误、过期，或请求到了错误的服务商。",
        "steps": [
            "检查 .env 中的 API Key",
            "确认 base_url 是否正确",
            "确认模型供应商和密钥是否匹配",
        ],
    },
]


@function_tool
def explain_error_signature(error_text: str) -> str:
    """
    根据报错文本识别常见 Python / API 错误类型，并给出排查步骤。

    Args:
        error_text: 用户粘贴的报错文本。
    """
    matched = []

    for rule in ERROR_RULES:
        if rule["keyword"] in error_text:
            matched.append(rule)

    if not matched:
        matched.append({
            "keyword": "unknown",
            "error_type": "未识别错误",
            "reason": "当前规则库没有匹配到明确错误类型，需要结合完整堆栈继续分析。",
            "steps": [
                "复制完整 traceback",
                "从最后一行错误类型开始看",
                "定位第一个出现在你自己项目文件中的行号",
                "逐步打印关键变量",
            ],
        })

    return json.dumps(
        {
            "matched_count": len(matched),
            "matched": matched,
        },
        ensure_ascii=False,
    )
