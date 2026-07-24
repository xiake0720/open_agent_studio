from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import or_, select

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.db.session import AsyncSessionLocal
from backend.app.models.model_config import ModelConfig


def compact(value: Any, *, limit: int = 1200) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, indent=2)
    else:
        text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...<truncated>"


def chat_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/chat/completions"


async def load_model_config(selector: str) -> ModelConfig:
    async with AsyncSessionLocal() as db:
        stmt = select(ModelConfig).where(
            or_(
                ModelConfig.id == selector,
                ModelConfig.model_id == selector,
                ModelConfig.display_name == selector,
            )
        )
        model_config = await db.scalar(stmt)

    if model_config is None:
        raise SystemExit(f"Model config not found: {selector}")
    return model_config


async def request_chat(
    *,
    model_config: ModelConfig,
    api_key: str,
    with_tools: bool,
    stream: bool,
    prompt: str,
) -> None:
    payload: dict[str, Any] = {
        "model": model_config.model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 128,
        "temperature": 0,
        "stream": stream,
    }
    if with_tools:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "Return a static test value.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                },
            }
        ]
        payload["tool_choice"] = "auto"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if stream else "application/json",
    }
    url = chat_url(model_config.base_url)
    mode = "stream" if stream else "plain"
    if with_tools:
        mode += "+tools"
    print(f"\n=== Testing {mode} ===")
    print(f"POST {url}")

    timeout = httpx.Timeout(60.0, connect=20.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            if stream:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    print(f"HTTP {response.status_code}")
                    if response.status_code >= 400:
                        body = await response.aread()
                        print(compact(body.decode("utf-8", errors="replace")))
                        return

                    lines: list[str] = []
                    async for line in response.aiter_lines():
                        if line:
                            lines.append(line)
                        if len(lines) >= 8:
                            break
                    print(compact("\n".join(lines)))
                    return

            response = await client.post(url, headers=headers, json=payload)
            print(f"HTTP {response.status_code}")
            try:
                print(compact(response.json()))
            except ValueError:
                print(compact(response.text))
        except httpx.TimeoutException as exc:
            print(f"TIMEOUT: {exc.__class__.__name__}")
        except httpx.HTTPError as exc:
            print(f"HTTPX_ERROR: {exc.__class__.__name__}: {exc}")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe an OpenAI-compatible model config from the local database."
    )
    parser.add_argument(
        "selector",
        nargs="?",
        default="moonshotai/kimi-k2.6",
        help="Model config id, model_id, or display_name.",
    )
    parser.add_argument("--prompt", default="Say OK in one short sentence.")
    parser.add_argument(
        "--skip-tools",
        action="store_true",
        help="Only send a plain chat request, even if support_tools is enabled.",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Also send a streaming request.",
    )
    args = parser.parse_args()

    model_config = await load_model_config(args.selector)
    api_key = os.getenv(model_config.api_key_env)

    print("Loaded model config")
    print(f"id: {model_config.id}")
    print(f"display_name: {model_config.display_name}")
    print(f"model_id: {model_config.model_id}")
    print(f"base_url: {model_config.base_url}")
    print(f"api_key_env: {model_config.api_key_env}")
    print(f"api_key_present: {bool(api_key)}")
    print(f"support_tools: {model_config.support_tools}")
    print(f"support_streaming: {model_config.support_streaming}")

    if not api_key:
        raise SystemExit(f"Missing environment variable: {model_config.api_key_env}")

    await request_chat(
        model_config=model_config,
        api_key=api_key,
        with_tools=False,
        stream=False,
        prompt=args.prompt,
    )
    if args.stream:
        await request_chat(
            model_config=model_config,
            api_key=api_key,
            with_tools=False,
            stream=True,
            prompt=args.prompt,
        )
    if model_config.support_tools and not args.skip_tools:
        await request_chat(
            model_config=model_config,
            api_key=api_key,
            with_tools=True,
            stream=False,
            prompt=args.prompt,
        )


if __name__ == "__main__":
    asyncio.run(main())
