from typing import Any

from fastapi import APIRouter

from cs.app.dependencies import ChatServiceDep, UserDep
from cs.app.schemas import ChatMessageRequest

router = APIRouter(prefix="/api/v1", tags=["聊天api"])


@router.post("/chat/messages")
async def process_chat_messages(payload: ChatMessageRequest,
                                service: ChatServiceDep,
                                user_info: UserDep
                                ):
    # 聊天消息对接口过程
    print("调用聊天消息接口...")
    await service.process_chat_message(payload, user_info.user_id)


@router.get("/chat/history")
async def get_chat_history(
        service: ChatServiceDep,
        user_info: UserDep,
) -> dict[str, Any]:
    chat_history = await service.get_chat_history(user_info.user_id)
    return chat_history
