from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cs.app.models.models import RealtimeEvent
from cs.common.utils import get_utcnow

class RealtimeService:
    def __init__(self, session: AsyncSession):
        self._session = session

    def add_event(self, message, conversation, *, notify_user, notify_staff):
        # 新增发件箱数据，targets可以单数，也可以是复数
        print("发件箱来了一条新消息...")
        targets: list[str] = []  # 因为发件目标有个能是多个

        # 根据发件箱消息管道内容进行判断
        if notify_user:
            targets.append(conversation.user_id)
        if notify_staff:
            targets.append("staff")

        # 封装data字段，给客服或者用户阅读
        event_data = {
            "conversation_mode": conversation.mode,
            "role": message.role,
            "content": message.content,
        }

        # 写入数据库
        for target in targets:
            self._session.add(RealtimeEvent(target=target, data=event_data))

    # 获得未发布事件
    async def get_unpublish_event(self):
        # print("get_unpublish_event，获得未发布事件...")
        stmt = select(RealtimeEvent).where(RealtimeEvent.published_at.is_(None)).order_by(RealtimeEvent.id).limit(1)
        return await self._session.scalar(stmt)

    # 更新发布事件
    async def mark_published(self, event):
        # print("mark_published，更新发布事件...")
        event.published_at = get_utcnow()
        await self._session.commit()
