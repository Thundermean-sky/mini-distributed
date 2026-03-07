from datetime import datetime, timedelta
import asyncio
import json
from typing import List, Optional

from backend.database import get_redis, worker_key, task_key, simulating_key, hgetall_json, hset_json
from backend.models import WorkerInfo
from backend.config import settings
from backend.ws_manager import manager

redis = get_redis()


async def register_worker(worker_id: str, total_cpu: int, total_gpu: int) -> WorkerInfo:
    """注册新Worker"""
    key = worker_key(worker_id)
    now = datetime.utcnow().isoformat()

    data = {
        "total_cpu": str(total_cpu),
        "total_gpu": str(total_gpu),
        "used_cpu": "0",           # 初始无Running任务
        "used_gpu": "0",
        "status": "online",
        "last_heartbeat": now,
        "tasks": json.dumps([])    # 存储所有任务ID（含历史）
    }
    redis.hset(key, mapping=data)

    worker = await get_worker_info(worker_id)
    await manager.broadcast("worker_update", worker.dict())
    return worker


async def heartbeat(worker_id: str):
    """接收心跳"""
    key = worker_key(worker_id)
    if redis.exists(key):
        redis.hset(key, mapping={
            "last_heartbeat": datetime.utcnow().isoformat(),
            "status": "online"
        })


async def demo_heartbeat_loop():
    """Demo 模式：定期为所有在线 Worker 模拟心跳，避免无真实进程时被判离线"""
    while True:
        await asyncio.sleep(2)
        if not getattr(settings, "DEMO_MODE", True):
            continue
        for key in list(redis.scan_iter(match="worker:*")):
            worker_id = key.split(":", 1)[1]
            data = hgetall_json(key)
            if data.get("status") == "online":
                await heartbeat(worker_id)


def schedule_worker_offline(worker_id: str, delay_seconds: int = 5) -> bool:
    """安排 Worker 在 delay_seconds 秒后宕机（用于测试离线与任务回迁）"""
    key = worker_key(worker_id)
    if not redis.exists(key):
        return False
    offline_at = (datetime.utcnow() + timedelta(seconds=delay_seconds)).isoformat()
    redis.hset(key, "scheduled_offline_at", offline_at)
    return True


def bring_worker_online(worker_id: str) -> bool:
    """将已离线的 Worker 重新开机为 online"""
    key = worker_key(worker_id)
    if not redis.exists(key):
        return False
    data = hgetall_json(key)
    if data.get("status") != "offline":
        return True
    now = datetime.utcnow().isoformat()
    redis.hset(key, mapping={
        "status": "online",
        "last_heartbeat": now,
        "scheduled_offline_at": "",
    })
    return True


async def check_all_heartbeats():
    """每隔一段时间检查所有Worker心跳 + 计划宕机 + 处理离线逻辑"""
    while True:
        await asyncio.sleep(settings.HEARTBEAT_TIMEOUT // 3)

        now = datetime.utcnow()
        for key in list(redis.scan_iter(match="worker:*")):
            worker_id = key.split(":", 1)[1]
            data = hgetall_json(key)

            if data.get("status") == "offline":
                continue

            should_go_offline = False
            scheduled_at = data.get("scheduled_offline_at")
            if scheduled_at:
                try:
                    at = datetime.fromisoformat(scheduled_at)
                    if now >= at:
                        redis.hset(key, "scheduled_offline_at", "")
                        should_go_offline = True
                    else:
                        continue
                except (TypeError, ValueError):
                    redis.hset(key, "scheduled_offline_at", "")

            if not should_go_offline:
                last_hb = datetime.fromisoformat(data.get("last_heartbeat", now.isoformat()))
                if now - last_hb <= timedelta(seconds=settings.HEARTBEAT_TIMEOUT):
                    continue  # 仍然在线

            print(f"⚠️ Worker {worker_id} 离线，开始处理...")

            raw_tasks = data.get("tasks", "[]")
            current_tasks = raw_tasks if isinstance(raw_tasks, list) else json.loads(raw_tasks)
            running_to_migrate = []
            historical_tasks = []
            released_cpu = 0
            released_gpu = 0

            # 1. 分离 Running 和历史任务
            for tid in current_tasks:
                tdata = hgetall_json(task_key(tid))
                if not tdata:
                    continue
                if tdata.get("status") == "Running":
                    running_to_migrate.append(tid)
                    released_cpu += int(tdata.get("cpu_required", 0))
                    released_gpu += int(tdata.get("gpu_required", 0))
                else:
                    historical_tasks.append(tid)   # Success/Failed 保留

            # 2. 更新Worker：资源归零，只保留历史任务
            redis.hset(key, mapping={
                "status": "offline",
                "used_cpu": "0",                    # 重点：归零
                "used_gpu": "0",                    # 重点：归零
                "tasks": json.dumps(historical_tasks)
            })

            # 3. 把Running任务迁移回Pending（并停止模拟执行，避免日志继续输出）
            from backend.task_manager import get_pending_tasks
            for tid in running_to_migrate:
                redis.delete(simulating_key(tid))
                redis.hset(task_key(tid), mapping={
                    "status": "Pending",
                    "assigned_worker": "",
                    "started_at": ""
                })
                redis.rpush("pending_tasks", tid)
                await manager.broadcast("task_status", {
                    "task_id": tid,
                    "status": "Pending",
                    "assigned_worker": None
                })
            pending = await get_pending_tasks()
            await manager.broadcast("pending_tasks_update", pending)

            # 4. 通知前端
            worker_info = await get_worker_info(worker_id)
            await manager.broadcast("worker_update", worker_info.dict())

            # 5. 立即尝试把刚迁回待执行的任务调度到其他在线 Worker
            if running_to_migrate:
                from backend.scheduler import try_schedule
                await try_schedule()


async def release_worker_resources(worker_id: str, task_id: str):
    """任务完成（成功/失败）时释放该任务占用的 CPU/GPU，并广播 worker_update"""
    key = worker_key(worker_id)
    if not redis.exists(key):
        return
    task_data = hgetall_json(task_key(task_id))
    if not task_data:
        return
    cpu_required = int(task_data.get("cpu_required", 0))
    gpu_required = int(task_data.get("gpu_required", 0))

    data = hgetall_json(key)
    used_cpu = max(0, int(data.get("used_cpu", 0)) - cpu_required)
    used_gpu = max(0, int(data.get("used_gpu", 0)) - gpu_required)
    redis.hset(key, mapping={
        "used_cpu": str(used_cpu),
        "used_gpu": str(used_gpu),
    })
    worker_info = await get_worker_info(worker_id)
    await manager.broadcast("worker_update", worker_info.dict())


async def get_worker_info(worker_id: str) -> Optional[WorkerInfo]:
    data = hgetall_json(worker_key(worker_id))
    if not data:
        return None

    task_list = []
    raw_tasks = data.get("tasks", "[]")
    task_ids = raw_tasks if isinstance(raw_tasks, list) else json.loads(raw_tasks)
    for tid in task_ids:
        t = hgetall_json(task_key(tid))
        if t:
            task_list.append({
                "task_id": tid,
                "task_name": t.get("task_name", tid),
                "cpu_used": int(t.get("cpu_required", 0)) if t.get("status") == "Running" else 0,
                "gpu_used": int(t.get("gpu_required", 0)) if t.get("status") == "Running" else 0,
                "status": t.get("status", "Unknown")
            })

    return WorkerInfo(
        worker_id=worker_id,
        status=data.get("status", "offline"),
        total_cpu=int(data.get("total_cpu", 0)),
        used_cpu=int(data.get("used_cpu", 0)),      # 只反映Running占用
        total_gpu=int(data.get("total_gpu", 0)),
        used_gpu=int(data.get("used_gpu", 0)),
        last_heartbeat=datetime.fromisoformat(data.get("last_heartbeat", datetime.utcnow().isoformat())),
        tasks=task_list
    )


async def get_all_workers() -> List[WorkerInfo]:
    workers = []
    for key in redis.scan_iter(match="worker:*"):
        wid = key.split(":", 1)[1]
        info = await get_worker_info(wid)
        if info:
            workers.append(info)
    return workers