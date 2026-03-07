<script setup lang="ts">
import { ElCard, ElScrollbar, ElTag } from 'element-plus'
import type { PendingTask } from '@/api'

defineOptions({ name: 'Uncompletedlist' })

defineProps<{
  pendingTasks: PendingTask[]
}>()

const emit = defineEmits<{
  (e: 'open-task', task: PendingTask): void
}>()

function openTask(task: PendingTask) {
  emit('open-task', task)
}
</script>

<template>
  <el-card v-if="pendingTasks.length" class="pending-card" shadow="hover">
    <div class="pending-header">
      <span class="pending-title">待执行任务</span>
      <span class="pending-count">共 {{ pendingTasks.length }} 个 Pending</span>
    </div>
    <el-scrollbar max-height="120" class="hide-scrollbar">
      <div
        v-for="(task, index) in pendingTasks"
        :key="task.task_id"
        class="pending-item"
        :style="{ animationDelay: index * 0.04 + 's' }"
        @click="openTask(task)"
      >
        <div class="pending-main">
          <div class="pending-name">{{ task.task_name }}</div>
          <div class="pending-meta">
            <span>CPU: {{ task.cpu_required }}</span>
            <span>GPU: {{ task.gpu_required }}</span>
          </div>
        </div>
        <el-tag size="small" type="warning" class="pending-tag">Pending</el-tag>
      </div>
    </el-scrollbar>
  </el-card>
</template>

<style scoped>
.pending-card {
  margin-bottom: 20px;
  border-radius: 12px;
  border: 1px solid var(--app-border, #e2e8f0);
  transition: box-shadow 0.25s ease, border-color 0.25s ease;
}
.pending-card:hover {
  box-shadow: 0 8px 28px rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.25);
}

.pending-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--app-border, #e2e8f0);
}

.pending-title {
  font-weight: 600;
  font-size: 15px;
  color: var(--app-text, #1e293b);
}

.pending-count {
  font-size: 12px;
  color: var(--app-text-muted, #64748b);
}

.pending-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
  animation: fade-in-up 0.35s ease backwards;
}

.pending-item:hover {
  background: rgba(245, 158, 11, 0.08);
  transform: translateX(4px);
}

.pending-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pending-name {
  font-weight: 500;
  font-size: 13px;
}

.pending-meta {
  font-size: 12px;
  color: var(--app-text-muted, #64748b);
  display: flex;
  gap: 12px;
}

.pending-tag {
  flex-shrink: 0;
}

.hide-scrollbar {
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.hide-scrollbar::-webkit-scrollbar {
  display: none;
}
:deep(.hide-scrollbar .el-scrollbar__wrap) {
  scrollbar-width: none;
  -ms-overflow-style: none;
}
:deep(.hide-scrollbar .el-scrollbar__wrap::-webkit-scrollbar) {
  display: none;
}
</style>
