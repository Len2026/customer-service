import uvicorn

from cs.common.event_loop import run_async

async def start_uvicorn():
    server = uvicorn.Server(
        config=uvicorn.Config(
            app="cs.app.app.app:app",
            host="0.0.0.0",
            port=8000,
            loop="none",    # 关闭自动的,使用手动
        ),
    )
    await server.start()

if __name__ == "__main__":
    pass