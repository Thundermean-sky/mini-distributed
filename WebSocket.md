# 连接方式

连接地址：ws://localhost:8000/ws（生产环境可换为 wss）
连接流程：
前端页面加载后立即建立 WebSocket 连接。
连接成功后，后端立即推送一次当前全量数据（worker_update 全量 + pending_tasks_update）。
心跳：前端每30秒发送 ping，后端回复 pong（防止断线）。
断线重连：前端实现自动重连机制（间隔1s、3s、5s递增，最多重试10次）。


# 消息格式规范
所有推送消息均为以下格式：
```
{
  "type": "string",           // 消息类型，必填
  "timestamp": "string",      // ISO 8601 时间戳，如 "2025-03-06T12:05:23.456Z"
  "data": {}                  // 具体数据，根据 type 不同而不同
}
```

## 具体消息类型定义
## worker_update
Worker信息更新（新增、资源变化、离线）,任意Worker发生变化时（新增、心跳、资源分配、任务完成）,更新对应Worker Card（进度条、任务列表、状态颜色）

## pending_tasks_update
待执行任务列表变化,有任务进入/离开Pending队列时,TaskInfo[]（完整待执行任务数组）,刷新最上方“待执行任务列表”Card（为空则隐藏Card）

## task_status
单个任务状态变更,任务从Pending→Running、Running→Success/Failed
## task_log
实时日志行（模拟执行核心）,Running任务每隔500~1200ms生成一行日志时,在右侧抽屉日志区追加一行，并自动滚动到底部

## cluster_overview
集群全局概览（可选增强）,每5秒或任意资源/任务总数变化时,可用于Header或全局统计卡片

# 各消息的 data 详细结构定义

## WorkerInfo
```
{
  "worker_id": "worker_1",
  "status": "online | offline",
  "total_cpu": 4,
  "used_cpu": 2,
  "total_gpu": 8,
  "used_gpu": 3,
  "last_heartbeat": "2025-03-06T12:05:23Z",
  "tasks": [
    {
      "task_id": "taskC",
      "task_name": "任务C",
      "cpu_used": 1,
      "gpu_used": 2,
      "status": "Running"
    },
    {
      "task_id": "taskD",
      "task_name": "任务D",
      "cpu_used": 1,
      "gpu_used": 1,
      "status": "Success"
    }
  ]
}
```

## TaskInfo

```
{
  "task_id": "taskA",
  "task_name": "任务A",
  "cpu_required": 2,
  "gpu_required": 3,
  "status": "Pending",
  "submitted_at": "2025-03-06T11:50:00Z"
}
```
## task_log
```
{
  "type": "task_log",
  "timestamp": "2025-03-06T12:05:23.789Z",
  "data": {
    "task_id": "taskA",
    "timestamp": "2025-03-06 12:05:23",
    "content": "Processing data chunk 7/18... GPU utilization: 62%"
  }
}
```

# 模拟执行日志推送机制

任务进入Running状态后，后端立即开始模拟执行。
每隔随机500~1200毫秒推送一条task_log。
日志内容随机但真实感强（类似Linux终端输出）。
失败场景：日志突然停止（无“Task completed successfully”），符合真实程序崩溃效果。
所有日志永久保存在Redis中，失败任务的日志也可完整查看。

# WebSocket 错误与状态处理

后端推送用于异常通知。
前端需显示连接状态（Header右侧绿色/红色）。
断线后自动重连，重连成功后后端会重新下发全量worker_update和pending_tasks_update。