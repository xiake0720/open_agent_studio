import asyncio

from agents import Agent, Runner

from backend.app.db.init_db import init_db
from backend.app.db.session import AsyncSessionLocal
from backend.app.services.model_config_service import get_default_model_config
from backend.app.services.model_factory import build_chat_model
import os


async def main() -> None:
    print("\n开始初始化数据库...")
    await init_db()

    async with AsyncSessionLocal() as db:
        model_config = await get_default_model_config(db)
        # api_key = os.getenv(model_config.api_key_env)
        built_model = build_chat_model(model_config)

        agent = Agent(
            name="GeneralAgent",
            instructions="你是一个中文助手，请用简洁清晰的中文回答用户问题。",
            model=built_model.model,
            model_settings=built_model.model_settings,
        )

        result = await Runner.run(
            agent,
            "请用一句话介绍你自己。",
        )

        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())