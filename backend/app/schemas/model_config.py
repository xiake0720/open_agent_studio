from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelConfigResponse(BaseModel):
    """
    模型配置响应。

    返回给前端模型下拉框使用。
    注意：这里不会返回真实 API Key，只返回是否已配置和旧环境变量名。
    """

    id: str
    provider: str
    display_name: str
    model_id: str
    base_url: str
    api_key_configured: bool = False
    api_key_env: str | None = None
    api_shape: str
    support_streaming: bool
    support_tools: bool
    support_image: bool
    enabled: bool
    extra_body_json: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelConfigCreate(BaseModel):
    """
    创建模型配置请求。

    Day 6 暂时可以不用开放创建接口，
    但先定义出来，后面做模型管理页面时会用。
    """

    provider: str = Field(max_length=50)
    display_name: str = Field(max_length=100)
    model_id: str = Field(max_length=100)
    base_url: str = Field(max_length=500)
    api_key: str | None = Field(default=None, max_length=4096)
    api_key_env: str | None = Field(default=None, max_length=100)
    api_shape: str = Field(default="chat_completions", max_length=50)

    support_streaming: bool = True
    support_tools: bool = False
    support_image: bool = False
    enabled: bool = True

    extra_body_json: str | None = None
