from cs.app.routers import chat
from fastapi import FastAPI
from cs.app.swagger_security import SwaggerAuth
app = FastAPI

SwaggerAuth(app)

app.include_router(chat.router)

