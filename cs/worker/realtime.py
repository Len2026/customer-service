import asyncio
import json

from cs.app.services.realtime import RealtimeService
from cs.common.event_loop import run_async
from cs.common.settings import get_settings
from cs.infrastructure.db import async_session_factory
from cs.infrastructure.redis import redis_client


class RealtimeWorker:
    def __init__(self):
        self._settings = get_settings()
        self._session_factory = async_session_factory
        self._redis_client = redis_client
        engine = self._session_factory.kw["bind"]
        engine.echo = False

    async def start(self):
        print("RealtimeWorker发件箱处理器 is running...")
        while True:
            pulled = await self._pull_next_event() # 发件箱业务逻辑
            if not pulled:
                await asyncio.sleep(self._settings.realtime_worker_poll_interval_seconds)

    # 发件箱业务逻辑
    async def _pull_next_event(self):

        async with self._session_factory() as session:
            realtime_service = RealtimeService(session)
            # 获得未发布的消息
            event = await realtime_service.get_unpublish_event()
            if event is None:
                return False # 系统中没有消息，方法直接返回
            event_json = json.dumps(event.data,ensure_ascii=False)

            # 发布给对应的redis频道
            try:
                await self._redis_client.publish(event.target,event_json)
            except Exception as e:
                print(f"_pull_next_event，发布频道信息错误...:{e}")
                return False

            # 标记已发布
            await realtime_service.mark_published(event)
            return True

realtimeWorker = RealtimeWorker()
if __name__ == '__main__':
    run_async(realtimeWorker.start())

