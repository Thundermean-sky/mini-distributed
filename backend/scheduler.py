import json
from datetime import datetime

from backend.database import get_redis, worker_key, task_key, hgetall_json
from backend.task_manager import get_pending_tasks
from backend.worker_manager import get_worker_info
from backend.ws_manager import manager
from backend.simulator import start_simulation

redis = get_redis()


async def try_schedule():
    """尝试调度Pending任务（First Fit Decreasing）"""
    pending_ids = redis.lrange("pending_tasks", 0, -1)
    if not pending_ids:
        return

    # 按资源需求降序排序
    sorted_tasks = []
    for tid in pending_ids:
        t = hgetall_json(task_key(tid))
        if t and t.get("status") == "Pending":
            score = int(t["cpu_required"]) * 10 + int(t["gpu_required"])
            sorted_tasks.append((score, tid, t))

    sorted_tasks.sort(reverse=True)

    for _, task_id, task_data in sorted_tasks:
        allocated = False
        for wkey in redis.scan_iter(match="worker:*"):
            w = hgetall_json(wkey)
            worker_id = wkey.split(":", 1)[1]

            if w.get("status") != "online":
                continue

            if (int(w.get("used_cpu", 0)) + int(task_data["cpu_required"]) <= int(w["total_cpu"]) and
                int(w.get("used_gpu", 0)) + int(task_data["gpu_required"]) <= int(w["total_gpu"])):

                # 分配成功
                new_used_cpu = int(w.get("used_cpu", 0)) + int(task_data["cpu_required"])
                new_used_gpu = int(w.get("used_gpu", 0)) + int(task_data["gpu_required"])

                raw_tasks = w.get("tasks", "[]")
                tasks_list = raw_tasks if isinstance(raw_tasks, list) else json.loads(raw_tasks)
                tasks_list.append(task_id)

                redis.hset(wkey, mapping={
                    "used_cpu": str(new_used_cpu),
                    "used_gpu": str(new_used_gpu),
                    "tasks": json.dumps(tasks_list)
                })

                now = datetime.utcnow().isoformat()
                redis.hset(task_key(task_id), mapping={
                    "status": "Running",
                    "assigned_worker": worker_id,
                    "started_at": now
                })

                redis.lrem("pending_tasks", 0, task_id)

                await manager.broadcast("task_status", {"task_id": task_id, "status": "Running", "assigned_worker": worker_id})
                await manager.broadcast("pending_tasks_update", await get_pending_tasks())
                await manager.broadcast("worker_update", (await get_worker_info(worker_id)).dict())
                await start_simulation(task_id)

                allocated = True
                break

        if not allocated:
            # 暂时无法分配，继续Pending
            pass