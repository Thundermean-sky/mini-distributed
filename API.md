# 概述
后端使用FastAPI，提供REST API + WebSocket。所有接口返回JSON，错误用HTTP状态码。WebSocket用于实时推送。基URL：/api。
# REST API 接口
## POST /api/workers

描述：新增单个Worker。
```
{
  "worker_id": "string (可选，后端生成)",
  "total_cpu": "number",
  "total_gpu": "number"
}
```
返回
```{
  "success": true,
  "worker_id": "string"
}
```
错误：400 Bad Request（参数无效）。

## POST /api/tasks

描述：批量新增任务。
```
[
  {
    "task_name": "string (可选，后端生成)",
    "command": "string",
    "cpu_required": "number",
    "gpu_required": "number"
  }
]
```
返回
```
{
  "success": true,
  "task_ids": ["string", "..."]
}
```
错误：400 Bad Request。

## GET /api/tasks/pending

描述：获取待执行任务列表。
参数：无。
返回
```
[
  {
    "task_id": "string",
    "task_name": "string",
    "cpu_required": "number",
    "gpu_required": "number",
    "status": "Pending"
  }
]
```

## GET /api/workers

描述：获取所有Worker信息。
参数：无。
返回
```
[
  {
    "worker_id": "string",
    "status": "online|offline",
    "total_cpu": "number",
    "used_cpu": "number",
    "total_gpu": "number",
    "used_gpu": "number",
    "tasks": [
      {
        "task_id": "string",
        "task_name": "string",
        "cpu_used": "number",
        "gpu_used": "number",
        "status": "Running|Success|Failed"
      }
    ]
  }
]
```
## GET /api/tasks/{task_id}

描述：获取单个任务详情。
路径参数：task_id (string)。

返回
```
{
  "task_id": "string",
  "task_name": "string",
  "command": "string",
  "cpu_required": "number",
  "gpu_required": "number",
  "status": "Pending|Running|Success|Failed",
  "assigned_worker": "string|null",
  "submitted_at": "string (ISO)",
  "started_at": "string|null",
  "finished_at": "string|null"
}
```
错误：404 Not Found。

## GET /api/tasks/{task_id}/logs

描述：获取任务历史日志（初始抽屉加载）。
路径参数：task_id (string)。
返回
```
[
  {
    "timestamp": "string",
    "content": "string"
  }
]
```
错误：404 Not Found。