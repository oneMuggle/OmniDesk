# 部署流程 — 离线独立部署完整指南

> 最后更新: 2026-05-14
> 适用版本: v0.1.0+
> 目标环境: 无外网访问的内部网络（air-gapped）

---

## 目录

1. [架构概览](#架构概览)
2. [前置条件](#前置条件)
3. [Phase 1: 构建镜像](#phase-1-构建镜像)
4. [Phase 2: 验证产物](#phase-2-验证产物)
5. [Phase 3: 传输到目标服务器](#phase-3-传输到目标服务器)
6. [Phase 4: 离线部署](#phase-4-离线部署)
7. [Phase 5: 冒烟测试](#phase-5-冒烟测试)
8. [Phase 6: 监控运维](#phase-6-监控运维)
9. [Phase 7: 升级与回滚](#phase-7-升级与回滚)
10. [健康检查机制](#健康检查机制)
11. [常见问题排查](#常见问题排查)
12. [环境变量参考](#环境变量参考)

---

## 架构概览

```
                    ┌─────────────────────────────────────┐
                    │         Docker Host (Linux)          │
                    │                                      │
  Port 80 ────────► │  ┌──────────┐    ┌──────────────┐    │
  (Nginx)          │  │ frontend │    │   backend    │    │
                    │  │ :80      │    │   :8000      │    │
                    │  └────┬─────┘    └──┬──┬──┬─────┘    │
                    │       │             │  │  │          │
                    │       │             │  │  │          │
                    │       ▼             ▼  ▼  ▼          │
                    │  ┌─────────────────────────────┐    │
                    │  │      omni_desk network       │    │
                    │  └──────┬──────────┬───────────┘    │
                    │         │          │                │
                    │    ┌────▼──┐  ┌───▼────┐  ┌──────┐ │
                    │    │  db   │  │ redis  │  │worker│ │
                    │    │ :5432 │  │ :6379  │  │celery│ │
                    │    └───────┘  └────────┘  └──────┘ │
                    └─────────────────────────────────────┘

  数据卷: postgres_data, redis_data, static_volume, media_volume
```

### 服务清单

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| `db` | `postgres:14.2` | 5432 (内部) | PostgreSQL 数据库 |
| `redis` | `redis:7-alpine` | 6379 (内部) | 缓存 + Celery 消息队列 |
| `backend` | `omni-desk-backend-prod:latest` | 8000 | Django 后端 API |
| `frontend` | `omni-desk-frontend-prod:latest` | 80 | Nginx 静态资源 + 反向代理 |
| `worker` | `omni-desk-backend-prod:latest` | 无 | Celery 异步任务处理器 |

---

## 前置条件

### 构建机器（有外网）

- Docker 20.10+
- Node.js 20.x（前端构建）
- Python 3.11 + pip（后端构建）
- Git 仓库访问

### 目标服务器（无外网 / air-gapped）

- Docker 20.10+
- 8GB+ 内存
- 20GB+ 可用磁盘空间
- Linux 内核 4.x+
- **无需外网访问** — 所有镜像通过 `.tar` 文件离线传输

---

## Phase 1: 构建镜像

在**有外网的构建机器**上执行：

```bash
cd /path/to/InsiteWebsite

# 执行构建并导出
bash deployment/docker/build_and_export.sh
```

### 构建流程（脚本自动执行）

```
Step 1: 读取版本号 (deployment/docker/VERSION)
        → 例: v0.1.0

Step 2: 构建后端镜像
        docker build -f omni_desk_backend/Dockerfile \
          -t omni-desk-backend-prod:v0.1.0 \
          -t omni-desk-backend-prod:latest .

Step 3: 构建前端镜像
        docker build -f omni_desk_frontend/Dockerfile \
          -t omni-desk-frontend-prod:v0.1.0 \
          -t omni-desk-frontend-prod:latest .

Step 4: 拉取基础镜像
        docker pull postgres:14.2
        docker pull redis:7-alpine

Step 5: 验证容器可用性
        后端: 导入核心依赖检查
        前端: 检查 nginx 配置文件存在

Step 6: 导出为 .tar 文件
        docker save → deployment/docker/dist/omni-desk-backend-prod-v0.1.0.tar
        docker save → deployment/docker/dist/omni-desk-frontend-prod-v0.1.0.tar
        docker save → deployment/docker/dist/postgres-14.2.tar
        docker save → deployment/docker/dist/redis-7.tar
```

### 产物清单

```
deployment/docker/dist/
├── omni-desk-backend-prod-v0.1.0.tar   (~500MB)
├── omni-desk-frontend-prod-v0.1.0.tar  (~50MB)
├── postgres-14.2.tar                   (~200MB, 已加载时可能较小)
├── redis-7.tar                         (~30MB, 已加载时可能较小)
└── build-metadata.json                 (构建元数据)
```

---

## Phase 2: 验证产物

```bash
bash deployment/docker/validate_artifacts.sh
```

验证项：

- 所有 `.tar` 文件存在且大小 > 1KB
- 镜像可成功 `docker load`
- 后端容器能导入核心 Django 模块
- 前端容器包含 nginx 配置文件
- 构建元数据 JSON 格式正确

---

## Phase 3: 传输到目标服务器

### 方式 A: U 盘 / 移动硬盘

```bash
# 在构建机器上
cp -r deployment/docker/dist/ /media/usb-drive/

# 在目标服务器上
cp -r /media/usb-drive/dist/ /tmp/omni-desk-deploy/
```

### 方式 B: 内网 SCP

```bash
# 从构建机器推送到目标服务器
scp deployment/docker/dist/*.tar user@target-server:/tmp/omni-desk-deploy/
scp deployment/docker/.env.production user@target-server:/tmp/omni-desk-deploy/
scp deployment/docker/docker-compose.offline-standalone.yml user@target-server:/tmp/omni-desk-deploy/
scp deployment/docker/deploy_offline.sh user@target-server:/tmp/omni-desk-deploy/
```

### 方式 C: 完整打包

```bash
cd deployment/docker
tar czf omni-desk-offline-package-v0.1.0.tar.gz \
  dist/*.tar \
  .env.production \
  docker-compose.offline-standalone.yml \
  deploy_offline.sh
```

---

## Phase 4: 离线部署

在**目标服务器**上执行：

```bash
cd /tmp/omni-desk-deploy

# 方法一: 使用一键部署脚本
bash deploy_offline.sh deploy

# 方法二: 手动部署
# 1. 加载镜像
docker load -i dist/postgres-14.2.tar
docker load -i dist/redis-7.tar
docker load -i dist/omni-desk-backend-prod-v0.1.0.tar
docker load -i dist/omni-desk-frontend-prod-v0.1.0.tar

# 2. 确保标签正确
docker tag omni-desk-backend-prod:v0.1.0 omni-desk-backend-prod:latest
docker tag omni-desk-frontend-prod:v0.1.0 omni-desk-frontend-prod:latest

# 3. 配置环境变量
cp .env.production .env
# 编辑 .env 修改必要的配置（数据库密码等）

# 4. 启动服务
docker compose -f docker-compose.offline-standalone.yml --env-file .env.production up -d

# 5. 等待服务就绪（约 60-90 秒）
sleep 90

# 6. 检查服务状态
docker compose -f docker-compose.offline-standalone.yml ps
```

### 期望输出

```
NAME                          IMAGE                              STATUS
omni-desk-deploy-db-1         postgres:14.2                      healthy
omni-desk-deploy-redis-1      redis:7-alpine                     healthy
omni-desk-deploy-backend-1    omni-desk-backend-prod:latest      healthy
omni-desk-deploy-frontend-1   omni-desk-frontend-prod:latest     healthy
omni-desk-deploy-worker-1     omni-desk-backend-prod:latest      healthy
```

所有服务状态必须为 `healthy`。

---

## Phase 5: 冒烟测试

```bash
bash deployment/docker/smoke_tests.sh http://<target-server-ip>
```

测试项：

| # | 测试 | 端点 | 期望状态码 |
|---|------|------|-----------|
| 1 | 健康检查 | `GET /api/health/` | 200 |
| 2 | 未授权访问 | `GET /api/users/` | 401 |
| 3 | 静态资源 | `GET /` | 200 |
| 4 | 管理员页面 | `GET /control-panel/` | 200 |
| 5 | 登录功能 | `POST /api/auth/login/` | 200 |
| 6 | 版本号 API | `GET /api/system/version/` | 200 |
| 7 | 变更日志 API | `GET /api/system/changelog/` | 200 |

---

## Phase 6: 监控运维

### 查看服务状态

```bash
bash deployment/docker/monitor.sh status
```

### 实时日志

```bash
# 所有服务
docker compose -f docker-compose.offline-standalone.yml logs -f

# 单个服务
docker compose -f docker-compose.offline-standalone.yml logs -f backend
docker compose -f docker-compose.offline-standalone.yml logs -f worker
docker compose -f docker-compose.offline-standalone.yml logs -f db
```

### 资源使用

```bash
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
```

### 磁盘使用

```bash
docker system df
docker volume ls
```

---

## Phase 7: 升级与回滚

### 升级

```bash
# 1. 在新版本构建机器上重新执行 Phase 1-2
bash deployment/docker/build_and_export.sh
bash deployment/docker/validate_artifacts.sh

# 2. 传输新镜像到目标服务器
scp dist/*.tar user@target-server:/tmp/omni-desk-upgrade/

# 3. 在目标服务器上执行升级
cd /tmp/omni-desk-upgrade
bash deploy_offline.sh upgrade
```

升级流程（`deploy_offline.sh upgrade`）自动执行：

1. 加载新镜像
2. 执行数据库备份
3. 运行预检查迁移
4. 停止旧容器
5. 启动新容器
6. 执行数据库迁移
7. 健康检查

### 回滚

```bash
bash deploy_offline.sh rollback
```

回滚流程：

1. 停止当前容器
2. 加载上一个版本的镜像
3. 启动上一个版本
4. 可选恢复数据库备份

---

## 健康检查机制

### 各服务健康检查配置

| 服务 | 检查方式 | 间隔 | 超时 | 重试 | 启动延迟 |
|------|---------|------|------|------|---------|
| `db` | `pg_isready -U $USER -d $DB` | 10s | 5s | 5 | 60s |
| `redis` | `redis-cli -a $PASS ping` | 10s | 5s | 5 | 10s |
| `backend` | HTTP GET `/api/health/` | 15s | 5s | 3 | 30s |
| `frontend` | HTTP GET `/` (wget) | 15s | 5s | 3 | 10s |
| `worker` | `celery status` 命令 | 15s | 5s | 3 | 20s |

### 启动顺序

```
1. db ────────► 等待 healthy
2. redis ─────► 等待 healthy
3. backend ───► 等待 db + redis healthy
4. frontend ──► 等待 backend 启动
5. worker ────► 等待 db + redis healthy
```

---

## 常见问题排查

### 后端启动失败

**症状**: `docker compose logs backend` 显示 `sqlite3.OperationalError`

**原因**: Django 使用了 SQLite 而非 PostgreSQL

**解决**: 确认 `.env.production` 包含 `DJANGO_ENV=production`，且 `entrypoint.sh` 正确导出环境变量

```bash
docker compose exec backend env | grep DJANGO
# 应显示:
# DJANGO_SETTINGS_MODULE=omni_desk_backend.settings.production
# DJANGO_ENV=production
```

### Worker 健康检查失败

**症状**: `pgrep: command not found`

**原因**: Python slim 镜像不包含 procps 包

**解决**: 确保 `docker-compose.offline-standalone.yml` 中 worker 的 healthcheck 使用 Python subprocess 方式：

```yaml
test: ["CMD-SHELL", "python -c \"import subprocess; subprocess.run(['celery', '-A', 'omni_desk_backend', 'status'], check=True, capture_output=True, timeout=10)\" || exit 1"]
```

### 镜像标签指向旧版本

**症状**: 重建镜像后容器仍运行旧代码

**原因**: `:latest` 标签仍指向旧 image ID

**解决**:

```bash
docker images | grep omni-desk
docker tag omni-desk-backend-prod:v0.1.0 omni-desk-backend-prod:latest
docker compose -f docker-compose.offline-standalone.yml up -d --force-recreate
```

### 数据库连接失败

**症状**: `could not connect to server: Connection refused`

**排查**:

```bash
# 检查 db 服务是否 healthy
docker compose -f docker-compose.offline-standalone.yml ps db

# 检查网络连通性
docker compose exec backend python -c "import socket; s = socket.socket(); s.connect(('db', 5432)); print('OK'); s.close()"
```

### 前端 502 Bad Gateway

**症状**: 访问首页返回 502

**排查**:

```bash
# 检查 nginx 配置
docker compose exec frontend nginx -t

# 检查后端是否可达
docker compose exec frontend wget -qO- http://backend:8000/api/health/

# 查看 nginx 错误日志
docker compose exec frontend cat /var/log/nginx/error.log
```

---

## 环境变量参考

### `.env.production` 完整变量列表

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POSTGRES_DB` | `omni_desk` | 数据库名称 |
| `POSTGRES_USER` | `omni_desk` | 数据库用户 |
| `POSTGRES_PASSWORD` | (必须设置) | 数据库密码 |
| `REDIS_PASSWORD` | (必须设置) | Redis 密码 |
| `DJANGO_ENV` | `production` | Django 环境（必须为 production） |
| `DJANGO_SETTINGS_MODULE` | `omni_desk_backend.settings.production` | Django 设置模块 |
| `MINERU_API_KEY` | `offline-temp-key-not-for-external-use` | MinerU API 密钥（离线环境可留占位符） |
| `SECRET_KEY` | (必须设置) | Django 密钥 |
| `DEBUG` | `False` | 调试模式（生产必须 False） |

---

## 文件位置参考

```
deployment/docker/
├── build_and_export.sh          # Phase 1: 构建镜像
├── validate_artifacts.sh        # Phase 2: 验证产物
├── smoke_tests.sh               # Phase 5: 冒烟测试
├── monitor.sh                   # Phase 6: 监控
├── deploy_offline.sh            # Phase 4/7: 部署/升级/回滚
├── docker-compose.offline-standalone.yml  # 服务编排
├── .env.production              # 环境变量模板
├── VERSION                      # 当前版本号
└── CHANGELOG.md                 # 变更日志
```
