import base64
import binascii
import json
import os
from uuid import uuid4

import httpx
from agents import RunContextWrapper, function_tool

from backend.app.agents.context import AppRunContext
from backend.app.core.config import DATA_DIR, settings


def _image_extension(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp", "image/webp"
    raise ValueError("NVIDIA 返回了无法识别的图片格式")


@function_tool
async def generate_flux_image(
    context: RunContextWrapper[AppRunContext],
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    seed: int = 0,
    steps: int = 4,
) -> str:
    """使用 NVIDIA FLUX.2-klein-4b 生成图片，并返回当前 Run 可访问的图片 URL。"""

    app_context = context.context
    app_context.require_permission("image.generate")
    if not prompt.strip():
        raise ValueError("生图提示词不能为空")
    if not (256 <= width <= 2048 and width % 64 == 0):
        raise ValueError("width 必须在 256-2048 之间且为 64 的倍数")
    if not (256 <= height <= 2048 and height % 64 == 0):
        raise ValueError("height 必须在 256-2048 之间且为 64 的倍数")
    if not 1 <= steps <= 50:
        raise ValueError("steps 必须在 1-50 之间")

    api_key = os.getenv("NVIDIA_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_KEY 环境变量未配置")

    payload = {
        "prompt": prompt.strip(),
        "width": width,
        "height": height,
        "seed": seed,
        "steps": steps,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=settings.NVIDIA_IMAGE_TIMEOUT_SECONDS) as client:
            response = await client.post(
                settings.NVIDIA_IMAGE_INVOKE_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"NVIDIA 生图请求失败（HTTP {exc.response.status_code}）") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("NVIDIA 生图服务连接失败") from exc

    body = response.json()
    artifacts = body.get("artifacts") if isinstance(body, dict) else None
    encoded = artifacts[0].get("base64") if isinstance(artifacts, list) and artifacts else None
    if not isinstance(encoded, str) or not encoded:
        raise RuntimeError("NVIDIA 生图响应缺少 artifacts[0].base64")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError("NVIDIA 生图响应包含无效 Base64 图片") from exc

    extension, media_type = _image_extension(image_bytes)
    filename = f"{uuid4()}{extension}"
    output_dir = DATA_DIR / "generated" / app_context.run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    output_path.write_bytes(image_bytes)

    return json.dumps(
        {
            "run_id": app_context.run_id,
            "model": "black-forest-labs/flux.2-klein-4b",
            "url": f"/api/generated/{app_context.run_id}/{filename}",
            "media_type": media_type,
            "width": width,
            "height": height,
            "seed": seed,
            "steps": steps,
        },
        ensure_ascii=False,
    )
