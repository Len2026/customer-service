import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, status
from cs.app.services.auth import decode_token
from cs.infrastructure.redis import redis_client

router = APIRouter()

@router.websocket("/api/v1/realtime")
async def realtime_endpoint(websocket: WebSocket):
    await websocket.accept() # 将http升级为ws

    # 1 处理前端的第一条数据，处理用户token
    try:
        auth_info:dict[str,Any] = await websocket.receive_json() # 前端发送令牌
        current_user_token = auth_info['token'] # 取出用户令牌
    except Exception as e:
        print("用户令牌接收失败...")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION,reason="未获得有效的用户信息")
        return

    # 2 获得用户信息
    current_user = decode_token(current_user_token)

    # 3 确定订阅频道
    target = current_user.user_id if current_user.role == "user" else "staff"

    # 4 订阅频道
    async with redis_client.pubsub() as pubsub:
        # 订阅
        await pubsub.subscribe(target)

        # 通知前端
        await websocket.send_json({"event_type":"connected"})

        # 启动通讯任务
        async def forward_event():
            # 给前端推消息
            async for message in pubsub.listen():
                if message["type"] == "message":
                    event_data = message["data"]
                    await websocket.send_text(event_data)

        # 监控通讯状态
        async def disconnected():
            # 监控前端是否关闭
            while True:
                await websocket.receive_text()

        # 开始两个任务
        tasks = [
            asyncio.create_task(forward_event()),
            asyncio.create_task(disconnected())
        ]

        # 等待运行任务结果
        _,pending = await asyncio.wait(tasks,return_when = asyncio.FIRST_COMPLETED) # 两个任务只要有一个结束，则结束waiting阻塞状态

        # 结束剩余的任务
        for task in pending:
            task.cancel()

        # 等待运行数据结果
        await asyncio.gather(*tasks,return_exceptions=True)


