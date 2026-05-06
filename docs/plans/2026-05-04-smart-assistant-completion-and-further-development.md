# OmniDesk 进一步开发计划

> 生成日期：2026-05-04
> 当前分支：develop
> 智能助手整体进度约 75%，本计划覆盖剩余收尾及下一阶段功能

---

## 阶段 1：补全智能助手剩余工作 ✅ 已完成

### 完成内容：
- [x] 在 `settings/local.py` 添加 `SMART_ASSISTANT_DATASET_ID` 环境变量配置
- [x] 修复 `views.py` 中 `AgentLogSerializer` 未导入的 `NameError`
- [x] 修复 `AgentLog` 创建时 `tool_output=None` 导致数据库 NOT NULL 错误
- [x] 新增 45 个测试用例（`test_tools.py` + `test_orchestrator.py` + `test_tasks.py` + `test_views.py`）
- [x] 全量测试 266/267 通过（1 个失败为已有 events 测试，与本次无关）

---

## 阶段 2：通知中心 ✅ 已完成

### 背景

计划文档中项目管理模块提到了"通知中心"，侧边栏也有"通知中心"入口占位，但当前无实现。

### 2.1 后端 ✅

**已完成：**
- [x] 新建 `notifications` Django app（models.py, serializers.py, views.py, urls.py, apps.py, signals.py, service.py）
- [x] Notification 模型：type 字段覆盖 schedule_change, announcement, memo_due, calibration_reminder, project_update, compliance_issue, system
- [x] ViewSet：列表（分页+过滤 type+is_read）、unread_count、mark_read、mark_all_read
- [x] NotificationService 服务类
- [x] Django 信号集成：Schedule 创建通知值班人员/领导，Announcement 创建通知全员，ComplianceIssue 通知项目负责人，Memo 创建通知用户
- [x] 注册到 INSTALLED_APPS 和主 urls.py
- [x] 数据库迁移已生成（`0001_initial.py`）

**新建文件：**
- `notifications/__init__.py`
- `notifications/apps.py`
- `notifications/models.py`
- `notifications/serializers.py`
- `notifications/views.py`
- `notifications/urls.py`
- `notifications/service.py`
- `notifications/signals.py`
- `notifications/migrations/__init__.py`
- `notifications/migrations/0001_initial.py`

**修改文件：**
- `omni_desk_backend/settings/base.py` — 添加 `notifications.apps.NotificationsConfig`
- `omni_desk_backend/urls.py` — 添加 `path('notifications/', include('notifications.urls'))`

### 2.2 前端 ✅

**已完成：**
- [x] 新建 `features/notifications/api/notificationApi.js` — getList, markRead, markAllRead, getUnreadCount
- [x] 重写 `shared/pages/NotificationsPage.jsx` — 使用 React Query，支持全部/未读/已读筛选，点击行自动标记已读，一键标记全部已读
- [x] 更新 `shared/components/Sidebar.jsx` — 将 badge 轮询从 `complianceApi.getUnreadCount()` 切换到 `notificationApi.getUnreadCount()`

### 2.3 信号集成 ✅

**已完成：**
- [x] `events.Schedule` 创建 → 通知值班人员和值班领导
- [x] `events.Announcement` 创建 → 通知所有用户（排除作者）
- [x] `compliance.ComplianceIssue` 创建 → 通知项目负责人
- [x] `memos.Memo` 创建（带提醒时间）→ 通知备忘录用户

---

## 阶段 3：仪表盘增强 ✅ 已完成

### 背景

首页 Dashboard 目前较简单，可以整合各模块数据提供更丰富的视图。

### 3.1 后端 ✅

**已完成：**
- [x] 新建 `dashboard` Django app（apps.py, views.py, urls.py）
- [x] `GET /api/dashboard/stats/` 聚合接口：今日排班、最新公告、备忘录提醒、项目概览、未读通知
- [x] 注册到 INSTALLED_APPS 和主 urls.py

### 3.2 前端 ✅

**已完成：**
- [x] 重写 `shared/pages/DashboardPage.js`
- [x] 新增行：未读通知统计、进行中项目统计、今日值班卡片
- [x] 新增行：待办事项（7 天内备忘录）+ 最新公告
- [x] 保留原有本周概览（试验/排班/会议室）

---

## 阶段 4：清理重复模型 ✅ 已完成

### 背景

- `sensors.Sensor` vs `sensor_management.Sensor` — 两个传感器模型
- `documents.EBook` vs `ebooks.Ebook` — 两个电子书模型

### 已完成：

- [x] `sensors/models.py` — 添加 `DeprecationWarning` + docstring 标记为已弃用
- [x] `documents/models.py` — `EBook` 类添加已弃用 docstring，指向 `ebooks.Ebook`
- [x] 保留旧模型功能以兼容现有引用，待后续迁移完成后移除

---

## 风险与依赖

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Ollama 服务不可用 | 智能助手意图分类失败 | 已有 fallback 到 general_chat |
| Ragflow 服务不可用 | 知识库向量化失败 | 已有优雅降级 |
| Celery + Redis 未启动 | 文档上传后状态卡在 pending | 阶段 1 验证 |
| 通知中心与现有模块耦合 | 集成工作量大 | 使用信号解耦，逐步接入 |

---

## 执行顺序

| 阶段 | 内容 | 预计工时 |
|------|------|----------|
| **1** | 补全智能助手（配置 + 测试） | 1-2 天 |
| **2** | 通知中心后端 + 前端 | 3-5 天 |
| **3** | 仪表盘增强 | 2-3 天 |
| **4** | 清理重复模型 | 1-2 天 |
