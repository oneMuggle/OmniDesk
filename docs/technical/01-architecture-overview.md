# OmniDesk 架构总览

## 1. 项目概述

OmniDesk 是一个全栈业务管理平台（中文 UI），采用 **Django 4.2**（后端）+ **React 18.3** via CRA（前端）。

### 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端 | Django 4.2 + DRF | REST API，JWT 认证 |
| 前端 | React 18.3 + CRA | Ant Design 5 + MUI 双 UI 库 |
| 数据库 | PostgreSQL 14 | 主数据库 |
| 缓存/队列 | Redis 7 | Celery 消息队列 + 缓存 |
| 任务队列 | Celery | 异步任务处理 |
| 反向代理 | Nginx | 静态文件 + API 代理 |
| 容器化 | Docker Compose | 多容器编排 |

### 状态管理

- **服务端状态**: TanStack React Query v5（5 min stale time, refetchOnWindowFocus: false）
- **认证状态**: React Context（JWT token 管理）
- **无全局状态库**: 不使用 Redux/Zustand

## 2. 目录结构

```
OmniDesk/
├── omni_desk_backend/              # Django 后端
│   ├── omni_desk_backend/          # Django 项目配置
│   │   └── settings/               # 分环境配置
│   │       ├── base.py             # 共享配置（DRF, JWT, CORS, Celery, i18n）
│   │       ├── local.py            # 本地开发（SQLite, DEBUG=True）← 默认
│   │       ├── development.py      # Docker 开发（PostgreSQL）
│   │       ├── production.py       # 生产环境
│   │       └── test.py             # 测试（内存 SQLite）
│   ├── users/                      # 自定义用户模型 (CustomUser)
│   ├── events/                     # 公告、事件
│   ├── personnel/                  # 人员管理
│   ├── memos/                      # 备忘录
│   ├── news/                       # 新闻管理
│   ├── projects/                   # 项目管理
│   ├── compliance/                 # 合规管理
│   ├── sensors/ / sensor_management/ # 传感器管理
│   ├── communication/              # 用户交流
│   ├── smart_assistant/            # 智能助手
│   ├── external_integration/       # 外部集成
│   └── ...
├── omni_desk_frontend/             # React 前端
│   ├── src/
│   │   ├── features/               # 按功能模块组织
│   │   ├── shared/                 # 共享组件、API、工具
│   │   └── routes/                 # 路由配置
│   └── scripts/generate-routes.js  # 路由自动生成
├── deployment/docker/              # Docker 部署脚本
├── docs/                           # 文档
└── .github/workflows/              # CI/CD
```

## 3. 认证与授权

- **认证**: JWT (djangorestframework-simplejwt)
  - Access Token: 30 min
  - Refresh Token: 7 天（rotation + blacklist）
  - Token 存储: localStorage/sessionStorage
- **后端授权**: 基于 `CustomUser.role`（管理员、经理、普通用户）
- **前端页面可见性**: 数据库驱动，管理员通过 UI 动态分配路由权限

## 4. 前端路由

- React Router v6.4+ (`createBrowserRouter`)
- 懒加载组件
- 构建时通过 Babel AST 自动生成 `public/routes.json`
- 受保护路由检查页面级权限

## 5. API 层

- Axios 实例 (`src/shared/api/axiosConfig.js`)
- baseURL: `/api/`
- JWT 拦截器（自动 token 刷新队列）
- 刷新失败重定向到 `/login`

## 6. 特殊约束

- **内网离线部署**: 所有产物自包含，无外部网络访问
- **Windows 7 兼容**: Chrome 109 / Edge 109，不主动放弃 IE11
- **双 UI 库**: Ant Design 5（主）和 MUI（次）共存
- **自定义用户模型**: `AUTH_USER_MODEL = 'users.CustomUser'`
