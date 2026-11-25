from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from cs.app.routers import chat, realtime, admin
from cs.app.swagger_security import SwaggerAuth
from cs.common.settings import get_settings

# 接口app
app = FastAPI()
SwaggerAuth(app) # 开启安全模式

# 注册router
app.include_router(chat.router)
app.include_router(realtime.router)
app.include_router(admin.router)
# 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)