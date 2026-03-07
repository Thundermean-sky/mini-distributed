import asyncio
import random
from datetime import datetime

from backend.database import get_redis, simulating_key, task_key, hgetall_json
from backend.task_manager import append_log
from backend.ws_manager import manager
from backend.config import settings

redis = get_redis()

# 每个任务执行 20–30 秒
TASK_DURATION_MIN = 20
TASK_DURATION_MAX = 30
# 日志输出间隔（秒）
LOG_INTERVAL = 1.0


async def start_simulation(task_id: str):
    """任务进入 Running 后调用：按 20–30 秒时长模拟执行并输出日志"""
    duration_seconds = random.randint(TASK_DURATION_MIN, TASK_DURATION_MAX)
    now = datetime.utcnow()

    redis.hset(simulating_key(task_id), mapping={
        "is_simulating": "true",
        "started_at": now.isoformat(),
        "duration_seconds": str(duration_seconds),
        "last_log_at": now.isoformat(),
    })

    task = hgetall_json(task_key(task_id))
    await append_log(task_id, f"🚀 开始模拟执行: {task.get('command', 'unknown')}")


async def simulator_loop():
    while True:
        await asyncio.sleep(settings.SIMULATOR_TICK_INTERVAL)
        now = datetime.utcnow()

        for key in list(redis.scan_iter(match="simulating:*")):
            task_id = key.split(":", 1)[1]
            try:
                data = hgetall_json(key)
                if data.get("is_simulating") != "true":
                    continue

                started_at = datetime.fromisoformat(data.get("started_at", now.isoformat()))
                duration_seconds = int(data.get("duration_seconds", 25))
                last_log_at = datetime.fromisoformat(data.get("last_log_at", now.isoformat()))

                elapsed = (now - started_at).total_seconds()
                if elapsed >= duration_seconds:
                    await finish_task(task_id)
                    continue

                # 约每 LOG_INTERVAL 秒输出一行日志
                if (now - last_log_at).total_seconds() >= LOG_INTERVAL:
                    content = random.choice([
                        "Processing chunk...", "GPU 67%", "CPU 42%",
                        "Running inference...", "Writing output..."
                    ])
                    await append_log(task_id, content)
                    redis.hset(key, "last_log_at", now.isoformat())
            except Exception as e:
                print(f"⚠️ simulator_loop 处理任务 {task_id} 时异常: {e}")


async def finish_task(task_id: str):
    """70% 成功，30% 失败；完成后可查看完整执行日志"""
    is_success = random.random() < 0.7
    status = "Success" if is_success else "Failed"
    now = datetime.utcnow().isoformat()

    redis.hset(task_key(task_id), mapping={
        "status": status,
        "finished_at": now
    })
    redis.delete(simulating_key(task_id))

    if is_success:
        await append_log(task_id, "✅ Task completed successfully.")
    else:
        await append_log(task_id, "❌ Execution failed.")

    await manager.broadcast("task_status", {
        "task_id": task_id,
        "status": status,
        "assigned_worker": None
    })

    # 释放资源（只在这里释放一次）
    task_data = hgetall_json(task_key(task_id))
    worker_id = task_data.get("assigned_worker")
    if worker_id:
        from .worker_manager import release_worker_resources   # 延迟导入避免循环
        await release_worker_resources(worker_id, task_id)

    from .scheduler import try_schedule
    await try_schedule()