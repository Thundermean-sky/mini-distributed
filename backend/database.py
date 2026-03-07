import fakeredis
import redis
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from .config import settings

class RedisClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            if settings.DEMO_MODE:
                print("🚀 使用 fakeredis 纯内存模式（无需安装Redis）")
                cls._instance = fakeredis.FakeRedis(
                    version=7,
                    decode_responses=True,
                    socket_connect_timeout=2
                )
            else:
                cls._instance = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    decode_responses=True,
                    socket_connect_timeout=2
                )
        return cls._instance

redis_client = RedisClient()

def get_redis():
    return redis_client

# ==================== 通用操作 ====================
def set_json(key: str, data: Any, expire: int = None):
    value = json.dumps(data, default=str)
    if expire:
        redis_client.setex(key, expire, value)
    else:
        redis_client.set(key, value)

def get_json(key: str) -> Optional[Dict]:
    data = redis_client.get(key)
    return json.loads(data) if data else None

def hgetall_json(key: str) -> Dict:
    """读取Hash并自动尝试解析JSON字段"""
    data = redis_client.hgetall(key)
    for k, v in data.items():
        try:
            if v.startswith(('{', '[')):
                data[k] = json.loads(v)
        except:
            pass
    return data

def hset_json(key: str, field: str, value: Any):
    redis_client.hset(key, field, json.dumps(value, default=str) if isinstance(value, (dict, list)) else str(value))

# ==================== Key 定义 ====================
def worker_key(worker_id: str) -> str:
    return f"worker:{worker_id}"

def task_key(task_id: str) -> str:
    return f"task:{task_id}"

def logs_key(task_id: str) -> str:
    return f"logs:{task_id}"

def simulating_key(task_id: str) -> str:
    return f"simulating:{task_id}"