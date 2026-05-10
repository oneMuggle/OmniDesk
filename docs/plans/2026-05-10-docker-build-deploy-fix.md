# Docker 构建到部署全流程修复方案

> 日期: 2026-05-10
> 状态: 实施中
> 分支: develop

## 背景

项目多次构建 Docker 镜像后启动失败，出现以下错误：

1. Frontend nginx 权限错误：`mkdir() "/var/cache/nginx/client_temp" failed (13: Permission denied)`
2. 外层 nginx 找不到 frontend DNS：`host not found in upstream "frontend"`
3. PostgreSQL 密码认证失败：`FATAL: password authentication failed for user "omni_desk_user"`
4. `docker-compose.offline.yml` 缺少 volume 定义
5. 多个 compose 文件 image 标签不一致
6. `build_and_export.sh` 每次覆盖 `.env.production` 导致密码变化

## 根因分析

### 架构问题

当前存在两层 nginx 架构：
- `frontend` 服务：基于 nginx:stable-alpine，内置完整反向代理配置
- `nginx` 服务：基于 nginx:latest，反向代理到 frontend:80

**问题**：两层 nginx 功能完全重叠，frontend 的 `nginx.conf` 已经实现了所有需要的路由（API 代理、Admin 代理、静态文件、媒体文件、Gzip、安全头），外层 nginx 完全多余。

### 密码不一致问题

`build_and_export.sh` 每次执行都会从 `.env.production.defaults` 复制并重新生成密码，而 PostgreSQL 的 volume 中已有旧数据（旧密码初始化）。PostgreSQL 容器检测到已有数据目录后跳过初始化，新密码与旧用户不匹配。

## 方案设计

### 核心原则

1. **一个入口**：只保留 frontend（内置 nginx）作为 HTTP 入口，删除多余的 nginx 服务
2. **一份环境文件**：统一 `.env.production` 的生成和使用逻辑
3. **一条命令打通全流程**：从本地构建 → 镜像导出 → 离线导入 → 启动
4. **幂等性**：同一命令多次执行结果一致

### 新架构

```
用户请求
    ▼
┌─────────────┐
│  Frontend   │ :80 (内置 Nginx，已包含反向代理)
│  (React +   │
│   Nginx)    │
└──────┬──────┘
       │
       ├──────────────┐
       ▼              ▼
┌────────────┐ ┌────────────┐
│  Backend   │ │  Static/   │
│  Django    │ │  Media     │
│  :8000     │ │  Files     │
└──────┬─────┘ └────────────┘
       │
  ┌────┴────┐
  ▼         ▼
Postgres  Redis
```

## 实施步骤

### Phase 1: 修改文件

- [x] `omni_desk_frontend/Dockerfile` — 创建 nginx 缓存目录并授权
- [ ] `docker-compose.offline.yml` — 删除 nginx 服务，补 volume 定义
- [ ] `docker-compose.build.yml` — 前端添加 `target: builder`
- [ ] `build_and_export.sh` — 不覆盖已有 `.env.production`
- [ ] `deploy_offline.sh` — 增加首次部署初始化指引
- [ ] `.env.production.defaults` — 完善占位符

### Phase 2: 本地构建测试

- [ ] `./build_and_export.sh` — 重新构建并导出镜像
- [ ] `./deploy_offline.sh debug` — 验证启动

### Phase 3: 数据库初始化

- [ ] `migrate` — 数据库迁移
- [ ] `collectstatic` — 收集静态文件
- [ ] `createsuperuser` — 创建管理员

### Phase 4: 验证

- [ ] 前端可访问
- [ ] 后端 API 可访问
- [ ] 所有服务 healthy

## 修改清单详情

### 1. docker-compose.offline.yml

删除 `nginx` 服务，补充 `postgres_data`、`static_volume`、`media_volume` volume 定义。

### 2. docker-compose.build.yml

前端构建添加 `target: builder`，确保只构建生产阶段。

### 3. build_and_export.sh

只在 `.env.production` 不存在时才生成，避免覆盖已有配置。

### 4. deploy_offline.sh

增加首次部署检测，输出 migrate/collectstatic/createsuperuser 指引。

### 5. .env.production.defaults

确保占位符格式一致，能被 Python 脚本正确替换。

## 风险评估

| 风险 | 等级 | 应对 |
|------|------|------|
| 删除旧 volume 会丢失已有数据库数据 | 高 | 如需保留数据先 pg_dump 导出 |
| 旧 `.env.production` 密码与新 volume 不匹配 | 中 | 方案改为不覆盖已有 `.env.production` |
| frontend 内置 nginx 能否完全替代外层 | 低 | nginx.conf 已包含完整代理配置 |
