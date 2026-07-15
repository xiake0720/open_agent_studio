from agents import FunctionTool

from backend.app.tools.basic_tools import (
    calculator,
    get_current_time,
    check_sensitive_words,
    explain_error_signature,
)


def build_general_tools() ->list[FunctionTool]:
    """
    构建GeneralAgent可用工具列表。
    :return:
    """
    return [
        get_current_time,
        calculator,
        check_sensitive_words,
        explain_error_signature,
    ]

