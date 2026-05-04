# Omni-Desk 项目测试方案

## 1. 概述

本文档旨在为 Omni-Desk 项目建立一个全面、自动化且高效的测试策略。目标是确保代码质量、提升开发效率、降低生产环境风险，并确保前后端应用的稳定性、可靠性和性能。

## 2. 测试层级与策略

我们将采用经典的测试金字塔模型，合理分配在单元测试、集成测试和端到端（E2E）测试上的投入。

### 2.1. 单元测试 (Unit Testing)

- **目标:** 验证最小可测试单元（如函数、组件、类）的逻辑正确性。
- **范围:**
    - **后端 (Python/Django):**
        - 使用 `pytest` 框架。
        - 重点测试 `views.py` 中的业务逻辑、`serializers.py` 的数据验证和转换、`models.py` 的方法以及其他工具函数。
        - 测试必须遵循 `omni_desk_backend/pytest.ini` 中定义的 `test_*.py` 或 `*_tests.py` 命名规范。
        - 数据库交互应使用 `pytest-django` 提供的内存数据库或测试专用数据库，避免污染开发数据。
    - **前端 (React/JavaScript):**
        - 使用 `Jest` 和 `@testing-library/react`。
        - 重点测试 React 组件的渲染、用户交互响应、状态管理（Context/Hooks）以及 `utils` 中的辅助函数。
        - 测试命令为 `npm test`。
- **原则:** 快速、独立、可重复。模拟（Mock）所有外部依赖（如API请求、数据库）。

### 2.2. 集成测试 (Integration Testing)

- **目标:** 验证模块之间、服务之间的交互是否按预期工作。
- **范围:**
    - **后端 API 测试:**
        - 使用 `pytest` 和 `djangorestframework.test.APIClient`。
        - 测试完整的API请求/响应周期，包括认证（JWT）、权限、序列化、视图逻辑和数据库操作。
        - 验证API的CRUD操作、边界条件和错误处理。
    - **前端与后端API集成:**
        - 在前端测试中，部分关键流程（如登录、核心数据获取）可以不模拟API，而是连接到一个真实的（测试环境）后端服务，验证数据格式和交互的正确性。
- **原则:** 关注模块间的“胶水层”，确保数据流和控制流正确无误。

### 2.3. 端到端测试 (End-to-End Testing)

- **目标:** 模拟真实用户场景，在完整的、部署好的应用上验证业务流程的正确性。
- **工具建议:** [Cypress](https://www.cypress.io/) 或 [Playwright](https://playwright.dev/)。
- **范围:**
    - 关键用户旅程，例如：
        1.  用户注册 -> 登录 -> 创建一个事件。
        2.  管理员登录 -> 人事管理 -> 添加新员工。
        3.  用户在日历上拖放一个排班。
- **原则:** 测试场景应尽可能贴近真实用户行为，覆盖核心业务价值。这类测试运行较慢，应精选最有价值的场景。

## 3. CI/CD 集成方案

将自动化测试集成到CI/CD流程是保障代码质量的关键。我们建议修改 `.github/workflows/build-and-push-images.yml` 工作流。

### 3.1. 修改后的工作流 (`.github/workflows/build-and-push-images.yml`)

建议在 `build-and-push` 任务之前增加 `test` 任务。

```yaml
name: Run Tests, Build and Push Docker Images

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      # 启动一个PostgreSQL数据库供后端测试使用
      postgres:
        image: postgres:13
        env:
          POSTGRES_USER: testuser
          POSTGRES_PASSWORD: testpassword
          POSTGRES_DB: testdb
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      # --- 前端测试 ---
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18' # 或与项目匹配的版本
      
      - name: Install Frontend Dependencies
        run: npm install
        working-directory: ./omni_desk_frontend

      - name: Run Frontend Tests
        run: npm test -- --watchAll=false
        working-directory: ./omni_desk_frontend

      # --- 后端测试 ---
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.9' # 或与项目匹配的版本

      - name: Install Backend Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
        working-directory: ./omni_desk_backend

      - name: Run Backend Tests
        run: pytest
        working-directory: ./omni_desk_backend
        env:
          # 将测试数据库连接到CI服务
          DATABASE_URL: postgres://testuser:testpassword@localhost:5432/testdb
          SECRET_KEY: 'a-dummy-secret-key-for-ci'
          # 其他必要的环境变量

  build-and-push:
    needs: test # 依赖测试任务成功
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Log in to the GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.repository_owner }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push backend image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./deployment/docker/omni_desk_backend/Dockerfile
          push: ${{ github.event_name == 'push' }} # 仅在推送到main分支时发布
          tags: ghcr.io/onemuggle/omni-desk-backend:latest

      - name: Build and push frontend image
        uses: docker/build-push-action@v5
        with:
          context: ./omni_desk_frontend
          file: ./omni_desk_frontend/Dockerfile
          push: ${{ github.event_name == 'push' }} # 仅在推送到main分支时发布
          tags: ghcr.io/onemuggle/omni-desk-frontend:latest
```

### 3.2. 流程说明

1.  **触发条件:** 当有代码推送到 `main` 分支或创建指向 `main` 分支的 `pull_request` 时触发。
2.  **`test` 任务:**
    *   并行执行前端和后端测试。
    *   为后端测试启动一个临时的 PostgreSQL 数据库服务。
    *   安装各自的依赖并运行测试命令。
    *   任何测试失败都将导致整个工作流失败，从而阻止代码合并或部署。
3.  **`build-and-push` 任务:**
    *   设置 `needs: test`，确保只有在所有测试都通过后才执行。
    *   修改 `push` 条件，仅在代码成功合并到 `main` 分支后（`github.event_name == 'push'`）才将镜像推送到 `ghcr.io`。在 `pull_request` 事件中，此任务仅构建镜像以验证其可构建性，但不会推送。

## 4. 质量门禁

- **代码覆盖率:** 建议引入代码覆盖率检查（如 `pytest-cov` for backend, `Jest --coverage` for frontend），并设定一个最低阈值（例如70%），未达到阈值的 PR 将无法合并。
- **静态代码分析:** 集成 `ESLint` (前端) 和 `Flake8` 或 `Black` (后端) 到CI流程中，强制执行代码风格和规范。

## 5. 测试现状（截至 2026-05-01）

### 5.1 后端测试覆盖情况

| Django App | 测试状态 | 覆盖率估计 | 说明 |
|---|---|---|---|
| personnel | 有测试 | ~40% | Model完整，API有覆盖，缺serializer和边界条件 |
| events | 有测试 | ~45% | Model较好，Schedule API完整，缺时区和冲突边界 |
| documents | 有测试 | ~35% | Model和基础CRUD，缺zip导入和权限过滤 |
| compliance | 有测试 | ~50% | 权限三级控制好，缺批量操作和状态流转 |
| users | 有测试 | ~55% | 注册/登录/权限有测试，缺JWT刷新/黑名单完整测试 |
| permissions | 有测试 | ~20% | 仅自定义permission class测试，ViewSet无测试 |
| config/memos/dify_apps/office_assistant/news/sensor_management/sensors/meeting_rooms/ebooks/projects/llm_service | **无测试** | 0% | 11个模块完全无测试 |

### 5.2 前端测试覆盖情况

- **0% 覆盖率** — 无任何 `.test.js` / `.test.jsx` 文件
- Jest + Testing Library 已安装，`setupTests.js` 有 matchMedia/ResizeObserver mock

### 5.3 API 端点覆盖

78 个端点中约 25 个有测试，**覆盖率约 32%**

---

## 6. 分阶段实施计划

### Phase 1: 关键路径快速覆盖（~67小时）

**后端基础设施：**
- [x] 创建 `conftest.py` 共享 fixtures（api_client, admin_user, regular_user）
- [x] `pytest.ini` 添加 `--cov-fail-under=60`
- [x] `requirements-dev.in` 添加 `factory_boy`、`model_bakery`、`pytest-mock`

**后端高优先级测试：**
- [x] `permissions/tests/test_views.py` — ViewSet CRUD + 权限隔离 (23 测试)
- [x] `sensor_management/tests/test_views.py` — 传感器管理 CRUD (12 测试)
- [x] `projects/tests/test_views.py` — 项目管理 CRUD (6 测试)
- [x] `config/tests/test_views.py` — 系统配置 CRUD (11 测试)
- [x] `memos/tests/test_views.py` — 备忘录 CRUD (7 测试)
- [ ] `users/` 补充 JWT 刷新、黑名单、token 过期测试
- [ ] `personnel/tests/test_serializers.py` — 数据验证
- [ ] `events/tests/test_edge_cases.py` — 时区、冲突边界

**前端基础设施：**
- [ ] 创建 `src/test-utils/test-utils.jsx` — QueryClient + MemoryRouter wrapper
- [ ] 创建 `src/test-utils/mocks.js` — axios mock
- [ ] 安装 `msw`（Mock Service Worker）

**前端高优先级测试：**
- [ ] `shared/api/axiosConfig.test.js` — JWT 拦截器、token 刷新
- [ ] `features/auth/components/ProtectedRoute.test.jsx` — 路由守卫
- [ ] `features/auth/pages/Login.test.jsx` — 登录表单
- [ ] `shared/components/communication/PostList.test.js` — 列表渲染
- [ ] `shared/components/communication/PostDetail.test.js` — 详情展示

**E2E 基础：**
- [ ] 安装 Playwright
- [ ] `e2e/tests/auth.spec.js` — 登录/登出流程

### Phase 2: 核心业务逻辑补充（~63小时）

- [ ] `news/tests/test_views.py`
- [ ] `dify_apps/tests/test_views.py`
- [ ] `office_assistant/tests/test_views.py`
- [ ] `ebooks/tests/test_views.py`
- [ ] `sensors/tests/test_views.py`
- [ ] `meeting_rooms/tests/test_views.py`
- [ ] 前端所有表单组件测试（约10个文件）
- [ ] 前端所有页面组件测试（约15个文件）
- [ ] 前端 custom hooks 测试（约5个文件）
- [ ] 已有测试模块边缘情况补充

### Phase 3: E2E 全覆盖 + 边缘情况（~42小时）

- [ ] `e2e/tests/personnel.spec.js` — 人员管理流程
- [ ] `e2e/tests/events.spec.js` — 排班管理流程
- [ ] `e2e/tests/documents.spec.js` — 文档管理流程
- [ ] `e2e/tests/permissions.spec.js` — 权限隔离验证
- [ ] 后端各模块边缘情况测试
- [ ] 大数据量查询性能测试

### Phase 4: 性能基线 + 回归检测（~20小时）

- [ ] 安装 `pytest-benchmark`
- [ ] API 响应时间基准测试
- [ ] N+1 查询检测
- [ ] 前端渲染性能测试
- [ ] 覆盖率门槛从 60% 提升至 80%

---

## 7. 工具链

| 工具 | 用途 | 添加位置 |
|---|---|---|
| `factory_boy` + `pytest-factoryboy` | 后端测试数据工厂 | `requirements-dev.in` |
| `model_bakery` | Django model 测试数据生成 | `requirements-dev.in` |
| `pytest-mock` | pytest mock 插件 | `requirements-dev.in` |
| `msw` | 前端 API mock 拦截 | `package.json` devDependencies |
| `playwright` | E2E 测试框架 | `package.json` devDependencies |
| `pytest-benchmark` | 性能基准测试 | `requirements-dev.in` |

---

## 8. 成功标准

- [ ] 后端 API 测试覆盖率 80%+（约 62/78 端点有测试）
- [ ] 前端语句覆盖率 50%+（当前 0%）
- [ ] users、permissions 安全模块 100% 覆盖
- [ ] E2E 覆盖 5 个核心用户流程
- [ ] CI 测试失败自动拦截合并（`--cov-fail-under=60`）
- [ ] 无 CRITICAL 安全漏洞的测试用例缺失