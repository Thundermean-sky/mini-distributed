import uuid
from datetime import datetime
from typing import List

from backend.database import get_redis, task_key, logs_key, hgetall_json, hset_json
from backend.models import NewTask
from backend.ws_manager import manager   # 第三阶段创建

redis = get_redis()


async def create_tasks(tasks: List[NewTask]) -> List[str]:
    task_ids = []
    for t in tasks:
        task_id = str(uuid.uuid4())[:8]
        now = datetime.utcnow().isoformat()

        task_data = {
            "task_name": t.task_name or f"任务-{task_id}",
            "command": t.command,
            "cpu_required": str(t.cpu_required),
            "gpu_required": str(t.gpu_required),
            "status": "Pending",
            "assigned_worker": "",
            "submitted_at": now,
            "started_at": "",
            "finished_at": ""
        }
        redis.hset(task_key(task_id), mapping=task_data)

        redis.rpush("pending_tasks", task_id)
        task_ids.append(task_id)

    await manager.broadcast("pending_tasks_update", await get_pending_tasks())
    return task_ids


async def get_pending_tasks() -> List[dict]:
    task_ids = redis.lrange("pending_tasks", 0, -1)
    result = []
    for tid in task_ids:
        data = hgetall_json(task_key(tid))
        if data and data.get("status") == "Pending":
            result.append({
                "task_id": tid,
                "task_name": data["task_name"],
                "cpu_required": int(data["cpu_required"]),
                "gpu_required": int(data["gpu_required"]),
                "status": "Pending",
                "submitted_at": data["submitted_at"]
            })
    return result


def _log_timestamp() -> str:
    """统一日志时间格式：年-月-日 时:分:秒"""
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


async def append_log(task_id: str, content: str):
    """追加一条模拟日志"""
    ts = _log_timestamp()
    log_line = f"{ts}  {content}"
    redis.rpush(logs_key(task_id), log_line)

    await manager.broadcast("task_log", {
        "task_id": task_id,
        "timestamp": ts,
        "content": content,
    })