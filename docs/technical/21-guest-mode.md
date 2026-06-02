# 游客模式

## 1. 概述

允许未注册用户以只读方式访问部分功能。

## 2. 实现

### 后端
- `api/auth/guest-login/` — 创建临时游客用户，返回 JWT
- Guest 用户分配 `Guest` 组，只读权限
- Celery 定时任务清理超 7 天未活跃游客

### 前端
- `loginAsGuest()` 调用后端获取 JWT
- Token 存 `sessionStorage`（关闭即失效）
- 侧边栏显示"游客"标识

## 3. 可访问页面

排班表浏览、图书馆浏览、公告浏览等只读页面。
