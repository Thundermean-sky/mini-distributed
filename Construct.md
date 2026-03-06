# 整体布局
页面采用Element Plus Layout：Header固定顶部、Sidebar左侧导航、Main Content右侧主体、Footer底部（可选）。响应式设计，支持滚动。
# Header

位置：页面顶部固定。
内容：左侧系统标题“轻量级分布式任务调度系统 Demo”；右侧“新增Worker”按钮、“新增任务”按钮、连接状态（绿色“Online” / 红色“Offline”）。

# Sidebar

位置：左侧固定，宽度200px，可折叠。
内容：3个选项卡（总览、Worker管理、任务管理）。默认“总览”页面显示Main Content。其他选项卡可扩展（Demo中简化为总览）。

# Main Content（总览页面）

位置：Sidebar右侧，占满剩余空间。
子区域：
待执行任务列表 Card（最上方，可隐藏）：
最多显示2个任务，多余垂直滚动。
每个任务：任务名称、CPU使用数、GPU使用数、状态（Padding）。
点击 → 右侧抽屉（详情无执行/结束时间、无日志）。

Worker Cards（下方网格，垂直滚动多Worker）：
每个Card：左右两部分 + 右上角状态（Online/Offline）。
左侧任务列表：垂直滚动。Running任务最上、Success次之、Failed最后，同状态按执行时间排序。每个任务：任务名称、CPU使用数、GPU使用数、状态。点击 → 右侧抽屉（详情 + 日志滚动）。
右侧资源展示：CPU进度条（使用/总）、GPU进度条（使用/总）。
离线：Card灰白、状态Offline、任务不可点击、进度条0%。


# 右侧抽屉（Drawer）

触发：点击任何任务。
内容：任务名称、CPU/GPU使用、创建/执行/结束时间、状态、Command。下半部日志区（预格式文本 + 滚动条）。Running实时追加日志；Success/Failed显示全历史日志；Pending无日志。

# Footer

位置：底部固定。
内容：可选系统状态（如“Powered by xAI”）。