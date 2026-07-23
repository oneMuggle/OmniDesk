# OmniDesk Docker 部署指南

本文档详细介绍 OmniDesk 项目的 Docker 部署方案，涵盖开发环境、生产环境和离线部署。

## 目录

- [架构概述](#架构概述)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [环境配置](#环境配置)
- [开发环境部署](#开发环境部署)
- [生产环境部署](#生产环境部署)
- [离线/内网部署](#离线内网部署)
- [CI/CD 自动化部署](#cicd-自动化部署)
- [镜像构建详解](#镜像构建详解)
- [常见操作](#常见操作)
- [故障排查](#故障排查)

---

## 架构概述

OmniDesk 采用多容器 Docker 架构，通过 `docker-compose` 编排以下服务（**单 Nginx 入口**：Nginx 集成在前端容器内）：

| 服务 | 镜像 | 说明 |
|------|------|------|
| `db` | postgres:14.2 | PostgreSQL 数据库 |
| `redis` | redis:7-alpine | Redis 缓存/消息队列 |
| `backend` | omni-desk-backend | Django 后端应用 |
| `frontend` | omni-desk-frontend | React 前端应用 + 内置 Nginx（唯一 HTTP 入口） |
| `worker` | omni-desk-backend | Celery 异步任务处理 |

### 流量架构

```
用户请求
    │
    ▼
┌──────────────────┐
│  Frontend        │ :80  (内置 Nginx + React 静态)
└────┬─────────────┘
     │
     ├──────────────────┬──────────────────┐
     ▼                  ▼                  ▼
┌──────────────┐ ┌─────────────┐   ┌─────────────┐
│  Backend     │ │  React SPA  │   │  Django     │
│  Django      │ │  (静态构建) │   │  Static/    │
│  :8000       │ │             │   │  Media      │
└──────┬───────┘ └─────────────┘   └─────────────┘
       │
  ┌────┴────┐
  ▼         ▼
┌────────┐ ┌──────┐
│Postgres│ │ Redis│
└────────┘ └──────┘
```

> **架构说明**：早期版本使用独立 Nginx 容器 + 前端 Nginx 双层架构，已简化为单 Nginx 入口。所有路由规则集中在前端容器的 `omni_desk_frontend/nginx.conf` 中维护。

---

## 目录结构

```
deployment/
├── docker/
│   ├── docker-compose.yml              # 基础配置（所有环境共享）
│   ├── docker-compose.override.yml     # 开发环境覆盖（自动加载）
│   ├── docker-compose.prod.yml        # 生产环境覆盖
│   ├── docker-compose.build.yml       # 本地构建配置
│   ├── .env                            # 开发环境变量
│   ├── .env.production                 # 生产环境变量
│   ├── omni_desk_backend/              # 后端 Dockerfile
│   │   └── Dockerfile
│   ├── deploy_docker.sh               # 部署管理脚本
│   ├── build_and_export.sh            # 镜像打包脚本
│   ├── deploy_offline.sh              # 离线部署脚本
│   └── exported_images/               # 导出的镜像文件
└── deploy.sh                          # 旧版部署脚本
```

---

## 快速开始

### 前置条件

- Docker 20.10+
- Docker Compose 2.0+
- Git

### 1. 克隆项目

```bash
git clone https://github.com/onemuggle/omni-desk.git
cd omni-desk
```

### 2. 配置环境变量

```bash
cd deployment/docker
cp .env.production .env  # 生产环境
# 或
cp .env .env  # 开发环境
```

编辑 `.env` 文件，修改以下关键配置：

```env
# 数据库配置
POSTGRES_DB=omni_desk
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_secure_password

# Django 配置
SECRET_KEY=your-very-secure-secret-key-here
DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.com,server-ip

# CORS 配置
CORS_ALLOWED_ORIGINS=http://your-domain.com
```

### 3. 一键启动

```bash
# 开发环境
./deploy_docker.sh up

# 生产环境
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 4. 初始化数据库

```bash
./deploy_docker.sh migrate    # 数据库迁移
./deploy_docker.sh collectstatic  # 收集静态文件
```

### 5. 访问应用

| 服务 | 地址 |
|------|------|
| 前端应用 | http://localhost |
| 后端 API | http://localhost/api/ |
| Django Admin | http://localhost/admin/ |

---

## 环境配置

### 环境变量说明

#### .env（开发环境）

```env
# ============ 数据库 ============
POSTGRES_DB=omni_desk              # 数据库名称
POSTGRES_USER=user                 # 数据库用户
POSTGRES_PASSWORD=password         # 数据库密码
DB_HOST=db                          # Docker 网络内主机名
DB_PORT=5432                        # 数据库端口

# ============ Django ============
SECRET_KEY='django-insecure-your-default-secret-key-for-development'
DEBUG=True                         # 开发环境开启调试
ALLOWED_HOSTS=localhost,127.0.0.1  # 允许的主机

# ============ Redis ============
REDIS_HOST=redis
REDIS_PORT=6379

# ============ Celery ============
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# ============ CORS & CSRF ============
CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost,http://127.0.0.1
```

#### .env.production（生产环境）

```env
# 数据库
POSTGRES_DB=omni_desk
POSTGRES_USER=your_prod_user
POSTGRES_PASSWORD=your_very_secure_password
DB_HOST=db
DB_PORT=5432

# Django
SECRET_KEY='your-production-secret-key-must-be-changed'
DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.com,server-ip

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# CORS & CSRF（修改为实际域名）
CORS_ALLOWED_ORIGINS=https://your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com
```

### docker-compose 环境组合

| 场景 | 命令 | 加载文件 |
|------|------|----------|
| 开发 | `docker-compose up` | + `override.yml` |
| 生产 | `docker-compose -f .yml -f .prod.yml up` | - `override.yml` |
| 本地构建 | `docker-compose -f .yml -f .build.yml build` | + `override.yml` |

---

## 开发环境部署

开发环境特点：
- 代码通过 volume 挂载，实时热重载
- 前端开发服务器在容器内运行
- 更详细的日志输出

### 使用部署脚本

```bash
cd deployment/docker

# 启动所有服务（带构建）
./deploy_docker.sh up

# 查看日志
./deploy_docker.sh logs          # 全部日志
./deploy_docker.sh logs backend   # 后端日志

# 停止服务
./deploy_docker.sh down

# 重新构建
./deploy_docker.sh build
```

### 手动操作

```bash
cd deployment/docker

# 启动服务
docker-compose up --build

# 新终端执行迁移
docker-compose exec backend python manage.py migrate

# 创建超级用户
docker-compose exec backend python manage.py createsuperuser
```

### 访问开发服务

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8000/api/ |
| Django Admin | http://localhost:8000/admin/ |

---

## 生产环境部署

### 方式一：从镜像仓库部署（推荐）

适用于可访问互联网的生产服务器。

```bash
cd deployment/docker

# 1. 拉取最新镜像
docker-compose -f docker-compose.yml -f docker-compose.prod.yml pull

# 2. 启动服务
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 3. 初始化（如首次部署）
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python manage.py migrate
docker-compose -f docker-compose.prod.yml exec backend python manage.py collectstatic --noinput
```

### 方式二：使用部署脚本

```bash
cd deployment/docker

# 启动生产环境
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 方式三：手动指定镜像标签

```bash
cd deployment/docker

# 设置镜像标签（可以是 git commit hash）
export BACKEND_IMAGE_TAG=abc1234
export FRONTEND_IMAGE_TAG=abc1234

# 使用脚本部署
../../deployment/deploy.sh $BACKEND_IMAGE_TAG
```

### 生产环境 Nginx 配置

前端镜像内置生产 Nginx 配置（`omni_desk_frontend/nginx.conf`）：

```nginx
server {
    listen 80;
    client_max_body_size 20M;
    keepalive_timeout 65;

    # 静态文件（7天缓存）
    location /django-static/ {
        alias /usr/src/app/staticfiles/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # 媒体文件
    location /media/ {
        alias /usr/src/app/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # React SPA
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri /index.html;
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Django Admin
    location /django-admin/ {
        proxy_pass http://backend:8000/django-admin/;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Gzip 压缩
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
}
```

---

## 离线/内网部署

适用于无法访问互联网的内网服务器。

### 步骤 1：在有网环境打包镜像

```bash
cd deployment/docker

# 运行打包脚本，会构建并导出所有需要的镜像
./build_and_export.sh
```

脚本执行后，`exported_images/` 目录包含：
- `omni_desk_backend.tar` - 后端镜像
- `omni_desk_frontend.tar` - 前端镜像（含内置 Nginx）
- `postgres.tar` - PostgreSQL 镜像
- `redis.tar` - Redis 镜像

### 步骤 2：传输文件到内网服务器

需要传输的文件：
```
deployment/docker/
├── exported_images/          # 镜像 tar 包
├── docker-compose.yml       # 基础配置
├── docker-compose.prod.yml  # 生产配置
├── .env.production          # 环境变量（需根据内网修改）
└── deploy_offline.sh       # 离线部署脚本
```

### 步骤 3：在内网服务器部署

```bash
# 1. 进入部署目录
cd /opt/omni-desk-deployment

# 2. 确保 Docker 服务运行
sudo systemctl start docker

# 3. 添加执行权限
chmod +x deploy_offline.sh

# 4. 运行离线部署
./deploy_offline.sh
```

脚本自动完成：
- 从 tar 文件加载所有镜像
- 使用 docker-compose 启动服务

### 步骤 4：初始化（如首次部署）

```bash
# 数据库迁移
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python manage.py migrate

# 收集静态文件
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python manage.py collectstatic --noinput

# 创建管理员账号
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

---

## CI/CD 自动化部署

### GitHub Actions 工作流

#### 1. 构建并推送镜像 (`build-and-push-images.yml`)

推送到 `main` 分支时自动触发：

```yaml
触发条件:
  - push to main branch
  - pull_request to main branch
  - 手动触发 (workflow_dispatch)

流程:
  1. 测试阶段
     ├── 前端测试 (npm test)
     └── 后端测试 (pytest)
  
  2. 构建阶段
     ├── 构建后端镜像 (target: production)
     ├── 推送后端镜像 → ghcr.io/onemuggle/omni-desk-backend
     ├── 构建前端镜像
     └── 推送前端镜像 → ghcr.io/onemuggle/omni-desk-frontend
```

#### 2. 部署到 Windows 服务器 (`deploy-ssh-windows.yml`)

镜像构建成功后自动触发：

```yaml
触发条件:
  - build-and-push-images.yml 成功完成
  
流程:
  1. SSH 连接到 Windows 服务器
  2. 拉取最新代码
  3. 配置环境变量
  4. 拉取 Docker 镜像
  5. 启动服务
```

### 手动触发 CI/CD

```bash
# 通过 GitHub CLI 触发
gh workflow run build-and-push-images.yml --ref main

# 查看运行状态
gh run list --workflow=build-and-push-images.yml
```

---

## 镜像构建详解

### 后端多阶段构建

位置：`deployment/docker/omni_desk_backend/Dockerfile`

```dockerfile
# ============ Stage 1: Base ============
FROM python:3.11-slim-bullseye AS base

# 安装运行时依赖
RUN apt-get update && \
    apt-get install -y libpq5 build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# ============ Stage 2: Builder ============
FROM base AS builder

# 预编译生产依赖为 wheel
RUN pip wheel --wheel-dir=/wheelhouse -r requirements-prod.txt

# ============ Stage 3: Development ============
FROM base AS development

# 直接安装所有依赖（用于本地开发）
RUN pip install -r requirements.txt
COPY omni_desk_backend/ .
CMD ["python", "manage.py", "runserver"]

# ============ Stage 4: Production ============
FROM base AS production

# 创建非 root 用户
RUN addgroup --system app && adduser --system --group app

# 从 Builder 复制预编译的 wheel
COPY --from=builder /wheelhouse /wheelhouse
RUN pip install --no-index --find-links=/wheelhouse -r requirements-prod.txt

# 复制应用代码
COPY --chown=app:app omni_desk_backend/ .

# 设置入口脚本
RUN chmod +x ./entrypoint.sh

# 创建静态文件目录
RUN mkdir -p /usr/src/app/staticfiles && chown -R app:app /usr/src/app/staticfiles

USER app
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "omni_desk_backend.wsgi:application", "--bind", "0.0.0.0:8000"]
```

### 前端多阶段构建

位置：`omni_desk_frontend/Dockerfile`

```dockerfile
# ============ Stage 1: Development ============
FROM node:18-alpine AS development
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["npm", "start"]

# ============ Stage 2: Builder ============
FROM node:18-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .
RUN npm run build

# ============ Stage 3: Production ============
FROM nginx:stable-alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### 后端入口脚本

位置：`omni_desk_backend/entrypoint.sh`

```bash
#!/bin/sh
echo "Collecting static files..."
python manage.py collectstatic --noinput
exec "$@"
```

---

## 常见操作

### 服务管理

```bash
cd deployment/docker

# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart backend

# 查看服务状态
docker-compose ps
```

### 日志查看

```bash
# 实时查看所有日志
docker-compose logs -f

# 实时查看特定服务
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f worker

# 查看最近 100 行日志
docker-compose logs --tail=100 backend
```

### 数据库操作

```bash
# 执行迁移
docker-compose exec backend python manage.py migrate

# 创建迁移文件（开发时）
docker-compose exec backend python manage.py makemigrations

# 进入 Django shell
docker-compose exec backend python manage.py shell

# 创建超级用户
docker-compose exec backend python manage.py createsuperuser

# 导入导出数据
docker-compose exec -T backend python manage.py dumpdata > data.json
docker-compose exec -T backend python manage.py loaddata data.json
```

### 静态文件和媒体文件

```bash
# 收集静态文件
docker-compose exec backend python manage.py collectstatic --noinput

# 查看媒体文件目录
docker-compose exec backend ls -la /usr/src/app/media/
```

### 清理操作

```bash
# 删除未使用的镜像
docker image prune -f

# 删除停止的容器
docker container prune -f

# 完全清理（谨慎使用）
docker system prune -af --volumes
```

### Celery Worker 管理

```bash
# 查看 worker 日志
docker-compose logs -f worker

# 重启 worker
docker-compose restart worker

# 如需更多 worker，可扩展
docker-compose up -d --scale worker=3
```

---

## 故障排查

### 容器启动失败

```bash
# 1. 查看容器状态
docker-compose ps

# 2. 查看详细日志
docker-compose logs backend

# 3. 检查配置文件
docker-compose config

# 4. 重建特定服务
docker-compose build --no-cache backend
docker-compose up -d backend
```

### 数据库连接问题

```bash
# 1. 检查数据库容器
docker-compose ps db

# 2. 测试数据库连接
docker-compose exec db pg_isready -U user

# 3. 查看数据库日志
docker-compose logs db

# 4. 进入数据库容器
docker-compose exec db psql -U user -d omni_desk
```

### 权限问题

```bash
# 修改文件权限
docker-compose exec backend chown -R app:app /usr/src/app/

# 重建容器
docker-compose up -d --force-recreate backend
```

### 端口冲突

```bash
# 检查端口占用
netstat -tlnp | grep 80
netstat -tlnp | grep 8000
netstat -tlnp | grep 5432

# 修改 docker-compose.yml 中的端口映射
ports:
  - "8080:80"  # 改 80 为 8080
```

### 迁移失败

```bash
# 查看迁移状态
docker-compose exec backend python manage.py showmigrations

# 重置特定应用的迁移
docker-compose exec backend python manage.py migrate your_app zero
docker-compose exec backend python manage.py migrate your_app
```

### 静态文件 404

```bash
# 重新收集静态文件
docker-compose exec backend python manage.py collectstatic --noinput

# 检查静态文件目录
docker-compose exec backend ls -la /usr/src/app/staticfiles/
```

### 生产环境内存不足

```bash
# 限制容器内存
# 在 docker-compose.yml 中添加:
deploy:
  resources:
    limits:
      memory: 512M

# 重启服务
docker-compose down
docker-compose up -d
```

---

## 安全建议

### 生产环境必做

1. **修改默认密码**
   ```env
   POSTGRES_PASSWORD=<随机强密码>
   SECRET_KEY=<随机长字符串>
   ```

2. **关闭 DEBUG**
   ```env
   DEBUG=False
   ```

3. **配置 ALLOWED_HOSTS**
   ```env
   DJANGO_ALLOWED_HOSTS=your-domain.com
   ```

4. **配置 CORS**
   ```env
   CORS_ALLOWED_ORIGINS=https://your-domain.com
   ```

5. **使用环境变量管理密钥**
   不要将密钥直接写在 `.env` 文件中，使用 CI/CD 的 secret 功能。

---

## 附录

### 环境变量速查表

| 变量 | 说明 | 开发默认值 | 生产建议 |
|------|------|------------|----------|
| `POSTGRES_DB` | 数据库名 | omni_desk | omni_desk |
| `POSTGRES_USER` | 数据库用户 | user | 独立用户 |
| `POSTGRES_PASSWORD` | 数据库密码 | password | 强随机密码 |
| `SECRET_KEY` | Django 密钥 | insecure | 强随机密钥 |
| `DEBUG` | 调试模式 | True | False |
| `DJANGO_ALLOWED_HOSTS` | 允许主机 | localhost | 域名/IP |
| `REDIS_HOST` | Redis 主机 | redis | redis |
| `CELERY_BROKER_URL` | Celery broker | redis://... | redis://... |

### 常用端口

| 端口 | 服务 | 说明 |
|------|------|------|
| 80 | Nginx/Frontend | 主入口 |
| 8000 | Backend | API 端口 |
| 5432 | PostgreSQL | 数据库 |
| 6379 | Redis | 缓存 |

### 相关资源

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [Django 部署指南](https://docs.djangoproject.com/en/stable/howto/deployment/)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
