import asyncio

from sqlalchemy import func, select

from backend.app.db.init_db import init_db
from backend.app.db.session import AsyncSessionLocal
from backend.app.models import Conversation, Message, ModelConfig


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as db:
        conversation = Conversation(
            title="Day 3 数据库测试会话",
            agent_mode="general",
            default_model="glm-5.1",
        )

        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

        conversation_count = await db.scalar(
            select(func.count()).select_from(Conversation)
        )

        message_count = await db.scalar(
            select(func.count()).select_from(Message)
        )

        model_config_count = await db.scalar(
            select(func.count()).select_from(ModelConfig)
        )

        print("数据库初始化成功")
        print(f"新增会话ID：{conversation.id}")
        print(f"会话数量：{conversation_count}")
        print(f"消息数量：{message_count}")
        print(f"模型配置数量：{model_config_count}")


if __name__ == "__main__":
    asyncio.run(main())