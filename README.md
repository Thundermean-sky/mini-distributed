# 系统概述
本Demo是一个轻量级分布式任务调度系统，旨在展示任务提交、分布式调度、资源分配、状态监控和日志流的基本效果。系统采用中心化Master（调度器）+多个Worker节点的架构，使用Python后端（FastAPI + fakeredis模拟Redis）和Vue3前端（Element Plus）。所有任务执行均为模拟（不真实运行command，只生成随机日志行），以确保Demo易演示。核心目标：通过Web界面可视化展示分布式效果，包括资源热力图、任务列表和实时日志。
系统逻辑闭环：用户新增Worker → 新增任务 → 任务进入Pending（若无资源） → 调度器动态Bin Packing分配 → Worker模拟执行（日志推送） → 任务完成/失败 → 资源释放 → 触发下一次调度。
# 核心功能点与数据变化效果说明
以下逐一说明所有功能点，包括用户操作、数据变化和页面呈现效果，形成完整逻辑闭环。假设初始状态为空（无Worker、无任务）。
## 新增Worker

用户操作：点击Header右侧“新增Worker”按钮，弹出模态框。填写Worker ID（可选，后端生成）、总CPU核数、总GPU数（GB）。提交后POST到后端。
后端处理：在Redis创建worker:{worker_id} Hash，初始used_cpu=0、used_gpu=0、status=online、tasks=[]。推送WebSocket worker_update。
页面效果：
集群热力图新增一个Worker Card（右侧进度条显示0%使用率，左侧任务列表为空）。
如果是第一个Worker，页面从“无Worker”状态变为显示Card。
热力图支持滚动，如果Worker多于屏幕显示（e.g., >3个），通过滚动条查看。
示例：新增Worker1 (CPU=4, GPU=8) → Card显示“Worker1 Online”，进度条CPU:0/4、GPU:0/8。

闭环：新增Worker增加可用资源，可能触发Pending任务的调度（见2.3）。

## 新增任务

用户操作：点击Header右侧“新增任务”按钮，弹出模态框。支持批量添加多行任务，每行填写任务名称（可选，后端生成）、Command、CPU Required、GPU Required。提交后POST数组到后端。
后端处理：为每个任务生成task_id，在Redis创建task:{task_id} Hash（初始status=Pending、assigned_worker=null）。RPUSH到pending_tasks List。立即尝试调度（Bin Packing）。
页面效果：
所有新任务初始出现在最上方“待执行任务列表”Card（状态: Padding，即Pending）。
Card最多显示2个任务，多余滚动查看。每个任务显示：任务名称、CPU使用数、GPU使用数、状态（Padding）。
点击任务 → 右侧抽屉显示详情（无执行/结束时间，无日志）。
如果无Pending任务，Card隐藏。

闭环：新增任务后，系统进入调度逻辑（见2.3）。

## 任务调度与资源不足情况

后端处理：调度器循环扫描pending_tasks。按任务资源需求降序排序（FFD算法），遍历每个Pending任务，找第一个剩余资源足够的Worker（used_cpu + required <= total_cpu, 同GPU）。匹配成功：分配任务、更新Worker tasks数组、used_cpu/gpu、任务assigned_worker和status=Running，从pending_tasks移除。无匹配：任务保持Pending。
页面效果：
有资源：任务从待执行列表消失，出现在对应Worker Card左侧任务列表（最上方Running）。Worker进度条更新（e.g., CPU从0/4 → 2/4）。
无资源：任务停留在待执行列表。用户可见“Pending”状态，直到资源释放。
示例（你的逻辑）：新增任务A (CPU=3, GPU=4)、B (CPU=1, GPU=2)。无Worker够 → 两者在待执行列表。Worker1释放资源 (剩余CPU=2, GPU=3) → B匹配先执行（移到Worker1 Card），A继续Pending。
WebSocket实时推送 pending_tasks_update 和 worker_update，页面无刷新动态变化。

闭环：调度失败不阻塞，资源释放（见2.4）后自动重试。

## 任务模拟执行

后端处理：分配后，任务status=Running，创建simulating:{task_id} Hash（lines_remaining=10~30随机、speed=500~1200ms）。后台循环每speed ms追加模拟日志到logs:{task_id} List，并推送task_log。日志随机生成（e.g., “Processing chunk 1/15...”）。lines_remaining=0时：70% Success（推送完成日志），30% Failed（日志突然停止，无完成消息）。更新status，释放Worker资源，推送task_status和worker_update。失败不删除simulating:{task_id}，所有日志永久保留。
页面效果：
任务在Worker Card左侧移到最上方（Running状态）。
点击任务 → 抽屉显示详情 + 实时日志滚动（每秒追加1~2行，自动滚底，像Linux命令输出）。
Success：日志末尾“Task completed successfully.”，状态绿色。
Failed：日志突然停止（e.g., 中途“Error occurred”后无输出），状态红色。
历史任务：Success/Failed移到列表下方，按执行时间排序。点击查看全日志（滚动查看）。

闭环：执行完释放资源，触发Pending任务重新调度（e.g., A等待后执行）。

## Worker心跳与离线

后端处理：Worker每5s心跳更新last_heartbeat。Master检查超时>10s → status=offline，推送worker_update。
页面效果：
Card变灰白，右上角“Offline”，任务不可点击，CPU/GPU进度条0%，使用数0。
离线Worker任务不执行，Pending任务不受影响（调度绕过离线Worker）。
恢复心跳 → Card恢复正常。

闭环：离线减少资源，Pending任务增加；恢复后资源增加，触发调度。

## 其他效果与边界

无Worker/任务：热力图空，待执行Card隐藏。
多任务/Worker：滚动条处理溢出（待执行最多2可见、Worker Card任务列表滚动）。
实时性：所有变化通过WebSocket动态更新，无手动刷新。
失败处理：Failed任务日志保留，抽屉显示全日志（无完成行）。
整体闭环：用户新增资源/任务 → 调度 → 执行（模拟日志） → 完成/失败 → 资源释放 → 新调度循环，确保系统自洽。