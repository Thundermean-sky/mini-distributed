from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime

from ..models import NewWorker, NewTask, WorkerInfo, PendingTask, ClusterOverview, TaskInfo, LogLine
from ..worker_manager import register_worker, get_all_workers, schedule_worker_offline, bring_worker_online
from ..task_manager import create_tasks, get_pending_tasks
from ..scheduler import try_schedule
from ..database import get_redis, task_key, logs_key, hgetall_json

router = APIRouter()


# ====================== 总览接口 ======================

@router.get("/overview", response_model=ClusterOverview)
async def get_overview():
    """集群总览：Worker 数量、资源占用、运行中/待执行任务数"""
    workers = await get_all_workers()
    pending = await get_pending_tasks()
    total_cpu = sum(w.total_cpu for w in workers)
    used_cpu = sum(w.used_cpu for w in workers)
    total_gpu = sum(w.total_gpu for w in workers)
    used_gpu = sum(w.used_gpu for w in workers)
    running_tasks = sum(sum(1 for t in w.tasks if t.status == "Running") for w in workers)
    return ClusterOverview(
        total_workers=len(workers),
        online_workers=sum(1 for w in workers if w.status == "online"),
        total_cpu=total_cpu,
        used_cpu=used_cpu,
        total_gpu=total_gpu,
        used_gpu=used_gpu,
        running_tasks=running_tasks,
        pending_tasks=len(pending),
    )


# ====================== Worker 接口 ======================

@router.post("/workers", response_model=WorkerInfo)
async def add_worker(new_worker: NewWorker):
    """新增一个Worker节点"""
    worker_id = new_worker.worker_id or f"worker-{len(await get_all_workers()) + 1}"

    worker = await register_worker(
        worker_id=worker_id,
        total_cpu=new_worker.total_cpu,
        total_gpu=new_worker.total_gpu
    )
    # 尝试调度可能正在等待的任务
    await try_schedule()
    return worker


@router.get("/workers", response_model=List[WorkerInfo])
async def list_workers():
    """获取所有Worker信息"""
    return await get_all_workers()


@router.post("/workers/{worker_id}/schedule-offline")
async def schedule_offline(worker_id: str):
    """安排该 Worker 在 5 秒后宕机（用于测试离线与 Running 任务回迁待执行列表）"""
    ok = schedule_worker_offline(worker_id, delay_seconds=5)
    if not ok:
        raise HTTPException(status_code=404, detail="Worker not found")
    return {"message": f"Worker {worker_id} 将在 5 秒后宕机"}


@router.post("/workers/{worker_id}/start", response_model=WorkerInfo)
async def start_worker(worker_id: str):
    """将已离线的 Worker 重新开机为 online，并立即尝试将待执行任务分配过去"""
    ok = bring_worker_online(worker_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Worker not found")
    await try_schedule()
    workers_list = await get_all_workers()
    w = next((x for x in workers_list if x.worker_id == worker_id), None)
    if w is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    from ..ws_manager import manager
    await manager.broadcast("worker_update", w.dict())
    return w


# ====================== Task 接口 ======================

@router.post("/tasks")
async def add_tasks(tasks: List[NewTask]):
    """批量新增任务"""
    task_ids = await create_tasks(tasks)
    # 立即尝试调度
    await try_schedule()
    return {"success": True, "task_ids": task_ids}


@router.get("/tasks/pending", response_model=List[PendingTask])
async def list_pending_tasks():
    """获取待执行任务列表"""
    return await get_pending_tasks()


@router.get("/tasks/{task_id}", response_model=TaskInfo)
async def get_task_detail(task_id: str):
    """获取单个任务详情"""
    data = hgetall_json(task_key(task_id))
    if not data:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskInfo(
        task_id=task_id,
        task_name=data.get("task_name", task_id),
        command=data.get("command", ""),
        cpu_required=int(data.get("cpu_required", 0)),
        gpu_required=int(data.get("gpu_required", 0)),
        status=data.get("status", "Pending"),
        assigned_worker=data.get("assigned_worker") or None,
        submitted_at=datetime.fromisoformat(data["submitted_at"]),
        started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
        finished_at=datetime.fromisoformat(data["finished_at"]) if data.get("finished_at") else None,
    )


@router.get("/tasks/{task_id}/logs", response_model=List[LogLine])
async def get_task_logs(task_id: str):
    """获取任务历史日志"""
    redis = get_redis()
    raw_lines = redis.lrange(logs_key(task_id), 0, -1)

    if not raw_lines and not hgetall_json(task_key(task_id)):
        raise HTTPException(status_code=404, detail="Task not found")

    logs: List[LogLine] = []
    for line in raw_lines:
        if "  " in line:
            ts, content = line.split("  ", 1)
        else:
            ts, content = "", line
        logs.append(LogLine(timestamp=ts, content=content))
    return logs


# ====================== 辅助接口（可选） ======================

@router.get("/reset")
async def reset_system():
    """一键清空所有数据（Demo演示用）"""
    from ..database import get_redis
    redis = get_redis()
    for key in redis.scan_iter(match="*"):
        redis.delete(key)
    return {"message": "系统已重置"}