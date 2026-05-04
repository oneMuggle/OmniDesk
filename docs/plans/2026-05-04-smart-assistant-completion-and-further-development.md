# OmniDesk 进一步开发计划

> 生成日期：2026-05-04
> 当前分支：develop
> 智能助手整体进度约 75%，本计划覆盖剩余收尾及下一阶段功能

---

## 阶段 1：补全智能助手剩余工作（1-2 天）

### 1.1 Ragflow 数据集 ID 配置

**问题**：`SMART_ASSISTANT_DATASET_ID` 未在 `settings/local.py` 中配置，知识库向量化无法工作。

**方案**：
- 在 `settings/local.py` 中添加环境变量读取 + 默认占位符
- 参照 `base.py` 中 `OLLAMA_BASE_URL` 的模式，使用 `os.environ.get()`
- 在启动时检查该配置是否存在，若未配置则输出警告

### 1.2 智能助手后端测试

**问题**：smart_assistant 模块没有任何测试用例。

**需要覆盖的文件**：

| 文件 | 测试内容 |
|------|----------|
| `tools/schedule_tool.py` | 日期解析（今天/明天/后天/昨天）、无排班返回 |
| `tools/personnel_tool.py` | 关键字搜索、脱敏输出、空结果 |
| `tools/rag_tool.py` | Ragflow 调用成功/失败/未配置 |
| `agent/orchestrator.py` | 工具路由成功、工具失败 fallback、通用对话 |
| `tasks.py` | Celery 任务成功/失败/Ragflow 配置缺失 |
| `views.py` | 聊天 API、流式 API、知识库 CRUD |

### 1.3 Celery Worker 验证

**问题**：知识库文档上传依赖 Celery 异步任务，但 worker 未验证。

**方案**：
- 在 `docker-compose` 或本地开发文档中说明 Celery worker 启动方式
- 测试中 mock Celery 的 `apply_async`，不依赖真实 Redis

---

## 阶段 2：通知中心（3-5 天）

### 背景

计划文档中项目管理模块提到了"通知中心"，侧边栏也有"通知中心"入口占位，但当前无实现。

### 2.1 后端

**新建 `notifications` Django app**：

模型设计：
```python
class Notification(models.Model):
    user = ForeignKey(CustomUser)
    type = CharField  # schedule_change, announcement, memo_due, calibration_reminder, project_update
    title = CharField(max_length=200)
    content = TextField
    link = CharField(max_length=500, blank=True)  # 点击跳转的相对路径
    is_read = BooleanField(default=False)
    created_at = DateTimeField
```

API 端点：
- `GET /api/notifications/` — 列表（分页 + 过滤 type + is_read）
- `GET /api/notifications/unread-count/` — 未读数统计
- `PATCH /api/notifications/{id}/read/` — 标记已读
- `POST /api/notifications/batch-read/` — 批量标记已读

通知服务：
```python
class NotificationService:
    @staticmethod
    def create(user, type, title, content, link="")
    @staticmethod
    def mark_read(notification_id, user)
    @staticmethod
    def batch_mark_read(notification_ids, user)
    @staticmethod
    def get_unread_count(user)
```

与现有模块集成点：
- `events` — 排班变更时创建通知
- `announcements` — 公告发布时通知全员
- `memos` — 备忘录到期提醒
- `sensor_management` — 传感器校准到期

### 2.2 前端

- Header 通知铃铛组件（红点显示未读数）
- 通知下拉面板（最近 10 条，滚动加载更多）
- `/notifications` 通知列表页（全部/未读分类）
- 点击通知跳转到关联页面

### 2.3 实时推送

**方案 A（推荐）**：SSE（Server-Sent Events），与智能助手流式响应复用技术栈
**方案 B**：短轮询（每 30s），简单但不够实时

---

## 阶段 3：仪表盘增强（2-3 天）

### 背景

首页 Dashboard 目前较简单，可以整合各模块数据提供更丰富的视图。

### 方案

- **今日排班卡片**：显示今天值班人员和领导
- **待办事项**：备忘录到期 + 传感器校准到期
- **最新公告**：最近 5 条公告，标注未读
- **未读通知数**：红点提示
- **项目概览**：进行中项目数量 + 最近变更
- **快捷入口**：常用功能一键直达（智能助手、备忘录、公告等）

---

## 阶段 4：清理重复模型（1-2 天）

### 背景

- `sensors.Sensor` vs `sensor_management.Sensor` — 两个传感器模型
- `documents.EBook` vs `ebooks.Ebook` — 两个电子书模型

### 方案

- 标记旧模型为 deprecated（添加运行时警告）
- 将旧模型的 admin/Django admin 入口指向新模型
- 逐步迁移引用，最终移除旧模型

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
