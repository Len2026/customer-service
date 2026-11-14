import asyncio
from cs.infrastructure.db import async_engine
from cs.app.models.models import Base

# 初始化客服系统app /models
async def init_database():
    async with async_engine.begin()as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
if __name__=='__main__':

    # 事件循环
    run_async(init_database())