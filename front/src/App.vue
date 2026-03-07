<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { ElContainer, ElHeader, ElAside, ElMain, ElFooter, ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElInputNumber, ElMessage, ElSelect, ElOption } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Plus, User, List, Monitor, SwitchButton, VideoPlay } from '@element-plus/icons-vue'
import { addWorker, addTasks, scheduleWorkerOffline, startWorker, type NewWorkerPayload, type NewTaskPayload } from '@/api'
import { useClusterStore } from '@/stores/cluster'

// 当前激活的菜单
const activeMenu = ref('overview')
const router = useRouter()
const clusterStore = useClusterStore()
const { wsConnected, workers } = storeToRefs(clusterStore)

const onlineWorkers = computed(() => workers.value.filter((w) => w.status === 'online'))
const offlineWorkers = computed(() => workers.value.filter((w) => w.status === 'offline'))

// 切换菜单
const handleMenuClick = (menu: string) => {
  activeMenu.value = menu
  if (menu === 'overview') {
    router.push('/')
  } else if (menu === 'workers') {
    router.push('/workers')
  } else if (menu === 'tasks') {
    router.push('/tasks')
  }
}

// ========== 新增 Worker ==========
const showWorkerDialog = ref(false)
const workerFormRef = ref<FormInstance>()
const workerForm = reactive<NewWorkerPayload>({
  worker_id: '',
  total_cpu: 2,
  total_gpu: 1,
})
const workerRules: FormRules = {
  total_cpu: [{ required: true, message: '请输入 CPU 数量', trigger: 'blur' }, { type: 'number', min: 1, message: '至少为 1', trigger: 'blur' }],
  total_gpu: [{ required: true, message: '请输入 GPU 数量', trigger: 'blur' }, { type: 'number', min: 1, message: '至少为 1', trigger: 'blur' }],
}
const workerSubmitting = ref(false)

function openAddWorker() {
  workerForm.worker_id = ''
  workerForm.total_cpu = 2
  workerForm.total_gpu = 1
  showWorkerDialog.value = true
  workerFormRef.value?.clearValidate()
}

async function submitWorker() {
  if (!workerFormRef.value) return
  await workerFormRef.value.validate(async (valid) => {
    if (!valid) return
    workerSubmitting.value = true
    try {
      const payload: NewWorkerPayload = {
        total_cpu: workerForm.total_cpu,
        total_gpu: workerForm.total_gpu,
      }
      if (workerForm.worker_id?.trim()) payload.worker_id = workerForm.worker_id.trim()
      await addWorker(payload)
      ElMessage.success('Worker 添加成功')
      showWorkerDialog.value = false
    } catch (e: unknown) {
      const detail = e && typeof e === 'object' && 'response' in e ? (e as { response?: { data?: { detail?: string | unknown[] } } }).response?.data?.detail : null
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) && detail.length ? String((detail as { msg?: string }[])[0]?.msg ?? detail[0]) : '添加失败'
      ElMessage.error(msg)
    } finally {
      workerSubmitting.value = false
    }
  })
}

// ========== 新增任务（支持多行） ==========
interface TaskRow {
  task_name: string
  command: string
  cpu_required: number
  gpu_required: number
}
const showTaskDialog = ref(false)
const taskFormRef = ref<FormInstance>()
const taskRows = ref<TaskRow[]>([
  { task_name: '', command: '', cpu_required: 1, gpu_required: 1 },
])
const taskSubmitting = ref(false)

function addTaskRow() {
  taskRows.value.push({ task_name: '', command: '', cpu_required: 1, gpu_required: 1 })
}
function removeTaskRow(index: number) {
  if (taskRows.value.length <= 1) return
  taskRows.value.splice(index, 1)
}

function openAddTask() {
  taskRows.value = [{ task_name: '', command: '', cpu_required: 1, gpu_required: 1 }]
  showTaskDialog.value = true
  taskFormRef.value?.clearValidate()
}

async function submitTask() {
  const payloads: NewTaskPayload[] = []
  for (const row of taskRows.value) {
    const cmd = row.command?.trim()
    if (!cmd) continue
    payloads.push({
      command: cmd,
      cpu_required: row.cpu_required,
      gpu_required: row.gpu_required,
      ...(row.task_name?.trim() ? { task_name: row.task_name.trim() } : {}),
    })
  }
  if (payloads.length === 0) {
    ElMessage.warning('请至少填写一条任务的执行命令')
    return
  }
  taskSubmitting.value = true
  try {
    const res = await addTasks(payloads) as { success?: boolean; task_ids?: string[] }
    ElMessage.success(res.task_ids?.length ? `已创建 ${res.task_ids.length} 个任务` : '任务已创建')
    showTaskDialog.value = false
  } catch (e: unknown) {
    const detail = e && typeof e === 'object' && 'response' in e ? (e as { response?: { data?: { detail?: string | unknown[] } } }).response?.data?.detail : null
    const msg = typeof detail === 'string' ? detail : Array.isArray(detail) && detail.length ? String((detail as { msg?: string }[])[0]?.msg ?? detail[0]) : '创建失败'
    ElMessage.error(msg)
  } finally {
    taskSubmitting.value = false
  }
}

// ========== 停机（5s 后宕机） ==========
const showShutdownDialog = ref(false)
const shutdownWorkerId = ref('')
const shutdownSubmitting = ref(false)

function openShutdownDialog() {
  shutdownWorkerId.value = onlineWorkers.value[0]?.worker_id ?? ''
  showShutdownDialog.value = true
}

async function submitShutdown() {
  if (!shutdownWorkerId.value) return
  shutdownSubmitting.value = true
  try {
    await scheduleWorkerOffline(shutdownWorkerId.value)
    ElMessage.success('该 Worker 将在 5 秒后宕机，其 Running 任务将回到待执行列表')
    showShutdownDialog.value = false
  } catch (e: unknown) {
    const detail = e && typeof e === 'object' && 'response' in e ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail : null
    ElMessage.error(typeof detail === 'string' ? detail : '操作失败')
  } finally {
    shutdownSubmitting.value = false
  }
}

// ========== 开机 ==========
const showStartDialog = ref(false)
const startWorkerId = ref('')
const startSubmitting = ref(false)

function openStartDialog() {
  startWorkerId.value = offlineWorkers.value[0]?.worker_id ?? ''
  showStartDialog.value = true
}

async function submitStart() {
  if (!startWorkerId.value) return
  startSubmitting.value = true
  try {
    await startWorker(startWorkerId.value)
    ElMessage.success('Worker 已重新上线')
    showStartDialog.value = false
  } catch (e: unknown) {
    const detail = e && typeof e === 'object' && 'response' in e ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail : null
    ElMessage.error(typeof detail === 'string' ? detail : '操作失败')
  } finally {
    startSubmitting.value = false
  }
}
</script>

<template>
  <el-container class="app-container">
    <!-- Header -->
    <el-header class="app-header">
      <div class="app-logo">
        <span class="app-logo-icon">◇</span>
        <span>MeanSky 分布式任务调度</span>
      </div>
      <div class="app-actions">
        <el-button class="btn-action" type="success" :icon="VideoPlay" @click="openStartDialog" :disabled="!offlineWorkers.length">
          开机
        </el-button>
        <el-button class="btn-action" type="warning" :icon="SwitchButton" @click="openShutdownDialog" :disabled="!onlineWorkers.length">
          停机
        </el-button>
        <el-button class="btn-action" type="primary" :icon="Plus" @click="openAddWorker">
          新增 Worker
        </el-button>
        <el-button class="btn-action" type="success" :icon="Plus" @click="openAddTask">
          新增任务
        </el-button>
        <div :class="['status-dot', wsConnected ? 'online' : 'offline']">
          <span class="status-dot-bullet" />
          {{ wsConnected ? 'Online' : 'Offline' }}
        </div>
      </div>
    </el-header>

    <el-container class="app-body">
      <el-aside width="200px" class="app-aside">
        <div
          v-for="item in [{ id: 'overview', label: '总览', icon: Monitor }, { id: 'workers', label: 'Worker 管理', icon: User }, { id: 'tasks', label: '任务管理', icon: List }]"
          :key="item.id"
          class="menu-item"
          :class="{ active: activeMenu === item.id }"
          @click="handleMenuClick(item.id)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </div>
      </el-aside>
      <el-main class="app-main">
        <div class="app-main-bg" aria-hidden="true" />
        <div class="app-main-inner">
          <router-view v-slot="{ Component }">
            <transition name="page-fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </div>
      </el-main>
    </el-container>

    <el-footer class="app-footer">
      轻量级分布式任务调度 Demo · FastAPI + Vue3 + fakeredis
    </el-footer>

    <!-- 新增 Worker 弹窗 -->
    <el-dialog v-model="showWorkerDialog" title="新增 Worker" width="400px" :close-on-click-modal="false" class="app-dialog">
      <el-form ref="workerFormRef" :model="workerForm" :rules="workerRules" label-width="90px">
        <el-form-item label="Worker ID" prop="worker_id">
          <el-input v-model="workerForm.worker_id" placeholder="选填，不填则自动生成" clearable />
        </el-form-item>
        <el-form-item label="CPU 数量" prop="total_cpu" required>
          <el-input-number v-model="workerForm.total_cpu" :min="1" :max="256" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="GPU 数量" prop="total_gpu" required>
          <el-input-number v-model="workerForm.total_gpu" :min="1" :max="64" style="width: 100%;" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showWorkerDialog = false">取消</el-button>
        <el-button type="primary" :loading="workerSubmitting" @click="submitWorker">确定</el-button>
      </template>
    </el-dialog>

    <!-- 新增任务 弹窗（支持多行，内容过多时在弹窗内滚动） -->
    <el-dialog v-model="showTaskDialog" title="新增任务" width="520px" :close-on-click-modal="false" class="app-dialog app-dialog--tasks">
      <div class="task-dialog-scroll">
        <div v-for="(row, index) in taskRows" :key="index" class="task-row">
          <div class="task-row-title">任务 {{ index + 1 }}</div>
          <el-form ref="taskFormRef" label-width="90px" class="task-row-form">
            <el-form-item label="任务名称">
              <el-input v-model="row.task_name" placeholder="选填" clearable />
            </el-form-item>
            <el-form-item label="执行命令" required>
              <el-input v-model="row.command" type="textarea" :rows="1" placeholder="如：python train.py" />
            </el-form-item>
            <el-form-item label="CPU / GPU">
              <div style="display: flex; gap: 12px;">
                <el-input-number v-model="row.cpu_required" :min="1" :max="256" placeholder="CPU" />
                <el-input-number v-model="row.gpu_required" :min="1" :max="64" placeholder="GPU" />
              </div>
            </el-form-item>
          </el-form>
          <el-button v-if="taskRows.length > 1" type="danger" link @click="removeTaskRow(index)">删除</el-button>
        </div>
        <el-button type="primary" link class="task-add-row-btn" @click="addTaskRow">+ 添加一行</el-button>
      </div>
      <template #footer>
        <el-button @click="showTaskDialog = false">取消</el-button>
        <el-button type="success" :loading="taskSubmitting" @click="submitTask">确定</el-button>
      </template>
    </el-dialog>

    <!-- 开机 弹窗 -->
    <el-dialog v-model="showStartDialog" title="Worker 开机" width="400px" class="app-dialog">
      <p style="color: #606266; margin-bottom: 12px;">选择已离线的 Worker 重新上线。</p>
      <el-select v-model="startWorkerId" placeholder="选择 Worker" style="width: 100%;">
        <el-option
          v-for="w in offlineWorkers"
          :key="w.worker_id"
          :label="w.worker_id"
          :value="w.worker_id"
        />
      </el-select>
      <template #footer>
        <el-button @click="showStartDialog = false">取消</el-button>
        <el-button type="success" :loading="startSubmitting" @click="submitStart">确定开机</el-button>
      </template>
    </el-dialog>

    <!-- 停机 弹窗 -->
    <el-dialog v-model="showShutdownDialog" title="Worker 停机" width="400px" class="app-dialog">
      <p style="color: #606266; margin-bottom: 12px;">选择一名在线 Worker，将在 5 秒后宕机。其上的 Running 任务会自动回到待执行列表等待重新分配。</p>
      <el-select v-model="shutdownWorkerId" placeholder="选择 Worker" style="width: 100%;">
        <el-option
          v-for="w in onlineWorkers"
          :key="w.worker_id"
          :label="w.worker_id"
          :value="w.worker_id"
        />
      </el-select>
      <template #footer>
        <el-button @click="showShutdownDialog = false">取消</el-button>
        <el-button type="warning" :loading="shutdownSubmitting" @click="submitShutdown">确定停机</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<style scoped>
.app-container {
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: var(--app-header-bg);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  padding: 0 24px;
  height: 56px;
  flex-shrink: 0;
}

.app-logo {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 10px;
  letter-spacing: 0.02em;
}

.app-logo-icon {
  color: var(--app-accent);
  font-size: 14px;
  opacity: 0.95;
}

.app-actions {
  margin-left: auto;
  display: flex;
  gap: 10px;
  align-items: center;
}

.btn-action {
  transition: transform var(--app-transition), box-shadow var(--app-transition);
}
.btn-action:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(14, 165, 233, 0.25);
}

.status-dot {
  font-size: 13px;
  font-weight: 500;
  color: #94a3b8;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: 8px;
  padding: 4px 10px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.06);
  transition: color var(--app-transition), background var(--app-transition);
}

.status-dot-bullet {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}

.status-dot.online {
  color: var(--app-success);
}
.status-dot.online .status-dot-bullet {
  animation: pulse-dot 2s ease-in-out infinite;
}

.status-dot.offline {
  color: var(--app-danger);
}

.app-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
}

.app-aside {
  background: var(--app-sidebar);
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  padding: 12px 0;
}

.menu-item {
  padding: 14px 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #94a3b8;
  margin: 0 8px;
  border-radius: var(--app-radius-sm);
  transition: all var(--app-transition);
}

.menu-item:hover {
  background: var(--app-sidebar-hover);
  color: #e2e8f0;
}

.menu-item.active {
  background: var(--app-sidebar-active);
  color: #fff;
  font-weight: 600;
}

.menu-item.active .el-icon {
  color: inherit;
}

.app-main {
  position: relative;
  padding: 24px;
  overflow: auto;
  background: var(--app-content-bg);
}

.app-main-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(ellipse 80% 50% at 20% 40%, rgba(14, 165, 233, 0.08) 0%, transparent 50%),
    radial-gradient(ellipse 60% 40% at 80% 60%, rgba(6, 182, 212, 0.06) 0%, transparent 50%),
    radial-gradient(ellipse 50% 30% at 50% 80%, rgba(14, 165, 233, 0.05) 0%, transparent 45%);
  animation: bg-gradient-shift 18s ease-in-out infinite;
}

.app-main-inner {
  position: relative;
  z-index: 1;
  min-height: 100%;
}

.app-footer {
  height: 40px;
  background: var(--app-sidebar);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #64748b;
  flex-shrink: 0;
}

/* 页面切换过渡 */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.page-fade-enter-from {
  opacity: 0;
  transform: translateX(8px);
}
.page-fade-leave-to {
  opacity: 0;
  transform: translateX(-8px);
}

.task-add-row-btn {
  margin-bottom: 12px;
}

.task-row {
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  padding: 14px;
  margin-bottom: 12px;
  position: relative;
  transition: border-color var(--app-transition), box-shadow var(--app-transition);
}
.task-row:hover {
  border-color: var(--app-accent);
  box-shadow: 0 0 0 1px var(--app-accent-soft);
}
.task-row-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--app-text);
}
.task-row-form {
  margin-bottom: 0;
}
</style>