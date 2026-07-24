import json
import os
from dataclasses import dataclass
from json import JSONDecodeError

from typing import Any

from openai import AsyncOpenAI
from agents import (
    ModelSettings,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
)

from backend.app.core.exceptions import AppException
from backend.app.models.model_config import ModelConfig

# 你目前用的是自定义模型库，不使用 OpenAI 官方 Key。
# 所以先关闭 tracing，避免 SDK 尝试向 OpenAI 官方 tracing 服务上报。
set_tracing_disabled(True)


@dataclass
class BuiltModel:
    """
    模型构建结果。

    model:
        OpenAI Agents SDK 可以直接使用的模型对象。

    model_settings:
        第三方模型额外参数，例如 GLM 的 thinking disabled。

    config:
        数据库中的模型配置。
    """

    model: OpenAIChatCompletionsModel
    model_settings: ModelSettings
    config: ModelConfig

def parse_extra_body(extra_body_json: str | None) -> dict[str, Any] | None:
    """
    解析model_config.extra_body_json.

    例如GLM-5.1 关闭思考模式
    {"thinking":{"type":"disabled"}}
    :param extra_body_json:
    :return:
    """

    if not extra_body_json:
        return None

    try:
        value= json.loads(extra_body_json)
    except JSONDecodeError as exc:
        raise AppException(
            message="模型 extra_body_json 不是合法 JSON",
            code=40010,
            data={
                "extra_body_json": extra_body_json,
                "error": str(exc),
            },
        )

    if not isinstance(value, dict):
        raise AppException(
            message="模型 extra_body_json 必须是 JSON 对象",
            code=40011,
            data={"extra_body_json": extra_body_json},
        )

    return value

def build_chat_model(model_config: ModelConfig) -> BuiltModel:
    """
    根据数据库中的 ModelConfig 创建 OpenAI Agents SDK 模型对象。
    """

    if model_config.api_shape != "chat_completions":
        raise AppException(
            message="当前阶段只支持 chat_completions 模型",
            code=40012,
            data={
                "model_config_id": model_config.id,
                "api_shape": model_config.api_shape,
            },
        )

    api_key = (model_config.api_key or "").strip()
    if not api_key and model_config.api_key_env:
        api_key = os.getenv(model_config.api_key_env, "").strip()

    if not api_key:
        raise AppException(
            message="模型 API Key 未配置",
            code=40013,
            data={
                "api_key_env": model_config.api_key_env,
                "api_key_configured": bool(model_config.api_key),
                "model": model_config.display_name,
            },
        )

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=model_config.base_url,
        timeout=60.0,
        max_retries=0,
    )

    model = OpenAIChatCompletionsModel(
        model=model_config.model_id,
        openai_client=client,
    )

    extra_body = parse_extra_body(model_config.extra_body_json)

    model_settings = ModelSettings(
        extra_body=extra_body,
    )

    return BuiltModel(
        model=model,
        model_settings=model_settings,
        config=model_config,
    )
