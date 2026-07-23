# 离线部署

## 1. 概述

适用于无外网访问的内部网络（air-gapped）环境。所有镜像通过 `.tar` 文件离线传输。

## 2. 架构

```
  Port 80 ──► frontend(:80) → backend(内部)
              db(:5432)  redis(:6379)  worker
```

数据卷: postgres_data, redis_data, static_volume, media_volume, backup_volume

## 3. 部署步骤

### Phase 1: 构建镜像（有外网）
```bash
cd deployment/docker && bash build_and_export.sh
```

产物在 `deployment/docker/dist/`。

### Phase 2: 验证
```bash
bash validate_artifacts.sh
```

### Phase 3: 传输
U 盘/SCP/完整打包。

### Phase 4: 离线部署
```bash
bash deploy_offline.sh start
```

### Phase 5: 冒烟测试
健康检查(200)、未授权(401)、首页(200)、登录(200)、版本API(200)。

## 4. 升级与回滚

```bash
bash deploy_offline.sh upgrade
bash deploy_offline.sh rollback
```

## 5. 关键环境变量

| 变量 | 说明 |
|------|------|
| `POSTGRES_DB/USER/PASSWORD` | 数据库配置 |
| `DB_HOST/DB_PORT` | Docker 内部 service 名（db / 5432） |
| `REDIS_PASSWORD` | Redis 密码 |
| `DJANGO_ENV=production` | 必须为 production |
| `DEBUG=False` | 生产必须 False |
| `USE_HTTPS` | `false`(纯 HTTP,默认)/ `true`(启用 HTTPS 全套加固) |
| `MINERU_API_KEY` | 可选,留空 = 文档解析功能禁用 |
| `BACKEND_IMAGE_TAG` / `FRONTEND_IMAGE_TAG` | semver tag,默认 `v0.2.0` |

## 6. 三层一致性约束(2026-06 新增)

`docs/plans/2026-06-03_docker-deployment-three-layer-assurance.md` 已实施并验证。

### 6.1 镜像命名统一
- **生产/GHCR 镜像名**: `ghcr.io/onemuggle/omni-desk-{backend,frontend}:v{VERSION}`
- **离线镜像 tag**: `omni-desk-{backend,frontend}-prod:v{VERSION}`(本地名)
- **自动 retag**: `build_and_export.sh` 在 docker save 前同时打 GHCR 全名 tag,让离线包加载后 compose 直接用 GHCR 名

### 6.2 Python 3.10 统一
- Dockerfile base: `python:3.10-slim-bookworm`
- CI workflow: `python-version: '3.10'`
- 本地 conda 环境: `omni_desk` 环境
- 锁文件 `requirements-prod.txt` / `requirements.txt` 用 pip-tools 7.5+ 在 Py3.10 重新生成
- **不再使用 :latest** — 严禁在生产中用 latest tag

### 6.3 镜像打包统一
- `build_and_export.sh` 自动给镜像同时打 4 个 tag: `v{VERSION}` / `latest` / `develop` / `sha-*`
- 镜像保存/导出用 `BACKEND_IMAGE` / `FRONTEND_IMAGE` (本地名,避免 GHCR 路径在 docker save 中被误解析)
- 部署时 `BACKEND_IMAGE_TAG` / `FRONTEND_IMAGE_TAG` 控制具体使用的 tag

### 6.4 env 模板统一
- **唯一模板**: `deployment/docker/.env.production.example`
- 已删除冗余的 `.env.production.template` 和 `.env.production.defaults`
- 所有脚本 (`build_and_export.sh` / `package_offline_bundle.sh` / `verify.sh`) 都引用 `.env.production.example`
- 模板含详细占位符说明: `<CHANGE-TO-...>` / `<GENERATE-...>` / `<YOUR_...>` 风格

### 6.5 部署流程验证(2026-06-04 端到端)
- **L1 本地开发**: docker compose dev 5 服务 UP + pytest 475 通过 + jest 328 通过 + vite build 21s
- **L2 GitHub 自动化**: CI 4m10s success + Run Tests 9m27s success + Deploy Test 12s success
- **L3 服务器部署**: 离线包加载后 5 服务全 healthy + `/api/health/` 返回 `{"status":"ok","database":"ok"}` + upgrade/rollback 流程全过

## 7. 常见问题

### 7.1 MINERU_API_KEY 缺失导致启动失败
**原因**: 使用了阶段 1.2 修复前打包的旧镜像,production.py 仍强校验 MINERU
**解法**:
- 选项 A: 升级到新版本镜像(已合并阶段 1.2 修复)
- 选项 B(临时): 在 .env.production 中加 `MINERU_API_KEY=<任意非空非 placeholder 值>`

### 7.2 db volume 残留旧数据导致密码不匹配
**现象**: backend 日志持续 `password authentication failed for user "omni_desk_user"`
**原因**: PostgreSQL 14 启动时如果 data 目录已有数据,不会用 `POSTGRES_PASSWORD` env 重置已有用户密码
**解法**:
```bash
# 在 db 容器内 ALTER USER 重置密码
docker exec -e PGPASSWORD=<旧密码或新密码> <db容器> psql -U omni_desk_user -d omni_desk \
  -c "ALTER USER omni_desk_user WITH PASSWORD '<新密码>';"
# 然后 backend/worker 自动恢复(entrypoint.sh 持续重试)
```

### 7.3 frontend 容器 vite 启动失败
**原因**: docker-compose.yml 中 `node_modules_volume`(旧 named volume)残留旧 node_modules,与新 image 不一致
**解法**: `docker compose down` 不删 volumes,改用匿名 volume (已修复:部署脚本中 `volumes: [/app/node_modules]` 匿名方式)

### 7.4 端口 80 已被占用(nginx / traefik 等),frontend 容器启动失败
**现象**: `compose-frontend-1` 报 `Error response from daemon: failed to bind host port 0.0.0.0:80/tcp: address already in use`
**原因**: 离线包 compose 中 frontend 默认 `ports: ["80:80"]`,与已有服务(本机 traefik/ingress/nginx)冲突
**解法 A(临时,本地测试)**: 在 `compose/` 加 `docker-compose.override.yml`,把 frontend 端口改到 18080:
```yaml
services:
  frontend:
    ports: !reset []   # 清空 offline.yml 的 ports 列表
    image: ghcr.io/onemuggle/omni-desk-frontend:v0.7.0-beta.3
    pull_policy: never
    command: ["nginx", "-g", "daemon off;"]
    networks: [omni_desk]
    # ... (其余字段复制 offline.yml 的 frontend 完整定义)
```
然后用 `docker compose -f compose/docker-compose.offline.yml -f compose/docker-compose.override.yml --env-file compose/.env.production up -d` 启动(注意:`deploy.sh` 默认不会自动加载 override,需显式加 `-f`)
**解法 B(生产)**: 用独立 nginx/Caddy 反代到容器内部端口,或调整 infra 让 frontend 独占 80
**关键点**: docker compose 对 `ports` 列表默认**追加**而非替换,直接 override `ports: ["18080:80"]` 会同时绑 80 + 18080,仍冲突;必须用 `!reset []` 清空后再定义

### 7.5 阶段 1-4 计划文件
- 已删除: `docs/plans/2026-06-03_docker-deployment-three-layer-assurance.md`
- 实施详情见各 commit 与本章节 6.x 节

详细指南见 [部署指南](02-deployment-guide.md)。
