<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { ElRow, ElCol, ElCard, ElStatistic, ElEmpty, ElIcon, ElDrawer, ElTag } from 'element-plus'

defineOptions({ name: 'OverviewPage' })
import { Cpu, Monitor, List, Clock, Connection, CircleCheck } from '@element-plus/icons-vue'
import { getOverview, getTaskDetail, getTaskLogs, type ClusterOverview, type TaskDetail, type LogLine, type WorkerInfo, type PendingTask } from '@/api'
import { useClusterStore } from '@/stores/cluster'
import Uncompletedlist from '@/components/Uncompletedlist.vue'
import Worker from '@/components/Worker.vue'

const overview = ref<ClusterOverview | null>(null)
const loading = ref(true)
const error = ref('')
let timer: ReturnType<typeof setInterval> | null = null
let chartTimer: ReturnType<typeof setInterval> | null = null

const clusterStore = useClusterStore()
const { workers, pendingTasks, taskLogs } = storeToRefs(clusterStore)

// 每个 Worker 最近 60 秒的 GPU 使用率（0–100），用于折线图
const gpuHistory = ref<Record<string, number[]>>({})
const CHART_LEN = 60
const CHART_WIDTH = 200
const CHART_HEIGHT = 48

const drawerVisible = ref(false)
const drawerLoading = ref(false)
const selectedTask = ref<TaskDetail | null>(null)
const selectedTaskId = ref<string | null>(null)
/** 打开抽屉时从 API 拉取的历史日志（用于与 WebSocket 新日志合并） */
const initialLogs = ref<LogLine[]>([])
/** 打开抽屉时 store 中该任务已有日志条数，仅追加之后的 WS 日志 */
const storeLengthAtOpen = ref(0)
const logContainerRef = ref<HTMLElement | null>(null)

/** 时间显示：年-月-日 时:分:秒 */
function formatDateTime(s: string | null | undefined): string {
  if (s == null || s === '') return '-'
  try {
    const d = new Date(s)
    if (Number.isNaN(d.getTime())) return s
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const h = String(d.getHours()).padStart(2, '0')
    const min = String(d.getMinutes()).padStart(2, '0')
    const sec = String(d.getSeconds()).padStart(2, '0')
    return `${y}-${m}-${day} ${h}:${min}:${sec}`
  } catch {
    return s
  }
}

/** 抽屉内展示的日志 = 初始历史 + 打开后通过 WebSocket 收到的新日志 */
const displayLogs = computed(() => {
  const sid = selectedTaskId.value
  if (!sid) return []
  const ws = taskLogs.value[sid] || []
  const tail = ws.slice(storeLengthAtOpen.value)
  return [...initialLogs.value, ...tail]
})

function scrollToBottomIfAtBottom() {
  nextTick(() => {
    const el = logContainerRef.value
    if (!el) return
    const threshold = 30
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
    if (atBottom) el.scrollTop = el.scrollHeight
  })
}

/** 有数据：来自 overview 或 store 的 workers/pending，新增首个 worker 后立即隐藏空状态 */
const hasData = computed(
  () =>
    (overview.value && (overview.value.total_workers > 0 || overview.value.pending_tasks > 0)) ||
    workers.value.length > 0 ||
    pendingTasks.value.length > 0
)

/** 统计卡片配置（用于统一样式与入场动画） */
const statCols = computed(() => {
  if (!overview.value) return []
  const o = overview.value
  return [
    { key: 'total', title: 'Worker 总数', value: o.total_workers, prefix: Monitor, suffix: '', sub: '', klass: '' },
    { key: 'online', title: '在线 Worker', value: o.online_workers, prefix: Connection, suffix: '', sub: '', klass: 'stat-online' },
    { key: 'cpu', title: 'CPU 占用', value: o.used_cpu, prefix: Cpu, suffix: ` / ${o.total_cpu}`, sub: `${cpuPercent()}% 已用`, klass: '' },
    { key: 'gpu', title: 'GPU 占用', value: o.used_gpu, prefix: Cpu, suffix: ` / ${o.total_gpu}`, sub: `${gpuPercent()}% 已用`, klass: '' },
    { key: 'running', title: '运行中任务', value: o.running_tasks, prefix: List, suffix: '', sub: '', klass: 'stat-running' },
    { key: 'pending', title: '待执行任务', value: o.pending_tasks, prefix: Clock, suffix: '', sub: '', klass: 'stat-pending' },
  ]
})

/** 在线 Worker 排在上方，离线排下方 */
const sortedWorkers = computed(() =>
  [...workers.value].sort((a, b) => {
    if (a.status === 'online' && b.status !== 'online') return -1
    if (a.status !== 'online' && b.status === 'online') return 1
    return 0
  })
)

async function fetchOverview() {
  try {
    error.value = ''
    overview.value = await getOverview()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '获取总览失败'
    overview.value = null
  } finally {
    loading.value = false
  }
}

function cpuPercent() {
  if (!overview.value || overview.value.total_cpu === 0) return 0
  return Math.round((overview.value.used_cpu / overview.value.total_cpu) * 100)
}

function gpuPercent() {
  if (!overview.value || overview.value.total_gpu === 0) return 0
  return Math.round((overview.value.used_gpu / overview.value.total_gpu) * 100)
}

function workerGpuPercent(worker: WorkerInfo) {
  if (!worker.total_gpu) return 0
  return Math.round((worker.used_gpu / worker.total_gpu) * 100)
}

function hasRunningTask(worker: WorkerInfo) {
  return worker.tasks.some((t) => t.status === 'Running')
}

function tickGpuChart() {
  const list = workers.value
  const next: Record<string, number[]> = { ...gpuHistory.value }
  for (const w of list) {
    const arr = next[w.worker_id] || []
    if (w.status !== 'online') {
      next[w.worker_id] = arr
      continue
    }
    let val: number
    if (!hasRunningTask(w)) {
      val = 0
    } else {
      const base = workerGpuPercent(w)
      const delta = (Math.random() - 0.5) * 10
      val = Math.round(Math.min(100, Math.max(0, base + delta)))
    }
    arr.push(val)
    if (arr.length > CHART_LEN) arr.shift()
    next[w.worker_id] = arr
  }
  gpuHistory.value = next
}

function getGpuChartPoints(workerId: string): string {
  const arr = gpuHistory.value[workerId] || []
  if (arr.length === 0) return ''
  const w = CHART_WIDTH
  const h = CHART_HEIGHT
  return arr
    .map((v, i) => {
      const x = (i / Math.max(1, arr.length - 1)) * w
      const y = h - (v / 100) * h
      return `${x},${y}`
    })
    .join(' ')
}

function gpuLastPercent(workerId: string): string {
  const arr = gpuHistory.value[workerId] || []
  return arr.length ? String(arr[arr.length - 1] ?? 0) + '%' : '-'
}

function statusTagType(status: string) {
  if (status === 'Running') return 'primary'
  if (status === 'Success') return 'success'
  if (status === 'Failed') return 'danger'
  return 'warning'
}

/** 抽屉中展示的任务：用 store 里 workers/pending 的实时状态覆盖，避免任务结束后抽屉上方状态不更新 */
const drawerTask = computed(() => {
  const task = selectedTask.value
  const sid = selectedTaskId.value
  if (!task || !sid) return task
  for (const w of workers.value) {
    const t = w.tasks.find((x) => x.task_id === sid)
    if (t) return { ...task, status: t.status, assigned_worker: w.worker_id }
  }
  const pending = pendingTasks.value.find((p) => p.task_id === sid)
  if (pending) return { ...task, status: 'Pending' as const, assigned_worker: null }
  return task
})

async function openTaskDrawerFromPending(task: PendingTask) {
  await openTaskDrawer(task.task_id)
}

function openTaskDrawerFromWorker(taskId: string) {
  openTaskDrawer(taskId)
}

async function openTaskDrawer(taskId: string) {
  selectedTaskId.value = taskId
  drawerVisible.value = true
  drawerLoading.value = true
  initialLogs.value = []
  storeLengthAtOpen.value = 0

  try {
    const [detail, logs] = await Promise.all([getTaskDetail(taskId), getTaskLogs(taskId)])
    selectedTask.value = detail
    initialLogs.value = logs
    storeLengthAtOpen.value = (taskLogs.value[taskId] || []).length
    nextTick(scrollToBottomIfAtBottom)
  } catch {
    selectedTask.value = null
    initialLogs.value = []
  } finally {
    drawerLoading.value = false
  }
}

function onDrawerClose() {
  drawerVisible.value = false
  selectedTaskId.value = null
}

watch(displayLogs, () => scrollToBottomIfAtBottom(), { flush: 'post' })

watch(
  () => [selectedTaskId.value, pendingTasks.value.map((t) => t.task_id).join(',')] as const,
  async () => {
    if (!selectedTaskId.value || !drawerVisible.value) return
    if (pendingTasks.value.some((t) => t.task_id === selectedTaskId.value)) {
      try {
        const detail = await getTaskDetail(selectedTaskId.value)
        selectedTask.value = detail
      } catch {
        selectedTask.value = null
      }
    }
  },
  { flush: 'post' }
)

// 任务结束时（状态变为 Success/Failed）重新拉取详情，以便抽屉内结束时间等字段更新
watch(
  () =>
    drawerVisible.value &&
    selectedTaskId.value &&
    drawerTask.value?.status &&
    (drawerTask.value.status === 'Success' || drawerTask.value.status === 'Failed') &&
    !selectedTask.value?.finished_at,
  async (needRefetch) => {
    if (!needRefetch || !selectedTaskId.value) return
    try {
      const detail = await getTaskDetail(selectedTaskId.value)
      selectedTask.value = detail
    } catch {
      // 忽略单次拉取失败，保留当前展示
    }
  },
  { flush: 'post' }
)

onMounted(() => {
  clusterStore.ensureConnected()
  fetchOverview()
  timer = setInterval(fetchOverview, 5000)
  tickGpuChart()
  chartTimer = setInterval(tickGpuChart, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (chartTimer) clearInterval(chartTimer)
})
</script>

<template>
  <div class="overview-page">
    <h1 class="page-title">
      <span class="page-title-text">集群总览</span>
      <span class="page-title-line" />
    </h1>

    <template v-if="loading && !overview">
      <div class="loading-wrap">
        <el-icon class="is-loading" :size="32"><CircleCheck /></el-icon>
        <span>加载中...</span>
      </div>
    </template>

    <template v-else-if="error">
      <el-empty :description="error">
        <el-button type="primary" @click="fetchOverview">重试</el-button>
      </el-empty>
    </template>

    <template v-else-if="overview">
      <div class="overview-center">
      <el-row :gutter="16" class="stat-row">
        <el-col v-for="(col, idx) in statCols" :key="col.key" :xs="12" :sm="8" :md="6" class="stat-col" :style="{ animationDelay: idx * 0.06 + 's' }">
          <el-card shadow="hover" class="stat-card" :class="col.klass">
            <el-statistic :title="col.title" :value="col.value">
              <template v-if="col.prefix" #prefix>
                <el-icon><component :is="col.prefix" /></el-icon>
              </template>
              <template v-if="col.suffix" #suffix>{{ col.suffix }}</template>
            </el-statistic>
            <div v-if="col.sub" class="progress-text">{{ col.sub }}</div>
          </el-card>
        </el-col>
      </el-row>

      <div v-if="!hasData" class="empty-tip">
        <el-empty description="暂无 Worker 与任务，请通过顶部「新增 Worker」和「新增任务」开始" />
      </div>

      <Uncompletedlist :pending-tasks="pendingTasks" @open-task="openTaskDrawerFromPending" />

      <el-row v-if="sortedWorkers.length" :gutter="16" class="worker-row">
        <Worker
          v-for="(w, idx) in sortedWorkers"
          :key="w.worker_id"
          :worker="w"
          :gpu-chart-points="getGpuChartPoints(w.worker_id)"
          :gpu-last-percent="gpuLastPercent(w.worker_id)"
          :style="{ animationDelay: (idx * 0.05) + 's' }"
          @open-task="openTaskDrawerFromWorker"
        />
      </el-row>
      </div>
    </template>

    <!-- 任务详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      title="任务详情"
      size="40%"
      direction="rtl"
      class="overview-drawer"
      :destroy-on-close="true"
      @close="onDrawerClose"
    >
      <div v-if="drawerLoading" class="drawer-loading">
        <el-icon class="is-loading" :size="24"><CircleCheck /></el-icon>
        <span>加载任务详情...</span>
      </div>
      <template v-else>
        <div v-if="drawerTask" class="drawer-content">
          <section class="drawer-section drawer-meta">
            <h3 class="drawer-task-name">{{ drawerTask.task_name }}</h3>
            <p class="drawer-task-id">ID: {{ drawerTask.task_id }}</p>
            <div class="drawer-status-row">
              <span class="drawer-label">状态</span>
              <el-tag :type="statusTagType(drawerTask.status)" size="small">{{ drawerTask.status }}</el-tag>
            </div>
            <div class="drawer-grid">
              <div class="drawer-grid-item"><span class="drawer-label">CPU / GPU</span>{{ drawerTask.cpu_required }} / {{ drawerTask.gpu_required }}</div>
              <div class="drawer-grid-item"><span class="drawer-label">Worker</span>{{ drawerTask.assigned_worker || '-' }}</div>
              <div class="drawer-grid-item"><span class="drawer-label">提交</span>{{ formatDateTime(drawerTask.submitted_at) }}</div>
              <div class="drawer-grid-item"><span class="drawer-label">开始</span>{{ formatDateTime(drawerTask.started_at) }}</div>
              <div class="drawer-grid-item"><span class="drawer-label">结束</span>{{ formatDateTime(drawerTask.finished_at) }}</div>
            </div>
            <div class="drawer-command">
              <span class="drawer-label">Command</span>
              <pre class="drawer-command-code">{{ drawerTask.command }}</pre>
            </div>
          </section>
          <section class="drawer-section drawer-log-section">
            <div class="drawer-log-header">
              <span class="drawer-label">日志输出</span>
              <span v-if="displayLogs.length" class="drawer-log-count">{{ displayLogs.length }} 条</span>
            </div>
            <div ref="logContainerRef" class="drawer-log-container">
              <pre v-if="displayLogs.length" class="drawer-log-content">
<span v-for="(log, index) in displayLogs" :key="index">{{ log.timestamp }}  {{ log.content }}
</span>
              </pre>
              <div v-else class="drawer-log-empty">暂无日志</div>
            </div>
          </section>
        </div>
        <el-empty v-else description="未找到任务详情" />
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.overview-page {
  min-height: 200px;
}

.overview-center {
  width: 78%;
  max-width: 1200px;
  margin: 0 auto;
}

.page-title {
  margin: 0 0 28px 0;
  font-size: 26px;
  font-weight: 700;
  color: var(--app-text);
  letter-spacing: -0.02em;
  position: relative;
  display: inline-block;
}

.page-title-text {
  position: relative;
  z-index: 1;
}

.page-title-line {
  position: absolute;
  left: 0;
  bottom: 2px;
  width: 100%;
  height: 6px;
  background: linear-gradient(90deg, var(--app-accent), transparent);
  opacity: 0.35;
  border-radius: 3px;
  z-index: 0;
}

.loading-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 48px;
  color: var(--app-text-muted);
  font-size: 15px;
}

.stat-row {
  margin-bottom: 20px;
}

.stat-col {
  animation: fade-in-up 0.4s ease backwards;
}

.stat-card {
  margin-bottom: 16px;
  border-radius: var(--app-radius);
  border: 1px solid var(--app-border);
  transition: transform var(--app-transition), box-shadow var(--app-transition), border-color var(--app-transition);
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--app-card-shadow-hover);
  border-color: var(--app-accent-soft);
}

.stat-card :deep(.el-statistic__head) {
  font-size: 13px;
  color: var(--app-text-muted);
  font-weight: 500;
}

.stat-card :deep(.el-statistic__content) {
  font-size: 24px;
  font-weight: 700;
}

.stat-card :deep(.el-statistic__prefix) {
  margin-right: 8px;
  color: var(--app-accent);
}

.stat-online :deep(.el-statistic__number) {
  color: var(--app-success);
}

.stat-running :deep(.el-statistic__number) {
  color: var(--app-accent);
}

.stat-pending :deep(.el-statistic__number) {
  color: var(--app-warning);
}

.progress-text {
  margin-top: 8px;
  font-size: 12px;
  color: var(--app-text-muted);
}

.empty-tip {
  margin-top: 28px;
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  min-height: 200px;
}

.worker-row {
  margin-top: 20px;
}

.worker-row :deep(.el-col) {
  animation: fade-in-up 0.45s ease backwards;
}

.drawer-loading {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--app-text-muted);
}

.drawer-content {
  display: flex;
  flex-direction: column;
  gap: 0;
  height: 100%;
  min-height: 0;
}

.drawer-section {
  flex-shrink: 0;
}

.drawer-meta {
  padding: 4px 0 16px;
  border-bottom: 1px solid var(--app-border);
  margin-bottom: 12px;
}

.drawer-task-name {
  font-size: 17px;
  font-weight: 600;
  margin: 0 0 4px 0;
  color: var(--app-text);
}

.drawer-task-id {
  font-size: 12px;
  color: var(--app-text-muted);
  margin: 0 0 10px 0;
}

.drawer-label {
  display: inline-block;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--app-text-muted);
  margin-bottom: 4px;
}

.drawer-status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.drawer-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px 16px;
  font-size: 13px;
  color: var(--app-text);
  margin-bottom: 12px;
}

.drawer-grid-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.drawer-command {
  margin-top: 4px;
}

.drawer-command-code {
  background: #f1f5f9;
  color: #1e293b;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 12px;
  white-space: pre-wrap;
  margin: 0;
  border: 1px solid var(--app-border);
}

/* 日志区占据下方全部空间 */
.drawer-log-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #0f172a;
  margin: 0 -20px -20px -20px;
  padding: 0;
  border-radius: 12px 0 0 0;
}

.drawer-log-header {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #1e293b;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 12px;
}

.drawer-log-header .drawer-label {
  margin: 0;
  color: #94a3b8;
}

.drawer-log-count {
  font-size: 12px;
  color: #64748b;
}

.drawer-log-container {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 12px 16px;
}

.drawer-log-content {
  font-family: 'JetBrains Mono', Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  margin: 0;
  white-space: pre-wrap;
  color: #e2e8f0;
  line-height: 1.5;
}

.drawer-log-empty {
  font-size: 12px;
  color: #64748b;
  padding: 24px 0;
}

:deep(.overview-drawer .el-drawer__header) {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--app-border);
  font-size: 18px;
  font-weight: 600;
  color: var(--app-text);
}

:deep(.overview-drawer .el-drawer__body) {
  padding: 16px 20px 20px;
  height: calc(100% - 55px);
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
</style>
