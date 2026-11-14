from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from cs.common.settings import get_settings

async_engine:AsyncEngine = create_async_engine(
    url = get_settings().database_url,
    echo = True,
)

# 工厂
async_session_factory:async_sessionmaker[AsyncSession] = async_sessionmaker(
    async_engine,
    expire_on_commit = False,

)

# 获取session
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            print(f"数据库链接异常：{e}")
            await session.rollback()
            raise e


# 测试
if __name__ == '__main__':
    engine = create_async_engine(
        "postgresql+psycopg://customer_service:customer_service@192.168.222.66:5432/customer_service")
    print(engine.name)
    session = get_async_session()
    print(session)