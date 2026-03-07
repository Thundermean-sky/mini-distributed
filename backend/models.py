from pydantic import BaseModel, Field
from typing import Literal, List, Optional
from datetime import datetime

StatusType = Literal["Pending", "Running", "Success", "Failed"]
WorkerStatus = Literal["online", "offline"]

class NewWorker(BaseModel):
    worker_id: Optional[str] = None
    total_cpu: int = Field(..., gt=0)
    total_gpu: int = Field(..., gt=0)

class NewTask(BaseModel):
    task_name: Optional[str] = None
    command: str
    cpu_required: int = Field(..., gt=0)
    gpu_required: int = Field(..., gt=0)

class TaskInfo(BaseModel):
    task_id: str
    task_name: str
    command: str
    cpu_required: int
    gpu_required: int
    status: StatusType
    assigned_worker: Optional[str] = None
    submitted_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

class TaskInWorker(BaseModel):
    task_id: str
    task_name: str
    cpu_used: int          # 该任务实际占用的CPU（仅Running时有意义）
    gpu_used: int
    status: StatusType

class WorkerInfo(BaseModel):
    worker_id: str
    status: WorkerStatus
    total_cpu: int
    used_cpu: int          # ← 重点：只代表当前Running任务的总占用
    total_gpu: int
    used_gpu: int          # ← 重点：只代表当前Running任务的总占用
    last_heartbeat: datetime
    tasks: List[TaskInWorker] = Field(default_factory=list)   # 包含历史任务（Success/Failed）

class PendingTask(BaseModel):
    task_id: str
    task_name: str
    cpu_required: int
    gpu_required: int
    status: Literal["Pending"]
    submitted_at: datetime

class LogLine(BaseModel):
    timestamp: str
    content: str

class ClusterOverview(BaseModel):
    total_workers: int
    online_workers: int
    total_cpu: int
    used_cpu: int
    total_gpu: int
    used_gpu: int
    running_tasks: int
    pending_tasks: int