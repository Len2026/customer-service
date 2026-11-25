from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from cs.app.schemas import CurrentUser
from cs.app.services.admin import HandoffService
from cs.app.services.auth import require_authorized_user
from cs.app.services.chat import ChatService
from cs.infrastructure.db import get_async_session

# session注入
sessionDep = Annotated[AsyncSession, Depends(get_async_session)]

# chat服务注入
def get_chat_service(session:sessionDep):
    return ChatService(session)
# chatService:ChatServiceDep
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]

# handoff服务注入
def get_handoff_service(session:sessionDep):
    return HandoffService(session)
# chatService:ChatServiceDep
HandoffServiceDep = Annotated[HandoffService, Depends(get_handoff_service)]

# auth服务注入
def require_user_info(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    return require_authorized_user(authorization, "user")
# user_info:UserDep
UserDep = Annotated[CurrentUser, Depends(require_user_info)]

# auth服务注入
def require_staff_info(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    return require_authorized_user(authorization, "staff")
# user_info:UserDep
StaffDep = Annotated[CurrentUser, Depends(require_staff_info)]

# auth服务注入
def require_admin_info(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    return require_authorized_user(authorization, "admin")
# user_info:UserDep
AdminDep = Annotated[CurrentUser, Depends(require_admin_info)]