import { defineStore } from 'pinia'
import type {
  WorkerInfo,
  PendingTask,
  ClusterOverview,
  TaskDetail,
  LogLine,
} from '@/api'

type TaskLogMessage = {
  task_id: string
  timestamp: string
  content: string
}

let socket: WebSocket | null = null
let reconnectTimer: number | null = null
let retryCount = 0
const maxRetries = 10

function buildWsUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws`
}

export const useClusterStore = defineStore('cluster', {
  state: () => ({
    wsConnected: false,
    workers: [] as WorkerInfo[],
    pendingTasks: [] as PendingTask[],
    overview: null as ClusterOverview | null,
    taskLogs: {} as Record<string, LogLine[]>,
  }),
  actions: {
    ensureConnected() {
      if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        return
      }
      this.connect()
    },

    connect() {
      if (socket) {
        try {
          socket.close()
        } catch {
          // ignore
        }
        socket = null
      }

      const url = buildWsUrl()
      const ws = new WebSocket(url)
      socket = ws

      ws.onopen = () => {
        this.wsConnected = true
        retryCount = 0
      }

      ws.onclose = () => {
        this.wsConnected = false
        socket = null
        this.scheduleReconnect()
      }

      ws.onerror = () => {
        this.wsConnected = false
        try {
          ws.close()
        } catch {
          // ignore
        }
      }

      ws.onmessage = (event: MessageEvent) => {
        try {
          const msg = JSON.parse(event.data) as {
            type: string
            data: unknown
          }
          this.handleMessage(msg.type, msg.data)
        } catch {
          // 忽略无法解析的消息
        }
      }
    },

    scheduleReconnect() {
      if (retryCount >= maxRetries) {
        return
      }
      const delays = [1000, 3000, 5000, 5000, 5000]
      const delay = delays[Math.min(retryCount, delays.length - 1)]
      retryCount += 1

      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer)
      }
      reconnectTimer = window.setTimeout(() => {
        this.connect()
      }, delay)
    },

    handleMessage(type: string, data: unknown) {
      if (type === 'worker_update') {
        this.handleWorkerUpdate(data)
      } else if (type === 'pending_tasks_update') {
        this.handlePendingUpdate(data)
      } else if (type === 'task_log') {
        this.handleTaskLog(data)
      } else if (type === 'cluster_overview') {
        this.handleClusterOverview(data)
      }
    },

    handleWorkerUpdate(data: unknown) {
      if (Array.isArray(data)) {
        this.workers = data as WorkerInfo[]
        return
      }
      const w = data as Partial<WorkerInfo> | null
      if (!w || !w.worker_id) return
      const idx = this.workers.findIndex((item) => item.worker_id === w.worker_id)
      if (idx >= 0) {
        this.workers[idx] = w as WorkerInfo
      } else {
        this.workers.push(w as WorkerInfo)
      }
    },

    handlePendingUpdate(data: unknown) {
      if (!Array.isArray(data)) return
      this.pendingTasks = data as PendingTask[]
    },

    handleTaskLog(data: unknown) {
      const payload = data as TaskLogMessage
      if (!payload || !payload.task_id) return
      const arr = this.taskLogs[payload.task_id] || []
      arr.push({
        timestamp: payload.timestamp,
        content: payload.content,
      })
      this.taskLogs[payload.task_id] = arr
    },

    handleClusterOverview(data: unknown) {
      this.overview = data as ClusterOverview
    },
  },
})

