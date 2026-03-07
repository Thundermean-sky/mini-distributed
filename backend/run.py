import uvicorn
from backend.config import settings

if __name__ == "__main__":
    print("🚀 轻量级分布式任务调度系统 Demo 启动中...")
    print(f"访问地址 → http://127.0.0.1:{settings.PORT}")
    print(f"Swagger 文档 → http://127.0.0.1:{settings.PORT}/docs")
    print(f"WebSocket → ws://127.0.0.1:{settings.PORT}/ws")
    print("=" * 70)

    uvicorn.run(
        app="backend.main:app",           # ← 关键在这里
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )