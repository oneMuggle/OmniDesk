# 2026-06-02_django-admin-login-fix.md

## 背景与目标

用户在管理面板（`/control-panel/`）侧边栏点击"Django 后台"链接后，跳转到了登录页面而不是 Django admin 后台页面。

**根因分析**：
- 前端使用 JWT 认证（token 存储在 localStorage）
- Django admin 使用 session 认证
- 用户在前端登录后有 JWT token，但没有 Django session
- 访问 `/admin/` 时 Django 检测到未认证，重定向到 Django admin 登录页

**目标**：
- 用户点击"Django 后台"后，自动建立 Django session，然后跳转到 Django admin 后台

## 涉及的文件与模块

| 文件 | 修改内容 |
|------|----------|
| `omni_desk_backend/users/views.py` | 新增 `django_admin_login` 视图 |
| `omni_desk_backend/users/urls.py` | 注册新端点 |
| `omni_desk_frontend/src/features/admin/components/AdminLayout.jsx` | 修改 Django 后台链接 |

## 技术方案

### 后端：JWT → Session 转换端点

创建一个新的 API 端点 `/api/users/django-admin-login/`：

1. 接收 GET 请求，token 通过 URL 参数 `?token=xxx` 传递
2. 使用 `AccessToken` 直接验证 JWT
3. 检查用户是否为 superuser 或 staff
4. 调用 `django.contrib.auth.login()` 建立 session
5. 调用 `get_token()` 获取并设置 CSRF token
6. 重定向到 `/admin/`

使用 `@csrf_exempt` 因为此端点通过 URL 参数认证而非 session cookie。

### 前端：页面导航方式

将 `<a href="/admin/" target="_blank">` 改为：

1. 从 localStorage 获取 JWT access token
2. 使用 `window.location.href` 导航到 `/api/users/django-admin-login/?token=xxx`
3. 后端验证 token、建立 session、重定向到 `/admin/`
4. 浏览器收到 session cookie 和 CSRF cookie，Django admin 正常工作

**关键设计**：使用 `window.location.href`（当前页面导航）而非 `window.open`，确保 session cookie 在当前上下文中设置，后续的 Django admin 表单提交可以使用该 session。

## 实施步骤

- [x] 步骤 1：创建后端 JWT → Session 转换视图（接受 token 参数）
- [x] 步骤 2：注册 URL 端点
- [x] 步骤 3：修改前端 AdminLayout.jsx 链接逻辑（使用 window.location.href）
- [x] 步骤 4：语法和 lint 检查通过

## 风险与依赖

- **安全**：JWT token 通过 URL 传递，会出现在浏览器历史记录和服务器日志中（token 有效期 30 分钟，风险可控）
- **权限**：仅允许 staff/superuser 用户访问此端点
- **依赖**：用户必须有 Django superuser/staff 权限
