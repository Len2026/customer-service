from typing import Annotated

from fastapi import Depends, Header

from cs.app.schemas import CurrentUser
from cs.app.services.auth import require_authorized_user
from cs.app.services.chat import ChatService


# chat服务注入
def get_chat_service():
    return ChatService()
# chatService:ChatServiceDep
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]

# auth服务注入
def require_user_info(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    return require_authorized_user(authorization, "user")
# user_info:UserDep
UserDep = Annotated[CurrentUser, Depends(require_user_info)]
