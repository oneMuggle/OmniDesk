# Railway 部署指南

> 适用于 OmniDesk 项目的免费云部署方案

## 概述

Railway 是一个现代化的云平台，提供 $5/月的免费额度，足以运行一个 Django + PostgreSQL + Redis 的小型应用。

| 组件 | Railway 支持 | 当前项目状态 |
|------|-------------|-------------|
| Django + Gunicorn | ✅ 原生支持 | ✅ 已有 Dockerfile |
| PostgreSQL | ✅ 一键添加 | ✅ 已配置 |
| Redis | ✅ 一键添加 | ✅ 已配置 |
| Celery Worker | ⚠️ 需额外服务 | 需配置 |

---

## 1. 准备工作

### 1.1 注册 Railway 账号

访问 [railway.app](https://railway.app) 注册账号，推荐使用 GitHub 登录。

### 1.2 安装 Railway CLI

```bash
npm i -g @railway/cli
railway login
```

### 1.3 准备环境变量

在项目根目录创建 `.env.railway` 文件：

```bash
# Django 核心
SECRET_KEY=<生成一个强密钥>
DEBUG=False
DJANGO_ENV=production
ALLOWED_HOSTS=<你的域名>

# 数据库 (Railway 自动填充)
POSTGRES_DB=<数据库名>
POSTGRES_USER=<用户名>
POSTGRES_PASSWORD=<密码>
DB_HOST=<Railway 提供的 hostname>
DB_PORT=5432

# Redis (Railway 自动填充)
REDIS_URL=<Railway 提供的 redis 连接>

# Celery
CELERY_BROKER_URL=<Redis URL>
CELERY_RESULT_BACKEND=<Redis URL>

# CORS
CORS_ALLOWED_ORIGINS=<前端域名>
CSRF_TRUSTED_ORIGINS=<前端域名>

# 可选：OLLAMA (需要外部服务)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_NAME=llama2

# 可选：超级管理员
SUPERUSER_NAME=admin
SUPERUSER_EMAIL=admin@example.com
SUPERUSER_PASSWORD=<管理密码>
```

---

## 2. Railway 项目初始化

### 2.1 创建 Railway 项目

```bash
# 方法 A：从 Railway 模板一键创建（推荐）
railway init --template django

# 方法 B：链接现有 GitHub 仓库
railway init
```

### 2.2 添加数据库服务

```bash
# 在 Railway dashboard 或 CLI 中添加 PostgreSQL
railway add --plugin postgresql

# 添加 Redis
railway add --plugin redis
```

### 2.3 配置环境变量

```bash
# 设置环境变量
railway variables set SECRET_KEY=<your-secret-key>
railway variables set DEBUG=False
railway variables set DJANGO_ENV=production

# 从 Railway 获取数据库连接信息并设置
railway variables set POSTGRES_DB=${{Postgres.PGDATABASE}}
railway variables set POSTGRES_USER=${{Postgres.PGUSER}}
railway variables set POSTGRES_PASSWORD=${{Postgres.PGPASSWORD}}
railway variables set DB_HOST=${{Postgres.PGHOST}}
railway variables set DB_PORT=${{Postgres.PGPORT}}

# Redis
railway variables set REDIS_URL=${{Redis.REDISURL}}
railway variables set CELERY_BROKER_URL=${{Redis.REDISURL}}
railway variables set CELERY_RESULT_BACKEND=${{Redis.REDISURL}}

# 前端域名（部署后替换）
railway variables set ALLOWED_HOSTS=<your-app>.railway.app
railway variables set CORS_ALLOWED_ORIGINS=https://<your-frontend>.railway.app
railway variables set CSRF_TRUSTED_ORIGINS=https://<your-frontend>.railway.app
```

---

## 3. 部署后端

### 3.1 修改 Dockerfile（可选）

当前项目的 Dockerfile 已经很接近 Railway 格式，但需要确保：

1. **入口脚本兼容**：当前 `entrypoint.sh` 已兼容 ✅
2. **端口配置**：Railway 使用 `PORT` 环境变量

确保 Dockerfile 中的端口设置：

```dockerfile
# Railway 使用 PORT 环境变量
EXPOSE 8000
CMD ["gunicorn", "omni_desk_backend.wsgi:application", "--bind", "0.0.0.0:8000"]
```

### 3.2 部署命令

```bash
# 直接部署当前目录
railway up

# 或部署特定服务
railway up --service backend
```

### 3.3 验证部署

```bash
# 查看日志
railway logs

# 获取部署 URL
railway domain
```

---

## 4. 部署前端

### 4.1 构建 React 前端

```bash
cd omni_desk_frontend
npm run build
```

### 4.2 部署到 Railway

```bash
# 创建静态站点服务
railway add --plugin static

# 部署静态文件
railway up --service frontend
```

或者使用 Cloudflare Pages 托管前端（免费）：

1. 连接 GitHub 仓库到 Cloudflare Pages
2. 构建命令：`npm run build`
3. 输出目录：`omni_desk_frontend/build`

---

## 5. Celery Worker 部署

Railway 支持多服务部署，需要单独部署 Celery Worker：

### 5.1 创建 Worker 服务

```dockerfile
# Railwayfile.worker
{
  "build": {
    "builder": "DOCKERFILE",
    "dockerfile": "deployment/docker/omni_desk_backend/Dockerfile"
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10,
    "command": "celery -A omni_desk_backend worker -l info"
  }
}
```

### 5.2 部署 Worker

```bash
railway up --service worker
```

---

## 6. 完整架构

```
┌─────────────────────────────────────────────────────┐
│                    Railway                          │
│                                                     │
│  ┌─────────────┐    ┌─────────────┐                │
│  │   Backend   │    │   Worker    │                │
│  │   (Django)  │    │  (Celery)   │                │
│  │  :8000      │    │             │                │
│  └──────┬──────┘    └──────┬──────┘                │
│         │                  │                        │
│  ┌──────┴──────────────────┴──────┐                │
│  │        Database & Cache         │                │
│  │  PostgreSQL    │    Redis      │                │
│  └─────────────────────────────────┘                │
│                                                     │
└─────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│              Cloudflare Pages                        │
│                  (Frontend)                         │
└─────────────────────────────────────────────────────┘
```

---

## 7. 常见问题

### Q1: Railway 免费额度够用吗？

| 资源 | 免费限制 | 项目消耗 |
|------|----------|----------|
| 计算 | $5/月 | ~$2-3/月 |
| PostgreSQL | $5/月 | ~$1/月 |
| Redis | $1/月 | ~$0.5/月 |
| **总计** | **$5/月** | **~$4-5/月** |

> 刚好在免费额度内。

### Q2: 冷启动时间？

- **Railway**: 30-60 秒（首次请求）
- **Render**: 30-60 秒
- **建议**: 使用 UptimeRobot 定期 ping 保持活跃

### Q3: 如何配置自定义域名？

```bash
railway domain set yourdomain.com
```

然后在 DNS 服务商添加 CNAME 记录指向 Railway 提供的域名。

### Q4: 当前项目需要大改吗？

| 文件 | 状态 |
|------|------|
| Dockerfile | ✅ 兼容，无需修改 |
| entrypoint.sh | ✅ 兼容，无需修改 |
| settings/production.py | ✅ 已有，只需配置环境变量 |
| docker-compose.yml | 可保留，Railway 不强制使用 |

---

## 8. 快速开始命令

```bash
# 1. 安装 CLI 并登录
npm i -g @railway/cli
railway login

# 2. 初始化项目
cd /home/fz/project/InsiteWebsite
railway init

# 3. 添加数据库
railway add --plugin postgresql
railway add --plugin redis

# 4. 设置环境变量
railway variables set SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(50))")
railway variables set DEBUG=False
railway variables set DJANGO_ENV=production

# 5. 部署
railway up

# 6. 查看状态
railway status
railway logs
```

---

## 9. 替代方案

如果 Railway 不适合，可以考虑：

| 平台 | 免费限制 | 特点 |
|------|----------|------|
| **Render** | 750小时/月 | UI 干净，PostgreSQL 免费 90 天 |
| **Fly.io** | 3 台 VM | 全球部署，需手动配置 |
| **Dino云** | 国内访问快 | 需备案 |

---

## 10. 注意事项

1. **数据库初始化**：首次部署后需要运行 migrations
   ```bash
   railway run python manage.py migrate
   ```

2. **静态文件**：Railway 不持久化，需要配置 S3 或 Cloudflare R2

3. **密钥安全**：不要将 `.env` 文件提交到 Git

---

> 文档更新时间：2026-04-22
