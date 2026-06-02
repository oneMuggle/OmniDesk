# OmniDesk 测试策略

> 本文档描述 OmniDesk 的**双重测试体系**：开发期测试（保证代码变更安全）+ 部署期测试（保证部署后可用）。
> 最新一次体系升级：2026-05-31（双测试体系建设方案，详见 `docs/plans/2026-05-31-dual-testing-system.md`）

---

## 1. 概述

OmniDesk 采用**双重测试体系**，在两个关键阶段自动拦截问题：

| 测试类型 | 触发时机 | 目的 | 工具 |
|----------|----------|------|------|
| **开发期测试** | 每次代码变更 / PR | 保证代码逻辑正确、新功能不破坏已有功能 | pytest (后端) + Jest (前端) |
| **部署期测试** | Docker 镜像构建后 / 部署后 | 保证容器、网络、环境变量、业务流程全部可用 | Shell + curl + docker compose |

---

## 2. 开发期测试

### 2.1 后端测试（Django + pytest）

**运行命令：**

```bash
# 开发环境运行所有测试
pytest --ds=omni_desk_backend.settings.test

# 带覆盖率报告
pytest --ds=omni_desk_backend.settings.test --cov=. --cov-report=html

# 运行单个模块
pytest --ds=omni_desk_backend.settings.test events/tests/test_views.py

# 带 JUnit 输出（CI 使用）
pytest --ds=omni_desk_backend.settings.test --junitxml=test-results/pytest.xml
```

**配置说明：**

- 使用 `omni_desk_backend/settings/test.py` — 内存 SQLite，MD5 密码加速器，日志关闭
- 测试文件命名：`test_*.py`，位于各 Django app 的 `tests/` 目录
- 共享 fixtures 在 `omni_desk_backend/conftest.py` — 提供 14 个 model factory 函数
- 外部依赖（LLM API、RAGFlow）使用 mock，确保测试可离线运行
- 覆盖率阈值：≥ 80%（在 `pytest.ini` 中配置 `--cov-fail-under=80`）

**已覆盖模块：**

| Django App | 测试文件 | 说明 |
|---|---|---|
| events | `events/tests/test_views.py` | 事件 CRUD、权限隔离 |
| documents | `documents/tests/test_views.py` | 文档上传、下载、权限过滤 |
| meeting_rooms | `meeting_rooms/tests/test_views.py` | 会议室预订 |
| communication | `communication/tests/test_views.py` | 帖子 CRUD |
| news | `news/tests/test_views.py` | 新闻 CRUD |
| sensors | `sensors/tests/test_views.py` | 传感器数据 |
| ragflow_service | `ragflow_service/tests/test_views.py` | mock 外部 RAGFlow 服务 |
| office_assistant | `office_assistant/tests/test_views.py` | 办公助手 |
| dify_apps | `dify_apps/tests/test_views.py` | Dify 应用管理 |
| health | `tests/test_health.py` | `/api/health/` 端点 |

**编写新测试的步骤：**

1. 在对应 Django app 下创建或修改 `tests/test_views.py`
2. 使用 `APIClient` 发送请求，验证响应状态码和数据
3. 使用 `conftest.py` 中的 factory 函数创建测试数据
4. 外部服务调用使用 `@pytest.mark.parametrize` 或 `unittest.mock.patch` 模拟

### 2.2 前端测试（React + Jest）

**运行命令：**

```bash
# 开发环境运行测试（watch 模式）
npm test

# 一次性运行（CI 使用）
npm test -- --watchAll=false

# 带覆盖率报告
npm run test:coverage

# 运行单个测试文件
npm test -- --testPathPattern=ProtectedRoute.test
```

**配置说明：**

- 框架：Jest + `@testing-library/react`
- 测试文件：`*.test.js` / `*.test.jsx`，与被测文件同目录或集中在 `__tests__/`
- 设置文件：`src/setupTests.js` — 提供 matchMedia / ResizeObserver mock
- API 层使用 `jest.mock()` 拦截 axios 请求
- 覆盖率目标：functions / lines ≥ 50%（当前 23%，持续改善中）

**已有测试模块：**

- 54 个测试文件，324 个测试全部通过
- 核心覆盖：登录页、路由守卫、通知页面、API 客户端等
- 工具函数测试逐步补充中

**编写新测试的步骤：**

1. 纯函数：直接测试输入输出，不依赖渲染
2. 组件：使用 `render()` + `screen.getBy*()` 进行行为驱动测试
3. API 交互：使用 `jest.mock('axios')` 或 MSW 拦截
4. 复杂组件：使用 `src/test-utils/` 中的 wrapper（含 QueryClient + MemoryRouter）

### 2.3 开发期工作流

```
开发新功能
    → 编写测试（TDD：先写测试，再写实现）
    → 本地运行 pytest + npm test 验证
    → 提交代码
    → CI 自动运行测试（ci-test.yml）
    → 测试通过后才能合并
```

**日常开发推荐命令：**

```bash
# 后端快速验证
pytest --ds=omni_desk_backend.settings.test -xvs  # 失败即停，详细输出

# 前端快速验证
npm test -- --watch --testPathPattern=相关模块

# 完整验证
pytest --ds=omni_desk_backend.settings.test && npm test -- --watchAll=false
```

---

## 3. 部署期测试

部署期测试在 Docker 镜像构建完成后运行，验证整个系统在真实容器环境中的可用性。

### 3.1 测试脚本

主脚本：`deployment/docker/deploy_tests.sh`

```bash
# 本地运行（需要 docker compose 已启动服务）
cd deployment/docker/
./deploy_tests.sh http://localhost

# 指定其他地址
./deploy_tests.sh http://192.168.1.100
```

### 3.2 10 个验证阶段

| 阶段 | 验证内容 | 关键命令 |
|------|----------|----------|
| **1. 容器状态** | 所有服务 running/healthy | `docker compose ps` 检查 6 个容器 |
| **2. 前端可访问性** | 首页 HTTP 200，包含 `<div id="root">` | `curl http://localhost/` |
| **3. 后端 API 连通性** | `/api/health/` 返回 JSON，database 状态 ok | `curl http://localhost/api/health/` |
| **4. 数据库连接** | 后端能执行 SQL 查询 | `docker compose exec backend python -c "SELECT 1"` |
| **5. Redis 连通性** | Redis 响应 PONG | `docker compose exec redis redis-cli ping` |
| **6. Celery Worker** | worker 进程处于 Up 状态 | `docker compose ps worker` |
| **7. 关键业务流程** | Guest 登录 → 获取 token → 访问受保护 API | `curl guest-login` → `curl /api/users/me/` |
| **8. 反向代理** | `/api/` → 后端，`/admin/` → 后端，`/` → 前端 | `curl` 各路径验证路由 |
| **9. 环境变量** | 后端 `DJANGO_SETTINGS_MODULE`、`POSTGRES_DB` 等已注入 | `docker compose exec backend env` |
| **10. 静态文件** | JS/CSS bundle 返回 200，无 404 | 解析 HTML 中的资源引用，逐个 `curl` |

### 3.3 输出格式

```
==========================================
  OmniDesk 部署测试
  目标: http://localhost
  日期: 2026-05-31 16:00:00
==========================================

阶段 1: 容器状态
  OK: db (state=running)
  OK: redis (state=running)
  ...
  PASS: All required services running

...

==========================================
  测试结果
==========================================
  PASS: 20
  FAIL: 0
  SKIP: 2
  通过率: 100%

STATUS: ALL PASSED
```

### 3.4 部署测试工作流

```
Docker 镜像构建完成
    → docker compose up（使用生产配置）
    → 等待所有服务 healthy
    → 运行 deploy_tests.sh
    → 检查通过率（任何 FAIL 即告警）
    → 清理测试环境
```

---

## 4. CI/CD 集成

### 4.1 工作流总览

```
PR / 推送到 main/develop
    ↓
┌─────────────────────────────────────────┐
│ ci-test.yml                             │
│   后端 pytest + 前端 jest 并行运行        │
│   生成覆盖率报告 + JUnit 输出             │
│   任一失败 → 阻止合并                     │
└─────────────────────────────────────────┘
    ↓ (全部通过)
┌─────────────────────────────────────────┐
│ build-and-push-images.yml               │
│   Docker 构建                           │
│   镜像自检（health endpoint 验证）         │
│   推送到 GHCR                           │
└─────────────────────────────────────────┘
    ↓ (构建成功)
┌─────────────────────────────────────────┐
│ deploy-test.yml                         │
│   docker compose up（test 配置）          │
│   等待服务 healthy                       │
│   运行 deploy_tests.sh（10 个阶段）       │
│   输出结果 + 清理环境                     │
└─────────────────────────────────────────┘
```

### 4.2 各工作流职责

| 工作流 | 触发条件 | 运行内容 | 失败后果 |
|--------|----------|----------|----------|
| `ci-test.yml` | PR / push to main/develop | 后端 pytest + 前端 jest | 阻止 PR 合并 |
| `build-and-push-images.yml` | push to main | Docker 构建 + 镜像自检 | 不推送失败镜像 |
| `deploy-test.yml` | build-and-push 完成后 | 部署期 10 阶段测试 | 告警，不自动部署 |

### 4.3 覆盖率报告

CI 生成两种报告：

- **后端**: `pytest --cov --junitxml=test-results/pytest.xml` — 输出到 `test-results/`
- **前端**: `npm run test:coverage -- --coverageReporters=text --coverageReporters=cobertura` — 输出到 `coverage/`

---

## 5. 测试现状统计

### 5.1 后端

- **测试总数**: 438 passed, 29 failed（29 个为已有问题，非本次引入）
- **覆盖率**: 80%+ 目标（pytest.ini 配置中）
- **覆盖模块**: 9 个核心模块 + health endpoint

### 5.2 前端

- **测试文件**: 54 个
- **测试总数**: 324 passed, 0 failed
- **覆盖率**: 23%（目标 50%，持续改善中）

### 5.3 部署测试

- **检查阶段**: 10 个
- **脚本**: `deployment/docker/deploy_tests.sh`
- **运行环境**: Docker compose + 真实 PostgreSQL + Redis

---

## 6. 附录

### 6.1 测试目录结构

```
omni_desk_backend/
├── conftest.py                    # 共享 fixtures（14 个 model factory）
├── pytest.ini                     # pytest 配置 + 覆盖率阈值
├── tests/
│   └── test_health.py             # health endpoint 测试
├── events/tests/test_views.py
├── documents/tests/test_views.py
├── meeting_rooms/tests/test_views.py
├── communication/tests/test_views.py
├── news/tests/test_views.py
├── sensors/tests/test_views.py
├── ragflow_service/tests/test_views.py
├── office_assistant/tests/test_views.py
└── dify_apps/tests/test_views.py

omni_desk_frontend/
├── src/setupTests.js              # Jest 全局 mock 配置
├── src/__mocks__/                 # 自定义 mock
└── **/*.test.{js,jsx}             # 各模块测试文件

deployment/docker/
├── deploy_tests.sh                # 部署期主测试脚本（10 个阶段）
└── tests/
    ├── test_api_endpoints.sh      # API 端点专项测试
    ├── test_frontend.sh           # 前端资源专项测试
    └── test_infrastructure.sh     # 基础设施专项测试

.github/workflows/
├── ci-test.yml                    # PR/推送测试
├── build-and-push-images.yml      # 构建 + 推送
└── deploy-test.yml                # 部署后自动测试
```

### 6.2 常见问题

**Q: 本地开发时是否需要每次运行全部测试？**

不需要。开发时运行相关模块的测试即可，CI 会运行完整测试套件。

**Q: 部署测试是否需要在每次 commit 后运行？**

不需要。部署测试由 CI 在 Docker 构建后自动触发，本地仅在部署前手动验证时运行。

**Q: 测试依赖外部服务（LLM API、RAGFlow）如何保证稳定性？**

所有外部服务调用必须使用 mock。单元测试使用内存 SQLite，部署测试才使用真实 PostgreSQL。

### 6.3 工具链

| 工具 | 用途 | 位置 |
|---|---|---|
| `pytest` + `pytest-django` | 后端测试框架 | `requirements-dev.in` |
| `pytest-cov` | 覆盖率测量 | `requirements-dev.in` |
| `factory_boy` | 测试数据工厂 | `requirements-dev.in` |
| `model_bakery` | Django model 数据生成 | `requirements-dev.in` |
| `Jest` + `@testing-library/react` | 前端测试框架 | `omni_desk_frontend/package.json` |
| `curl` + `docker compose` | 部署期测试 | `deployment/docker/deploy_tests.sh` |
