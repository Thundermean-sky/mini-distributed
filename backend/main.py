from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import uvicorn
from datetime import datetime

from backend.config import settings
from backend.api.routes import router
from backend.ws_manager import manager, _make_json_serializable
from backend.worker_manager import check_all_heartbeats, demo_heartbeat_loop
from backend.simulator import simulator_loop
from backend.scheduler import try_schedule

app = FastAPI(title="轻量级分布式任务调度系统 Demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # 连接成功立即推送全量数据
        from .worker_manager import get_all_workers
        from .task_manager import get_pending_tasks

        await websocket.send_json({
            "type": "worker_update",
            "timestamp": datetime.utcnow().isoformat(),
            "data": _make_json_serializable([w.dict() for w in await get_all_workers()]),
        })
        await websocket.send_json({
            "type": "pending_tasks_update",
            "timestamp": datetime.utcnow().isoformat(),
            "data": await get_pending_tasks()
        })

        while True:
            await websocket.receive_text()  # 保持连接
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(check_all_heartbeats())
    if settings.DEMO_MODE:
        asyncio.create_task(demo_heartbeat_loop())
    asyncio.create_task(simulator_loop())
    # 启动后立即尝试一次调度
    asyncio.create_task(try_schedule())
    print(f"🎉 Demo后端启动成功！")
    print(f"   → http://localhost:{settings.PORT}")
    print(f"   → Swagger: http://localhost:{settings.PORT}/docs")


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)