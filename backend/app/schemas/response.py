from typing import Generic,Optional,TypeVar

from pydantic import BaseModel

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    """
    统一 API 响应结构。

    后续前端只需要判断：
    code === 0 表示成功
    code !== 0 表示失败
    """

    code: int = 0
    message: str = "success"
    data: Optional[T] = None


def success(data=None, message: str = "success") -> ApiResponse:
    return ApiResponse(
        code=0,
        message=message,
        data=data,
    )


def fail(code: int = 500, message: str = "error", data=None) -> ApiResponse:
    return ApiResponse(
        code=code,
        message=message,
        data=data,
    )