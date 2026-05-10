# OmniDesk 项目全面优化计划

**日期**: 2026-05-10
**分支**: develop
**状态**: 阶段一和阶段二已完成

---

## 背景与目标

OmniDesk 是一个 Django 4.2 + React 18.3 的全栈业务管理平台。经过代码审查，发现以下可优化的领域：

- 存在死代码和重复组件
- 日志系统未充分利用
- 多处 N+1 查询和性能瓶颈
- 测试覆盖率不足
- 安全配置可以加固

---

## 涉及模块

- `omni_desk_backend/` - 后端（Django 4.2）
- `omni_desk_frontend/` - 前端（React 18.3）
- `deployment/docker/` - Docker 部署配置
- `utils/docker/` - 辅助 Docker Compose

---

## 优化清单

### 阶段一：快速修复（每项 <1 小时）

| # | 优化项 | 涉及文件 | 状态 |
|---|--------|----------|------|
| 1 | 清理死代码：重复 CustomUser 模型 | `omni_desk_backend/omni_desk_backend/models.py`, `serializers.py`, `views.py` | [x] |
| 2 | print() 替换为 logging | `compliance/tasks.py`, `documents/file_processing.py`, `llm_service/ollama_client.py` | [x] |
| 3 | 移除根目录 Vue 依赖 | 根目录 `package.json`, `package-lock.json`, `node_modules/` | [x] |
| 4 | 处理未注册的 llm_service | `omni_desk_backend/llm_service/` | [x] |
| 5 | 生产环境移除 BrowsableAPIRenderer | `settings/base.py` | [x] |
| 6 | 清理前端重复通信组件 | `src/components/communication/` vs `src/shared/components/communication/` | [x] |

### 阶段二：中等投入（半天 ~ 1 天）

| # | 优化项 | 涉及文件 | 状态 |
|---|--------|----------|------|
| 7 | 添加数据库索引 | 多个 models.py | [x] |
| 8 | 修复 get_user_permissions N+1 | `users/serializers.py:17-39` | [x] |
| 9 | Celery 合规任务 bulk_update | `compliance/tasks.py:33-46` | [x] |
| 10 | 添加健康检查端点 | `omni_desk_backend/urls.py` + 新 view | [x] |
| 11 | 前端统一使用 Logger | 前端 47 文件 | [x] |
| 12 | 缓存后端改用 Redis | `settings/base.py:124-128` | [x] |
| 13 | Gunicorn Worker 动态配置 | `deployment/docker/omni_desk_backend/Dockerfile:97` | [x] |

### 阶段三：大型计划（多天，独立排期）

| # | 优化项 | 涉及范围 | 状态 |
|---|--------|----------|------|
| 14 | CRA 迁移到 Vite | 整个前端 | [ ] |
| 15 | 补充测试覆盖率 | compliance/, dashboard/, notifications/, ragflow_service/ | [ ] |
| 16 | 消除全局 N+1 查询 | 所有 views.py 和 serializers.py | [ ] |
| 17 | 安全加固 | settings/base.py, axiosConfig.js | [ ] |
| 18 | 结构化日志 + 错误追踪 | 后端 settings + Sentry 集成 | [ ] |
| 19 | 整合 Docker Compose | 12 个 compose 文件合并 | [ ] |

---

## 实施步骤

### 阶段一

- [x] 步骤 1：清理死代码 - 删除 omni_desk_backend/models.py, serializers.py, views.py
- [x] 步骤 2：替换 print 为 logging - compliance/tasks.py, documents/file_processing.py, llm_service/ollama_client.py
- [x] 步骤 3：清理根目录 Vue 依赖（已不存在）
- [x] 步骤 4：评估并处理 llm_service（确认仍在使用，无需操作）
- [x] 步骤 5：调整 BrowsableAPIRenderer 配置
- [x] 步骤 6：清理前端重复通信组件（删除 dead shared/components, shared/pages, shared/api/communicationApi.js, announcements/NewPostPage.jsx）
- [x] 步骤 7：为高频查询字段添加 db_index（ComplianceIssue.status/due_date, Notification.is_read, Memo.is_completed/reminder_time, Personnel.name, Trial.start_date/end_date）
- [x] 步骤 8：优化用户权限查询（lru_cache 缓存 GroupPagePermission）
- [x] 步骤 9：Celery 合规任务改为 bulk_update
- [x] 步骤 10：添加 /api/health/ 端点
- [x] 步骤 11：前端批量替换 console.* 为 logger.*（47 文件）
- [x] 步骤 12：Django 缓存切换到 Redis（开发环境 fallback LocMemCache）
- [x] 步骤 13：Gunicorn worker 数量环境变量化

### 阶段二

- [ ] 步骤 7：为高频查询字段添加 db_index
- [ ] 步骤 8：优化用户权限查询（prefetch_related 或 Redis 缓存）
- [ ] 步骤 9：Celery 合规任务改为 bulk_update
- [ ] 步骤 10：添加 /api/health/ 端点
- [ ] 步骤 11：前端批量替换 console.* 为 logger.*
- [ ] 步骤 12：Django 缓存切换到 Redis
- [ ] 步骤 13：Gunicorn worker 数量环境变量化

### 阶段三

- [ ] 步骤 14：前端迁移 Vite（需独立计划文档）
- [ ] 步骤 15：补充测试覆盖率
- [ ] 步骤 16：全局 N+1 查询优化
- [ ] 步骤 17：安全加固
- [ ] 步骤 18：Sentry + 结构化日志集成
- [ ] 步骤 19：Docker Compose 整合

---

## 风险评估

| 风险 | 等级 | 应对措施 |
|------|------|----------|
| 删除 models.py 可能影响未发现的引用 | 中 | 删除前 grep 全局搜索导入 |
| 缓存切换到 Redis 可能影响本地开发 | 中 | 本地开发环境需确保 Redis 可用，或提供 LocMemCache fallback |
| CRA 迁移 Vite 可能破坏构建 | 高 | 需要完整回归测试，独立分支 |
| JWT 迁移 httpOnly cookie 需前端配合 | 高 | 独立项目排期，不影响当前优化 |

---

## 预期收益

- **性能**: N+1 查询消除后，用户列表、Dashboard 等核心接口响应时间预计降低 50%+
- **安全**: BrowsableAPI 不再暴露，CORS 配置修正，JWT 存储更安全
- **可维护性**: 死代码清理减少认知负担，统一日志便于排查问题
- **可观测性**: 结构化日志 + Sentry 实现生产环境错误追踪
