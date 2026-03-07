<script setup lang="ts">
import { computed } from 'vue'
import { ElCard, ElCol, ElRow, ElTag } from 'element-plus'
import type { WorkerInfo } from '@/api'

defineOptions({ name: 'WorkerCard' })

const props = defineProps<{
  worker: WorkerInfo
  gpuChartPoints: string
  gpuLastPercent: string
}>()

const emit = defineEmits<{
  (e: 'open-task', taskId: string): void
}>()

const CHART_WIDTH = 200
const CHART_HEIGHT = 48

function workerCpuPercent(w: WorkerInfo) {
  if (!w.total_cpu) return 0
  return Math.round((w.used_cpu / w.total_cpu) * 100)
}

function workerGpuPercent(w: WorkerInfo) {
  if (!w.total_gpu) return 0
  return Math.round((w.used_gpu / w.total_gpu) * 100)
}

const sortedTasks = computed(() => {
  const statusOrder: Record<string, number> = {
    Running: 0,
    Success: 1,
    Failed: 2,
  }
  return [...props.worker.tasks].sort((a, b) => {
    const sa = statusOrder[a.status] ?? 99
    const sb = statusOrder[b.status] ?? 99
    if (sa !== sb) return sa - sb
    return a.task_id.localeCompare(b.task_id)
  })
})

function statusTagType(status: string) {
  if (status === 'Running') return 'primary'
  if (status === 'Success') return 'success'
  if (status === 'Failed') return 'danger'
  return 'warning'
}

function openTask(taskId: string) {
  if (props.worker.status === 'online') emit('open-task', taskId)
}
</script>

<template>
  <el-col :span="24">
    <el-card
      class="worker-card"
      :class="{ offline: worker.status === 'offline' }"
      shadow="hover"
    >
      <div class="worker-header">
        <div class="worker-title">
          <span class="worker-name">{{ worker.worker_id }}</span>
        </div>
        <el-tag :type="worker.status === 'online' ? 'success' : 'info'" size="small">
          {{ worker.status === 'online' ? 'Online' : 'Offline' }}
        </el-tag>
      </div>
      <div class="worker-body">
        <div class="worker-tasks">
          <div class="worker-tasks-title">任务列表</div>
          <div class="worker-tasks-scroll hide-scrollbar">
            <div
              v-for="t in sortedTasks"
              :key="t.task_id"
              class="worker-task-item"
              :class="{ clickable: worker.status === 'online' }"
              @click="openTask(t.task_id)"
            >
              <div class="task-main">
                <div class="task-name">{{ t.task_name }}</div>
                <div class="task-meta">
                  <span>CPU: {{ t.cpu_used }}</span>
                  <span>GPU: {{ t.gpu_used }}</span>
                </div>
              </div>
              <el-tag :type="statusTagType(t.status)" size="small">
                {{ t.status }}
              </el-tag>
            </div>
            <div v-if="!worker.tasks.length" class="worker-task-empty">暂无任务</div>
          </div>
        </div>
        <div class="worker-resource">
          <div class="resource-item">
            <div class="resource-label">
              <span>CPU</span>
              <span>{{ worker.used_cpu }} / {{ worker.total_cpu }}</span>
            </div>
            <div class="resource-bar">
              <div
                class="resource-bar-inner cpu"
                :style="{ width: workerCpuPercent(worker) + '%' }"
              />
            </div>
          </div>
          <div class="resource-item">
            <div class="resource-label">
              <span>GPU</span>
              <span>{{ worker.used_gpu }} / {{ worker.total_gpu }}</span>
            </div>
            <div class="resource-bar">
              <div
                class="resource-bar-inner gpu"
                :style="{ width: workerGpuPercent(worker) + '%' }"
              />
            </div>
          </div>
          <div class="resource-item gpu-chart-wrap">
            <div class="resource-label">
              <span>GPU 使用率</span>
              <span>{{ gpuLastPercent }}</span>
            </div>
            <svg
              class="gpu-chart"
              :viewBox="`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`"
              preserveAspectRatio="none"
            >
              <polyline
                v-if="gpuChartPoints"
                class="gpu-chart-line"
                :points="gpuChartPoints"
                fill="none"
                stroke="var(--el-color-primary)"
                stroke-width="1.5"
              />
            </svg>
          </div>
        </div>
      </div>
    </el-card>
  </el-col>
</template>

<style scoped>
.worker-card {
  margin-bottom: 16px;
  min-height: 380px;
  overflow: visible;
  border-radius: 12px;
  border: 1px solid var(--app-border, #e2e8f0);
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s ease, border-color 0.25s ease;
}

.worker-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(14, 165, 233, 0.1);
  border-color: rgba(14, 165, 233, 0.25);
}

.worker-card.offline {
  opacity: 0.7;
}
.worker-card.offline:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  border-color: var(--app-border, #e2e8f0);
}

.worker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.worker-name {
  font-weight: 600;
  font-size: 15px;
  color: var(--app-text, #1e293b);
}

.worker-body {
  display: flex;
  gap: 14px;
}

.worker-tasks {
  flex: 1.5;
  min-width: 0;
}

.worker-tasks-scroll {
  height: 220px;
  overflow-y: auto;
  overflow-x: hidden;
}

.worker-tasks-title {
  font-size: 13px;
  color: var(--app-text-muted, #64748b);
  margin-bottom: 6px;
  font-weight: 500;
}

.worker-task-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 8px;
  border-radius: 8px;
  transition: background 0.2s ease;
}

.worker-task-item.clickable {
  cursor: pointer;
}

.worker-task-item.clickable:hover {
  background: rgba(14, 165, 233, 0.08);
}

.worker-task-empty {
  font-size: 12px;
  color: #94a3b8;
  padding: 10px 0;
}

.task-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.task-name {
  font-size: 13px;
}

.task-meta {
  font-size: 12px;
  color: var(--app-text-muted, #64748b);
  display: flex;
  gap: 8px;
}

.worker-resource {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.resource-item {
  font-size: 12px;
}

.resource-label {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.resource-bar {
  background: #f1f5f9;
  border-radius: 6px;
  height: 8px;
  overflow: hidden;
}

.resource-bar-inner {
  height: 100%;
  border-radius: 6px;
  transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

.resource-bar-inner.cpu {
  background: linear-gradient(90deg, #10b981, #f59e0b);
}

.resource-bar-inner.gpu {
  background: linear-gradient(90deg, #0ea5e9, #10b981);
}

.gpu-chart-wrap {
  margin-top: 4px;
}

.gpu-chart-wrap .resource-label {
  margin-bottom: 2px;
}

.gpu-chart {
  display: block;
  width: 100%;
  height: 48px;
  background: #f1f5f9;
  border-radius: 8px;
}

.gpu-chart-line {
  vector-effect: non-scaling-stroke;
  transition: opacity 0.2s ease;
}

.hide-scrollbar {
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.hide-scrollbar::-webkit-scrollbar {
  display: none;
}
</style>
