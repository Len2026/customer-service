from fastapi import APIRouter

from cs.app.dependencies import ChatServiceDep, UserDep
from cs.app.schemas import ChatMessageRequest

router = APIRouter(prefix="/api/v1",tags=["聊天api"])

@router.get("/chat/messages")
async def process_chat_messages(payload: ChatMessageRequest,
                                service:ChatServiceDep,
                                user_info:UserDep
                                ):
    # 聊天消息对接口过程
    print("调用聊天消息接口...")
    return None