import asyncio

from sqlalchemy import func, select

from backend.app.db.init_db import init_db
from backend.app.db.session import AsyncSessionLocal, engine
from backend.app.models.model_config import ModelConfig


async def main() -> None:
    print("当前数据库地址：")
    print(engine.url)

    print("\n开始初始化数据库...")
    await init_db()

    async with AsyncSessionLocal() as db:
        count_stmt = select(func.count(ModelConfig.id))
        count_result = await db.execute(count_stmt)
        total_count = count_result.scalar_one()

        print(f"\nmodel_configs 总数量：{total_count}")

        enabled_count_stmt = select(func.count(ModelConfig.id)).where(
            ModelConfig.enabled.is_(True)
        )
        enabled_count_result = await db.execute(enabled_count_stmt)
        enabled_count = enabled_count_result.scalar_one()

        print(f"enabled=True 数量：{enabled_count}")

        list_stmt = select(ModelConfig).order_by(
            ModelConfig.provider.asc(),
            ModelConfig.display_name.asc(),
        )

        result = await db.execute(list_stmt)
        models = result.scalars().all()

        print("\n所有模型配置：")
        for model in models:
            print("-" * 60)
            print(f"id: {model.id}")
            print(f"display_name: {model.display_name}")
            print(f"provider: {model.provider}")
            print(f"model_id: {model.model_id}")
            print(f"base_url: {model.base_url}")
            print(f"api_key_env: {model.api_key_env}")
            print(f"enabled: {model.enabled}")


if __name__ == "__main__":
    asyncio.run(main())