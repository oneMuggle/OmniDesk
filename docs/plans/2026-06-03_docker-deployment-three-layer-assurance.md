# Docker 部署三层保障方案

> 计划编号：`2026-06-03_docker-deployment-three-layer-assurance`
> 创建日期：2026-06-03
> 计划状态：**待用户确认**（按 `CLAUDE.md` Plan-First Rule，未经批准不进入实施）
> 服务器目标：Ubuntu 22.04 LTS
> 本机环境：Ubuntu（与服务器一致）

---

## 一、背景与目标

OmniDesk 当前已具备 Docker 化部署能力（4 个 compose 文件 + Dockerfile + 多套 .env 模板 + GHCR 发布流水线 + 离线打包脚本），但调研发现 **23 个配置不一致或潜在缺陷**（详见第三节）。本方案的目标是确保以下三层都能稳定通过：

| 层级 | 入口 | 成功标准 |
|------|------|---------|
| L1 本地开发 | `docker compose up -d`（或 `npm start` + `python manage.py runserver`） | 前后端可访问、热重载工作、API 通畅、所有测试通过 |
| L2 GitHub 自动化 | push 到 `main` / `develop` → workflows | `ci-test.yml`、`build-and-push-images.yml`、`deploy-test.yml` 全绿 |
| L3 Ubuntu 22.04 服务器部署 | `docker compose -f docker-compose.offline-standalone.yml up -d` | 健康检查通过、80 端口可访问、API/Admin/静态资源/媒体均工作、Celery worker 运行、数据持久化 |

---

## 二、涉及的文件与模块

### 后端
- `omni_desk_backend/entrypoint.sh`
- `omni_desk_backend/omni_desk_backend/settings/production.py`
- `omni_desk_backend/omni_desk_backend/settings/base.py`（如需引入 `SECURE_PROXY_SSL_HEADER`）
- `omni_desk_backend/requirements-prod.txt`（重新 pip-compile）
- `deployment/docker/omni_desk_backend/Dockerfile`

### 前端
- `omni_desk_frontend/Dockerfile`
- `omni_desk_frontend/nginx.conf`
- `omni_desk_frontend/package.json`（`dev` 脚本加 `--host`）
- `omni_desk_frontend/vite.config.js`(确认 server.host)

### 部署
- `deployment/docker/docker-compose.yml`(dev)
- `deployment/docker/docker-compose.prod.yml`(GHCR 生产)
- `deployment/docker/docker-compose.offline.yml`(离线，叠加层)
- `deployment/docker/docker-compose.offline-standalone.yml`(离线独立)
- `deployment/docker/.env.production.example`
- `deployment/docker/.env.production.template`
- `deployment/docker/.env.production.defaults`
- `deployment/docker/.env.example`
- `deployment/docker/deploy_offline.sh`
- `deployment/docker/build_and_export.sh`
- `deployment/docker/deploy_tests.sh`

### CI/CD
- `.github/workflows/ci.yml`
- `.github/workflows/ci-test.yml`
- `.github/workflows/ci-develop.yml`
- `.github/workflows/build-and-push-images.yml`
- `.github/workflows/deploy-test.yml`

### 文档
- `CLAUDE.md`(更新过时描述)
- `docs/technical/`(新增部署章节)

---

## 三、风险评估清单(已识别的 23 个问题)

### CRITICAL(必须修复，否则三层均阻塞)

| ID | 问题 | 影响层级 | 现象 |
|----|------|---------|------|
| C1 | `entrypoint.sh` 用 `POSTGRES_HOST`，`production.py` 用 `DB_HOST` | L3 | 数据库连接等待逻辑回退到默认 'db'，若服务名变化或外部 PG 必失败 |
| C2 | `production.py` 强制要求 `MINERU_API_KEY`，但 `.env.production.example` 缺该字段 | L2 + L3 | 按文档操作后必触发 `ImproperlyConfigured`，容器不停重启 |
| C3 | `ci.yml` 与 `ci-test.yml` 重复运行测试且参数冲突(Node 20 vs 22、覆盖率阈值不同) | L2 | CI 资源浪费，结果可能互相矛盾 |
| C4 | `production.py` 强制 `CSRF_COOKIE_SECURE = True` / `SESSION_COOKIE_SECURE = True`，但 nginx 仅提供 HTTP 80 | L3 | 用户登录后 cookie 不下发，认证立即断开 |
| C5 | `deploy-test.yml` 通过 `cp .env.production.example .env.production` 创建测试配置时缺 `MINERU_API_KEY`，且被 `continue-on-error: true` 掩盖 | L2 | Deploy Test 实际从未真正成功，问题被屏蔽 |

### HIGH(影响交付质量)

| ID | 问题 | 影响层级 | 备注 |
|----|------|---------|------|
| H1 | `CLAUDE.md` 关于 CRA / package.json proxy 的描述已过时(项目已迁移到 Vite 5.4) | 全部 | 后续 AI/开发者会按过时指引犯错 |
| H2 | 前端 dev 阶段 `npm start` → vite dev server 默认仅监听 `localhost`，容器外无法访问 | L1 | docker-compose dev 模式失效(除非 vite.config 的 server.host 设为 true) |
| H3 | `requirements-prod.txt` 头注释为 Python 3.13，但 Dockerfile 用 python:3.11 | L2 + L3 | pip wheel 阶段可能失败或引入不兼容依赖 |
| H4 | 镜像命名割裂：CI 推 `ghcr.io/onemuggle/omni-desk-backend`，离线 standalone 用 `omni-desk-backend-prod` | L3 | 用户从 GHCR 拉镜像后无法直接使用离线 compose |
| H5 | 不同 compose 文件 tag 策略不一致(变量化 / v0.2.0 硬编码 / latest) | L3 | 升级与回滚混乱 |
| H6 | `docker-compose.prod.yml` 中 db/redis/backend/worker 未明确加入 `omni_desk` 网络 | L3 | 依赖 compose 隐式合并默认网络，可读性差 |
| H7 | `build-and-push-images.yml` 不打 semver tag，但 `.env.production.template` 默认 `BACKEND_IMAGE_TAG=v1.0.0` | L3 | 用户拉取 `v1.0.0` 会 404 |

### MEDIUM(建议修复)

| ID | 问题 | 影响层级 |
|----|------|---------|
| M1 | `requirements-prod.txt` 应在 python:3.11 容器内重新 `pip-compile` | L2 + L3 |
| M2 | 前端 dev Dockerfile 缺 `HEALTHCHECK` | L1 |
| M3 | Backend production 镜像缺 `HEALTHCHECK`(依赖 compose) | L3 |
| M4 | `.env.production` 实际值文件被 root 拥有且看起来已被 git 追踪过(需确认) | 全部 |
| M5 | `entrypoint.sh` 用 `setpriv`，但 python:3.11-slim-bookworm 不预装 `util-linux` 的完整 setpriv 工具 | L3 |
| M6 | `docker-compose.yml` (dev) 的 frontend `node_modules_volume` 在跨平台/重建时易失同步 | L1 |
| M7 | nginx CSP 中 `connect-src 'self'` 在引入 Ollama/外部 API 时会拦截 | L3 |

### LOW(可在后续迭代处理)

| ID | 问题 |
|----|------|
| L1 | `deploy_offline.sh` 默认 `latest` tag，与 CLAUDE.md "禁止 latest" 矛盾 |
| L2 | `scripts/generate-routes.js` 只在 `npm run build` 触发(依赖 prebuild 钩子)，未集成为 vite 插件 |
| L3 | `desktop_notifier_ci.yml` 未在本方案审视范围内 |
| L4 | `.env.production.defaults` / `.env.production.template` / `.env.production.example` 三套模板字段不一致 |

---

## 四、技术方案

### 4.1 设计原则

1. **L1 → L2 → L3 行为等价**：本地 `docker compose build` 出的镜像必须能在 GitHub Actions 上构建成功，再被服务器加载即可运行。任何在某一层"特殊处理"的逻辑都必须有理由。
2. **单一事实源(Single Source of Truth)**：
   - 环境变量名一套(统一 `DB_HOST` 而非 `POSTGRES_HOST`)
   - 镜像名一套(统一 `ghcr.io/onemuggle/omni-desk-{backend,frontend}`，离线 retag 后保留同名)
   - compose 文件分层清晰：`docker-compose.yml`(base/dev) + `prod.yml`(GHCR 拉取覆盖) + `offline.yml`(本地镜像覆盖)，淘汰 `offline-standalone.yml`，或仅作为兼容入口
3. **失败优先(Fail Fast)**：所有强制配置在容器启动时校验并明确报错，移除 `continue-on-error: true` 掩盖错误
4. **离线兜底**：所有镜像必须可通过 `docker save / docker load` 完整搬运，禁止任何运行时网络下载
5. **可观测性**：每个服务都有 healthcheck，部署脚本输出每一步进度

### 4.2 关键改动

#### 4.2.1 修复后端启动链路(C1 + C2 + C4)

```diff
- entrypoint.sh: host=os.environ.get('POSTGRES_HOST', 'db')
+ entrypoint.sh: host=os.environ.get('DB_HOST', 'db')

- production.py: 强制 MINERU_API_KEY 非空且非占位符
+ production.py: MINERU_API_KEY 改为可选(启用文档解析功能时才检查)

# 新增 SSL_PROXY 头识别(让 Django 知道 nginx 已终结 TLS，或在 HTTP 部署下放宽 cookie)
+ production.py: 引入 USE_HTTPS 环境变量，控制 *_COOKIE_SECURE
+ production.py: SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

#### 4.2.2 统一 CI 工作流(C3 + C5)

- 保留 `ci-test.yml`(覆盖 main/develop/test，输出 coverage artifact)
- 保留 `build-and-push-images.yml`(仅 main/develop 推镜像)
- 保留 `deploy-test.yml` 但移除 `continue-on-error`，让真实问题暴露
- **删除** `ci.yml`(与 ci-test.yml 重复，且阈值不同)
- **删除** `ci-develop.yml` 或合并为 `ci-test.yml` 的 matrix
- Node 版本统一为 **20**(与前端 Dockerfile 一致)

#### 4.2.3 修复前端 dev 容器(H2)

```diff
# vite.config.js
  server: {
    port: 3000,
+   host: true,   // = '0.0.0.0'，允许容器外访问
    proxy: { ... }
  }

# Dockerfile(development stage)
- CMD ["npm", "start"]
+ CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

#### 4.2.4 统一镜像命名(H4 + H5 + H7)

| 用途 | 镜像名 | tag 来源 |
|------|--------|---------|
| GHCR 发布 | `ghcr.io/onemuggle/omni-desk-backend` | `latest`/`develop`/`sha`/**新增 `v{VERSION}`** |
| GHCR 发布 | `ghcr.io/onemuggle/omni-desk-frontend` | 同上 |
| 离线包 | 同名镜像，通过 `docker save` 导出 | semver |

`build-and-push-images.yml` 新增 tag：
```yaml
type=raw,value=v${{ steps.read_version.outputs.VERSION }},enable={{is_default_branch}}
```
其中 `read_version` 步骤读 `deployment/docker/VERSION`。

#### 4.2.5 重新生成 requirements-prod.txt(H3 + M1)

```bash
# 在 python:3.11-slim-bookworm 镜像中执行
docker run --rm -v $(pwd):/work -w /work python:3.11-slim-bookworm bash -c "
  apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev &&
  pip install pip-tools &&
  pip-compile -o requirements-prod.txt requirements.in &&
  pip-compile -o requirements.txt requirements-dev.in
"
```

#### 4.2.6 网络与服务名显式化(H6)

`docker-compose.prod.yml` 中每个 service 都明确 `networks: [omni_desk]`，杜绝隐式合并。

#### 4.2.7 .env 模板统一(L4)

合并三个模板为一个 `.env.production.example`(带完整字段 + 注释)，删除 `.defaults` 与 `.template`；`deploy_offline.sh` 启动前校验所有必填项。

#### 4.2.8 文档更新(H1)

`CLAUDE.md` 修订：
- "React 18.3 via CRA" → "React 18.3 via Vite 5.4"
- "frontend proxy: package.json 有 proxy 字段" → "vite.config.js 的 server.proxy 配置"
- "npm run build 自动运行 generate-routes.js" → 标注通过 `prebuild` npm 钩子触发
- Backend Dockerfile 路径修正为 `deployment/docker/omni_desk_backend/Dockerfile`

新增 `docs/technical/05-deployment-guide.md`(合并现有 `deployment/docker/DEPLOYMENT_GUIDE*.md` 内容)。

### 4.3 数据流与端口图

```
                    [浏览器 / Win7 Chrome 109]
                              │
                              ▼ HTTP :80
              ┌───────────────────────────────┐
              │  nginx (frontend container)   │
              │  - /         → 静态 React 文件│
              │  - /api/     → backend:8000   │
              │  - /admin/   → backend:8000   │
              │  - /media/   → backend:8000   │
              │  - /django-static/ → backend:8000│
              └────────────┬──────────────────┘
                           │
                           ▼ (docker network: omni_desk)
              ┌───────────────────────────────┐
              │  backend (Gunicorn :8000)     │
              │  Django app                   │
              └──┬────────────┬───────────────┘
                 │            │
                 ▼            ▼
        ┌────────────┐  ┌─────────────┐
        │ db :5432   │  │ redis :6379 │
        │ Postgres14 │  │ + password  │
        └────────────┘  └─────┬───────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ worker (Celery)  │
                    │ 同 backend 镜像   │
                    └──────────────────┘

宿主机仅暴露 :80(HTTP)。
若启用 HTTPS：nginx 443 + 自签证书或反向代理终结 TLS。
```

---

## 五、实施步骤

> 实施按"修复 → 验证 → 推送 → 服务器演练"四阶段串行进行，每阶段必须验证通过才进入下一步。

### 阶段 1：本地修复(L1 基础)

- [ ] **1.1** 修复 `entrypoint.sh`：`POSTGRES_HOST` → `DB_HOST`
- [ ] **1.2** 修复 `production.py`：`MINERU_API_KEY` 改可选 + 引入 `USE_HTTPS` 控制 `*_COOKIE_SECURE` + 加 `SECURE_PROXY_SSL_HEADER`
- [ ] **1.3** 修复 `vite.config.js`：`server.host = true`
- [ ] **1.4** 修复前端 Dockerfile development stage：`CMD` 改为 `npm run dev -- --host 0.0.0.0`
- [ ] **1.5** 重新 pip-compile `requirements-prod.txt`(在 python:3.11 容器内)
- [ ] **1.6** 本地验证：`docker compose up -d`，访问 http://localhost:3000、http://localhost:8000/api/health/，运行 `pytest --ds=omni_desk_backend.settings.test`、`npm test`

### 阶段 2：CI 工作流统一(L2 基础)

- [ ] **2.1** 删除 `ci.yml`(与 ci-test.yml 重复)
- [ ] **2.2** 合并 `ci-develop.yml` 的 lint 步骤到 `ci-test.yml`
- [ ] **2.3** `build-and-push-images.yml` 增加 semver tag(读取 VERSION 文件)
- [ ] **2.4** `deploy-test.yml` 移除 `continue-on-error: true`，补全 `MINERU_API_KEY=skip`
- [ ] **2.5** `.env.production.example` 增加 `MINERU_API_KEY=` 占位
- [ ] **2.6** 三个 .env 模板合并为一个
- [ ] **2.7** 本地用 `act` 工具或推送到 `develop` 分支验证 CI 全绿

### 阶段 3：镜像与 compose 统一(L3 基础)

- [ ] **3.1** 离线 compose 文件统一镜像名为 `ghcr.io/onemuggle/omni-desk-{backend,frontend}`(与 GHCR 一致，docker save 时自然保留)
- [ ] **3.2** `docker-compose.prod.yml` 明确每个服务的 `networks: [omni_desk]`
- [ ] **3.3** 所有 compose 文件统一使用 `${BACKEND_IMAGE_TAG:?}` / `${FRONTEND_IMAGE_TAG:?}`
- [ ] **3.4** 淘汰 `docker-compose.offline-standalone.yml`(或保留为兼容入口，添加 deprecation 警告)
- [ ] **3.5** `deploy_offline.sh` 改用 `docker-compose.yml + docker-compose.offline.yml` 叠加方式
- [ ] **3.6** 更新 `build_and_export.sh`：导出镜像时使用 GHCR 完整名

### 阶段 4：服务器演练(L3 验收)

- [ ] **4.1** 在干净的 Ubuntu 22.04 测试机上：安装 docker + docker compose plugin
- [ ] **4.2** 把 `omnidesk-offline-v0.2.x.tar.gz` 拷贝到服务器
- [ ] **4.3** 执行 `./deploy_offline.sh start`，观察 pre_deploy_check 全 PASS
- [ ] **4.4** 验证健康检查：`docker compose ps` 所有服务 healthy
- [ ] **4.5** 浏览器访问 http://<服务器IP>/，登录/Admin/媒体/API 全部 OK
- [ ] **4.6** 执行 `./deploy_offline.sh upgrade` 模拟升级流程
- [ ] **4.7** 执行 `./deploy_offline.sh rollback` 验证回滚

### 阶段 5：文档与归档

- [ ] **5.1** 更新 `CLAUDE.md`(Vite 替换 CRA、Dockerfile 路径修正、CI 工作流清单更新)
- [ ] **5.2** 新增 `docs/technical/05-deployment-guide.md`
- [ ] **5.3** 更新 `docs/technical/README.md` 总览章节目录
- [ ] **5.4** 删除本计划文件 `docs/plans/2026-06-03_docker-deployment-three-layer-assurance.md`

---

## 六、验收标准(DoD)

| 层级 | 验收命令 / 操作 | 预期结果 |
|------|---------------|---------|
| L1 | `cd deployment/docker && docker compose up -d` | 4 个服务全部 healthy，前端 http://localhost:3000 可访问 |
| L1 | `cd omni_desk_backend && pytest --ds=omni_desk_backend.settings.test` | 全部测试通过，coverage ≥ 当前阈值 |
| L1 | `cd omni_desk_frontend && npm test && npm run build` | 测试通过 + build 产物在 `build/` 目录 |
| L2 | push 到 `develop` 分支 | `ci-test` + `build-and-push-images` + `deploy-test` 三个 workflow 全绿，GHCR 出现新镜像 |
| L3 | 在干净 Ubuntu 22.04 上 `./deploy_offline.sh start` | 全部健康检查通过，从外部浏览器访问 http://<IP>/ 能登录、看到首页、调用 API、上传文件、Celery 任务执行 |
| L3 | `./deploy_offline.sh upgrade` | 备份成功 + 镜像更新 + 迁移完成 + 健康检查通过 |
| L3 | `./deploy_offline.sh rollback` | 回滚到上一版本，业务功能恢复 |

---

## 七、依赖与风险

### 7.1 外部依赖
- Ubuntu 22.04 自带 docker 版本可能较旧 → 文档中要求升级到 docker 24+
- GHCR 推送需要 `GITHUB_TOKEN`(已自动注入)
- `MINERU_API_KEY` 若在生产真实需要 → 用户提前申请

### 7.2 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 旧 `.env.production` 已被 root 拥有且字段不全，迁移时残留 | 中 | 中 | 计划脚本先 `chown` 并对比新模板，缺字段时主动询问用户 |
| 重新 pip-compile 后某些依赖锁版本变化导致行为差异 | 中 | 高 | 在 CI 中先跑全套测试再发布 |
| 服务器与本机时区不一致导致 Celery 任务调度异常 | 低 | 中 | base.py 中已设 `TIME_ZONE = 'Asia/Shanghai'`，确保容器内 `TZ` 与之一致 |
| 离线包体积过大(>2GB)传输失败 | 中 | 中 | `package_offline_bundle.sh` 支持分卷压缩 |
| 用户已运行旧版本，迁移时数据库结构破坏 | 低 | 高 | 强制执行 `check_migrations` + `backup_db` 后再 migrate |

### 7.3 不在本方案范围
- Kubernetes / Helm 化(后续可独立计划)
- HTTPS 证书自动续期(建议用 nginx 反向代理 + Let's Encrypt 或自签证书)
- 多节点高可用 / 数据库主从

---

## 八、用户决策(已确认 2026-06-03)

| 决策项 | 用户选择 | 对实施的影响 |
|--------|---------|------------|
| MINERU_API_KEY 策略 | **改为可选** | production.py 移除强校验,文档解析功能在缺 KEY 时优雅降级 |
| HTTPS 策略 | **仅 HTTP(内网部署)** | 引入 `USE_HTTPS=false` 控制 `*_COOKIE_SECURE`,nginx 仅暴露 80 端口 |
| CI 工作流 | **全部精简** | 删除 `ci.yml` 与 `ci-develop.yml`,合并为 `ci-test.yml` + `build-and-push-images.yml` + `deploy-test.yml` 三件套 |
| Compose 整合 | **淘汰 standalone 改用叠加层** | 删除 `docker-compose.offline-standalone.yml`,统一 base + override 模式 |

## 九、实施确认

**此计划包含 5 个阶段、约 30 个具体步骤,估算工作量 1-2 个工作日。**

请回复:
- 全部同意 → `yes` / `批准`,进入阶段 1 实施
- 部分调整 → `modify: <具体调整>`
- 改方案 → `different approach: <你的建议>`
