from agents import FunctionTool

from backend.app.tools.basic_tools import (
    calculator,
    check_sensitive_words,
    explain_error_signature,
    get_current_time,
)


def build_general_tools() -> list[FunctionTool]:
    """
    通用 Agent 可使用的基础工具。
    """

    return [
        get_current_time,
        calculator,
    ]


def build_tech_tools() -> list[FunctionTool]:
    """
    技术 Agent 可使用的工具。
    """

    return [
        explain_error_signature,
        calculator,
    ]


def build_ecommerce_tools() -> list[FunctionTool]:
    """
    电商 Agent 可使用的工具。
    """

    return [
        check_sensitive_words,
    ]