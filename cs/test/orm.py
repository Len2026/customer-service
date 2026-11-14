import asyncio
import selectors
from asyncio import WindowsSelectorEventLoopPolicy

from sqlalchemy import String
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from atguigu.common.settings import get_settings

# 引擎实例
engin = create_async_engine(
    url=get_settings().database_url,
    echo=False,
)
# session实例
sessionLocal = async_sessionmaker(
    engin,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    print("根据需求加入一些关于数据库映射的基类的配置")
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))
    age: Mapped[int] = mapped_column(default=10)

    def __repr__(self) -> str:
        return f"User(id={self.id},name={self.name},age={self.age})"
    # print(user)

# 增删改查
async def crud_demo(session:AsyncSession):
    user = User(name="张三",age=10)
    session.add(user)
    await session.commit()
    print(user)


# 测试方法
async def main():
    # 建表
    # async with engin.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)

    # crud
    async with sessionLocal() as session:
        await crud_demo(session)


if __name__ == "__main__":
    # 方案1 windows策略
    # asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    # asyncio.run(main())

    # 方案1 python策略
    asyncio.run(main(),loop_factory=lambda :asyncio.SelectorEventLoop(selectors.SelectSelector()))
