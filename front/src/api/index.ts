import axios from 'axios'

export const api = axios.create({
  baseURL: '',
  timeout: 10000,
})

export interface WorkerTask {
  task_id: string
  task_name: string
  cpu_used: number
  gpu_used: number
  status: 'Pending' | 'Running' | 'Success' | 'Failed' | string
}

export interface WorkerInfo {
  worker_id: string
  status: 'online' | 'offline'
  total_cpu: number
  used_cpu: number
  total_gpu: number
  used_gpu: number
  last_heartbeat: string
  tasks: WorkerTask[]
}

export interface PendingTask {
  task_id: string
  task_name: string
  cpu_required: number
  gpu_required: number
  status: 'Pending'
  submitted_at: string
}

export interface ClusterOverview {
  total_workers: number
  online_workers: number
  total_cpu: number
  used_cpu: number
  total_gpu: number
  used_gpu: number
  running_tasks: number
  pending_tasks: number
}

export function getOverview() {
  return api.get<ClusterOverview>('/api/overview').then((r) => r.data)
}

export function getWorkers() {
  return api.get<WorkerInfo[]>('/api/workers').then((r) => r.data)
}

export function getPendingTasks() {
  return api.get<PendingTask[]>('/api/tasks/pending').then((r) => r.data)
}

export interface NewWorkerPayload {
  worker_id?: string
  total_cpu: number
  total_gpu: number
}

export interface NewTaskPayload {
  task_name?: string
  command: string
  cpu_required: number
  gpu_required: number
}

export function addWorker(data: NewWorkerPayload) {
  return api.post('/api/workers', data).then((r) => r.data)
}

export function scheduleWorkerOffline(workerId: string) {
  return api.post(`/api/workers/${workerId}/schedule-offline`).then((r) => r.data)
}

export function startWorker(workerId: string) {
  return api.post(`/api/workers/${workerId}/start`).then((r) => r.data)
}

export function addTasks(tasks: NewTaskPayload[]) {
  return api.post('/api/tasks', tasks).then((r) => r.data)
}

export interface TaskDetail {
  task_id: string
  task_name: string
  command: string
  cpu_required: number
  gpu_required: number
  status: 'Pending' | 'Running' | 'Success' | 'Failed'
  assigned_worker: string | null
  submitted_at: string
  started_at: string | null
  finished_at: string | null
}

export interface LogLine {
  timestamp: string
  content: string
}

export function getTaskDetail(taskId: string) {
  return api.get<TaskDetail>(`/api/tasks/${taskId}`).then((r) => r.data)
}

export function getTaskLogs(taskId: string) {
  return api.get<LogLine[]>(`/api/tasks/${taskId}/logs`).then((r) => r.data)
}
