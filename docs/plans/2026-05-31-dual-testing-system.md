# OmniDesk 双测试体系建设方案

## 日期: 2026-05-31

---

## 背景与目标

OmniDesk 作为全栈业务管理平台，当前存在两套测试不完善的问题：

1. **开发期测试不完善** — 部分 Django 应用和前端组件缺少单元测试，无法保证开发新功能时不破坏已有功能
2. **缺少部署期测试** — Docker 打包部署后缺少自动化验证，可能因路径错误、环境变量注入错误等导致功能不可用

**目标**: 建立完整的双重测试体系，确保代码变更安全和部署后可用。

---

## 涉及的文件与模块

### 后端（Django pytest）

| 模块 | 状态 | 需新增测试文件 |
|------|------|----------------|
| events | 缺失 | `events/tests/test_views.py` |
| documents | 缺失 | `documents/tests/test_views.py` |
| meeting_rooms | 缺失 | `meeting_rooms/tests/test_views.py` |
| communication | 缺失 | `communication/tests/test_views.py` |
| news | 缺失 | `news/tests/test_views.py` |
| sensors | 缺失 | `sensors/tests/test_views.py` |
| ragflow_service | 缺失 | `ragflow_service/tests/test_views.py` |
| office_assistant | 缺失 | `office_assistant/tests/test_views.py` |
| dify_apps | 缺失 | `dify_apps/tests/test_views.py` |
| health check | 缺失 | `tests/test_health.py` |

### 前端（Jest）

| 模块 | 状态 | 需新增测试文件 |
|------|------|----------------|
| API 客户端 | 缺失 | `src/shared/api/apiClient.test.js` |
| 路由守卫 | 缺失 | `src/shared/components/ProtectedRoute.test.js` |
| 登录页 | 缺失 | `src/shared/pages/LoginPage.test.js` |
| 工具函数 | 缺失 | `src/utils/*.test.js` |
| Mock 基础设施 | 缺失 | `src/__mocks__/handlers.js`, `src/__mocks__/server.js` |

### 部署测试

| 文件 | 说明 |
|------|------|
| `deployment/docker/deploy_tests.sh` | 主测试脚本（重构 smoke_tests.sh） |
| `deployment/docker/tests/test_api_endpoints.sh` | API 端点测试 |
| `deployment/docker/tests/test_frontend.sh` | 前端资源测试 |
| `deployment/docker/tests/test_infrastructure.sh` | 基础设施测试 |

### CI/CD

| 文件 | 变更 |
|------|------|
| `.github/workflows/ci-test.yml` | 增加覆盖率报告、JUnit 输出 |
| `.github/workflows/deploy-test.yml` | 新增：Docker 构建后自动部署测试 |
| `.github/workflows/build-and-push-images.yml` | 增加镜像自检步骤 |

---

## 技术方案

### 第一套：开发期测试

**后端**: 使用已有 pytest + pytest-django 框架
- 测试运行命令：`pytest --ds=omni_desk_backend.settings.test`
- 使用 conftest.py 共享 fixtures
- 外部依赖（LLM API、RAGFlow）使用 mock
- 覆盖率目标：≥ 80%

**前端**: 使用已有 Jest + @testing-library/react
- 测试运行命令：`npm test` / `npm run test:coverage`
- 纯函数直接测试输入输出
- 组件使用行为驱动测试
- API 层使用 jest.mock 拦截
- 覆盖率目标：functions/lines ≥ 60%

### 第二套：部署期测试

基于 shell 脚本 + curl + docker compose，分 10 个验证阶段：

| 阶段 | 验证内容 | 方法 |
|------|----------|------|
| 1 | 容器状态 | `docker compose ps` 检查 running/healthy |
| 2 | 前端可访问性 | `curl` 检查首页 HTTP 200 |
| 3 | 后端 API 连通性 | `curl` 逐个验证 API 端点 |
| 4 | 数据库连接 | `docker compose exec` 执行数据库查询 |
| 5 | Redis 连通性 | `docker compose exec redis redis-cli ping` |
| 6 | Celery Worker 状态 | `docker compose exec` 检查 worker 进程 |
| 7 | 关键业务流程 | 模拟登录 → 创建资源 → 查询 |
| 8 | 反向代理 | 验证 Nginx 路由转发正确 |
| 9 | 环境变量 | 检查容器内环境变量注入正确 |
| 10 | 静态文件路径 | 验证 JS/CSS/字体/图片无 404 |

### CI/CD 集成

```
PR/推送到 main/develop
    → ci-test.yml: 运行后端 pytest + 前端 jest
    → 生成覆盖率报告 + JUnit 报告

build-and-push-images.yml: Docker build
    → docker run 快速验证 health endpoint
    → push 到 GHCR

deploy-test.yml (Docker 构建后触发):
    → docker compose up (test 配置)
    → 等待服务 healthy
    → 运行 deploy_tests.sh
    → 输出结果 + 清理环境
```

---

## 实施步骤

### Phase 1: 后端测试补全（9 个模块） ✅ 已完成
- [x] 1.1 events 模块测试
- [x] 1.2 documents 模块测试
- [x] 1.3 meeting_rooms 模块测试
- [x] 1.4 communication 模块测试
- [x] 1.5 news 模块测试
- [x] 1.6 sensors 模块测试
- [x] 1.7 ragflow_service 模块测试（mock 外部服务）
- [x] 1.8 office_assistant 模块测试
- [x] 1.9 dify_apps 模块测试

### Phase 2: 后端基础设施 ✅ 已完成
- [x] 2.1 conftest.py 扩展（14 个通用 model factory 函数）
- [x] 2.2 health endpoint 单元测试
- [x] 2.3 pytest.ini 覆盖率阈值提升至 80%（待验证）

### Phase 3: 前端测试补全 ✅ 部分完成
- [x] 3.1 现有测试验证 (54 个测试文件，324 个测试全部通过)
- [x] 3.2 NotificationsPage 测试 (4 个测试用例)
- [~] 3.3 路由守卫测试 (已有 ProtectedRoute.test.jsx)
- [~] 3.4 登录页面测试 (已有 Login.test.js)
- [ ] 3.5 工具函数测试
- [ ] 3.6 前端覆盖率提升 (当前 23%，目标 50%)

### Phase 4: 部署测试体系 ✅ 已完成
- [x] 4.1 deploy_tests.sh（10 个检查阶段）
- [x] 4.2 容器状态 + 前端可访问性
- [x] 4.3 后端 API 连通性 + 数据库健康
- [x] 4.4 数据库连接验证
- [x] 4.5 Redis 连通性
- [x] 4.6 Celery Worker 状态
- [x] 4.7 关键业务流程 (Guest login -> 认证 API)
- [x] 4.8 反向代理配置验证
- [x] 4.9 环境变量注入验证
- [x] 4.10 静态文件路径验证

### Phase 5: CI/CD 集成
- [ ] 5.1 优化 ci-test.yml
- [ ] 5.2 新增 deploy-test.yml
- [ ] 5.3 优化 build-and-push-images.yml

---

## 风险评估与依赖

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 某些模块依赖外部服务，测试不稳定 | 中 | 全面使用 mock，测试网络隔离 |
| 覆盖率目标过高导致测试质量下降 | 中 | 关注关键路径，优先 80/20 |
| 部署测试在 CI 中运行时间长 | 中 | 设置合理超时，仅生产构建时运行 |
| PostgreSQL vs SQLite 测试差异 | 低 | 部署测试用真实 PostgreSQL，单元测试用 SQLite |

## 依赖

- pytest + pytest-django + pytest-cov（已有）
- Jest + @testing-library/react（已有）
- Docker + docker compose（部署测试需要）
- GitHub Actions CI/CD（已有）
