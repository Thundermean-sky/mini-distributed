from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # ==================== Demo 配置 ====================
    DEMO_MODE: bool = True                     # True = 使用 fakeredis 纯内存模式
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # ==================== Redis 配置 ====================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # ==================== 心跳与模拟执行配置 ====================
    HEARTBEAT_TIMEOUT: int = 5                # 秒，超过此时间视为离线
    SIMULATOR_TICK_INTERVAL: float = 0.3       # 模拟器检查间隔（秒）
    LOG_SPEED_MIN: int = 500                   # 每行日志最快间隔 ms
    LOG_SPEED_MAX: int = 1200                  # 每行日志最慢间隔 ms
    LINES_PER_TASK_MIN: int = 15
    LINES_PER_TASK_MAX: int = 30

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()