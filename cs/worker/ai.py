import asyncio

import httpx

from cs.app.schemas import CurrentUser
from cs.app.services.auth import encode_token
from cs.app.services.chat import ChatService
from cs.common.event_loop import run_async
from cs.common.settings import get_settings
from cs.infrastructure.db import async_session_factory


class AIWorker:
    def __init__(self):
        self._settings = get_settings()
        self._session_factory = async_session_factory
        engine = self._session_factory.kw["bind"]
        engine.echo = False

    async def start(self):
        print("AIWorker轮次处理器 is running...")
        while True:
            # print("AIWorker，i am working ...")
            claimed_turn = await self._process_next_turn()  # 处理轮次核心逻辑
            if claimed_turn is False:
                await asyncio.sleep(self._settings.ai_worker_pull_interval_ms / 1000)

    # 轮次核心处理流程
    async def _process_next_turn(self):
        # print("_process_next_turn,开始处理轮次...")
        async with self._session_factory() as session:
            # 1 领取轮次
            chat_service = ChatService(session)
            claimed = await chat_service.claim_turn() # 领取轮次
            if claimed is None:
                return False # 系统中没有有效的轮次，方法直接返回
            claimed_turn, payload, user_id = claimed

            # 2 调用ai
            run_result,error = await self._call_ai_service(payload, user_id) # 调用ai服务

            # 3 处理发件箱(结算修改关联数据)
            await chat_service.finish_turn(claimed_turn,run_result,error) # 结算轮次

            return True

    # 调用aiservice
    async def _call_ai_service(self, payload, user_id):
        # print("_call_ai_service,远程调用智能体，传入参数，获得ai反馈信息...")
        # 远程调用agent智能体服务：access_token(用户身份)，internal_token(服务器身份)
        user_token = encode_token(CurrentUser(user_id=user_id))
        internal_service_token = self._settings.internal_service_token

        # token一定放到header中
        headers = {
            "Authorization": f"Bearer {user_token}",
            "X-Internal-Service-Token": internal_service_token,
        }

        # 设置请求超时
        timeout = httpx.Timeout(self._settings.ai_timeout_seconds,connect=5)

        try:
            async with httpx.AsyncClient(timeout=timeout,trust_env=False) as client:
                response = await client.post(
                    f"{self._settings.ai_service_url}/internal/v1/agent/runs",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status() # 如果有异常，则抛出
                return response.json(), None
        except Exception as e:
            print(f"_call_ai_service，远程调用失败..:{e}")
            return None,e

aiworker = AIWorker()
if __name__ == '__main__':
    run_async(aiworker.start())
