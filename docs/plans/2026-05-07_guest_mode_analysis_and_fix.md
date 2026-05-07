# 2026-05-07_guest_mode_analysis_and_fix.md

## 背景与目标

项目存在一个"游客模式"（Guest Mode），但实现不完整，导致游客用户体验断裂。本次分析目标是识别问题并提供修复方案。

## 当前状态分析

### 游客模式现有实现

1. **前端入口**：登录页有"以游客身份访问"按钮（`Login.jsx:119-127`）
2. **登录逻辑**：`AuthContext.js:138-151` 的 `loginAsGuest()` 仅清除 tokens 并设置 `isGuest=true`，**不调用任何后端 API**
3. **无后端支持**：后端没有任何 guest user 模型、guest 登录端点或匿名用户识别机制
4. **JWT token 缺失**：游客没有 JWT token，所有需要认证的 API 调用都会返回 401

### 发现的问题

| 问题 | 严重程度 | 说明 |
|------|---------|------|
| 游客无后端身份 | CRITICAL | `loginAsGuest()` 不调用后端，游客无 JWT token |
| API 调用全部失败 | CRITICAL | 任何调用认证 API 的页面（仪表盘、事件等）对游客都会 401 |
| 权限检查全部拒绝 | HIGH | `hasPermission()` 对 `user=null` 的游客始终返回 false |
| 路由保护不一致 | HIGH | 部分路由（`/library`, `/announcements`, `/docs/*`）没有任何保护，但 API 仍需认证 |
| 游客侧边栏信息缺失 | MEDIUM | 游客看不到用户名、主题切换、退出按钮 |
| 退出逻辑不合理 | MEDIUM | 退出重定向到 `/` 而非 `/login`，游客无法返回登录页 |
| 排班页面 guest 支持不完整 | LOW | `ShiftSchedule` 声明了 `isGuest` prop 但未实际使用 |

### 游客可访问的路由

| 路由 | 包装组件 | 状态 |
|------|---------|------|
| `/login` | GuestRoute | 正常 |
| `/register` | GuestRoute | 正常 |
| `/schedule` | GuestRoute | 可读，API 可能失败 |
| `/trial-schedule` | GuestRoute | 可读，API 可能失败 |
| `/shift-schedule` | GuestRoute | 可读，API 可能失败 |
| `/library`, `/books/*` | 无保护 | API 需要认证 |
| `/announcements` | 无保护 | API 需要认证 |
| `/communication/:postId` | 无保护 | API 需要认证 |
| `/docs/:docId` | 无保护 | API 需要认证 |
| 其余所有路由 | ProtectedRoute | 游客不可访问 |

## 修复方案

### 方案选择：后端 Guest User + JWT Token（推荐）

核心思路：为游客创建临时后端身份，返回有效 JWT token，使游客可以正常调用只读 API。

#### Phase 1: 后端 Guest 登录端点 [x]

- [x] 创建 `api/auth/guest-login/` 端点
- [x] 自动生成或复用 guest 用户（`User` 模型，用户名 `guest_{session_id}`）
- [x] 返回标准 JWT token（access + refresh）
- [x] Guest 用户分配到一个专门的 `Guest` 组，拥有只读页面权限

**涉及文件：**
- `omni_desk_backend/users/views.py` - 新增 `GuestLoginView`
- `omni_desk_backend/users/auth_urls.py` - 注册路由
- `omni_desk_backend/users/serializers.py` - 新增 `GuestLoginSerializer`

#### Phase 2: 前端 Guest 登录对接 [x]

- [x] 修改 `loginAsGuest()` 调用后端 `api/auth/guest-login/`
- [x] 接收并存储 JWT token（使用 sessionStorage，关闭即失效）
- [x] 获取 guest 用户的权限列表
- [x] 更新 `initializeAuth` 恢复游客会话
- [x] 更新 `logout` 逻辑，游客退出重定向到 `/login`
- [x] 更新 `hasPermission` 支持游客权限检查

**涉及文件：**
- `omni_desk_frontend/src/features/auth/context/AuthContext.js`

#### Phase 3: 游客权限配置 [x]

- [x] 确定游客可访问的页面清单（排班表、图书馆浏览、公告浏览等只读页面）
- [x] 创建 `setup_guest_permissions` 管理命令配置 `Guest` 组的 `GroupPagePermission`

**涉及文件：**
- `omni_desk_backend/permissions/management/commands/setup_guest_permissions.py`

#### Phase 4: 游客 UI 优化 [x]

- [x] 侧边栏为游客显示"游客"标识和"登录/注册"按钮
- [x] 退出按钮对游客可见

**涉及文件：**
- `omni_desk_frontend/src/shared/components/Sidebar.jsx`
- `omni_desk_frontend/src/App.css`

#### Phase 5: 数据清理机制 [x]

- [x] 创建 Celery 定时任务 `cleanup_expired_guest_users`，每天清理超过 7 天未活跃的游客用户

**涉及文件：**
- `omni_desk_backend/users/tasks.py`
- `omni_desk_backend/omni_desk_backend/settings/base.py`（Celery Beat schedule）

## 风险评估

| 风险 | 等级 | 应对 |
|------|------|------|
| Guest 用户数据膨胀 | MEDIUM | 定时清理过期 guest 用户 |
| 游客权限泄露 | LOW | Guest 组权限严格限制为只读，定期审计 |
| API 性能影响 | LOW | Guest 用户与普通用户共用 JWT 机制，无额外开销 |
| 前端兼容性问题 | LOW | 现有 `isGuest` 标志和逻辑可以保留并增强 |

## 工作量估算

| 阶段 | 工作量 |
|------|--------|
| Phase 1: 后端端点 | 2-3 小时 |
| Phase 2: 前端对接 | 1-2 小时 |
| Phase 3: 权限配置 | 2-3 小时 |
| Phase 4: UI 优化 | 1-2 小时 |
| Phase 5: 数据清理 | 1 小时 |
| **总计** | **7-11 小时** |
