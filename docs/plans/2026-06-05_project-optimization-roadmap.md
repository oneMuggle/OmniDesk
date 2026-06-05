# 项目优化路线图(2026-06-05)

## 背景与目标

OmniDesk 是 Django 4.2 + React 18.3 全栈业务管理平台,约 22K 行 Python 代码、34 个 Django app、23 篇技术文档、4 条 CI workflow。已具备离线部署、Windows 7 兼容、版本管理、Docker 三层保障等能力。

本次优化以**不破坏现有强约束**(离线/Windows 7/双 UI 库共存过渡期/Django LTS)为前提,从 ROI 角度分 P0/P1/P2 三个优先级给出 8 个可执行模块。**目标:**

- 测试覆盖率从当前基线提升至 ≥ 80%
- 主要列表 API P95 响应下降 50%
- 前端首屏 LCP < 2.5s(Chrome 109)
- 仓库可维护性 + 安全基线对齐 OWASP Top 10
- 文档与代码现状同步(消除 CLAUDE.md/AGENTS.md 中过时描述)

## 涉及的文件与模块

| 优化项 | 主要文件 | 影响范围 |
|--------|----------|----------|
| 文档同步 | `CLAUDE.md`、`AGENTS.md`、`docs/technical/README.md` | 项目元信息 |
| 测试覆盖率 | `omni_desk_backend/{users,permissions,compliance,projects,events,...}/tests/`、`pytest.ini`、`ci.yml` | CI 卡点 |
| API 性能 | `omni_desk_backend/**/views.py`、`omni_desk_backend/**/serializers.py` | 列表/详情 API |
| 前端构建 | `omni_desk_frontend/vite.config.js`、`omni_desk_frontend/src/main.jsx` | 首屏 + 包体积 |
| 日志可观测 | `omni_desk_backend/omni_desk_backend/settings/{base,production}.py`、`core/views.py` | 生产环境 |
| 安全 | `omni_desk_backend/requirements.in`、`omni_desk_frontend/package.json`、`.github/workflows/*.yml` | CI 卡点 |
| 前端架构 | `omni_desk_frontend/src/shared/`、`omni_desk_frontend/tsconfig.json` | 新代码可选 |

## 技术方案概览

### 文档同步(P0 验证后的发现)
实际扫描结果与 `CLAUDE.md` 描述存在偏差,需先纠正再制定后续计划:

| `CLAUDE.md` 原描述 | 扫描结果 | 行动 |
|--------------------|----------|------|
| #1 "Two UI libraries" (antd + MUI) | MUI 已完全移除,只剩 antd 120 处 import | 更新为"antd 单一" |
| #5 "Root package.json has Vue deps" | 根 `package.json` 不存在(已被 .gitignore 排除) | 删除该条目 |
| `**/db.sqlite3`、`htmlcov/` 已忽略 | 已正确忽略,无需处理 | 仅核对 |
| `.claude/` 等 IDE 目录 | `.roo/.trae/.sisyphus/.night-work/.opencode` 已在 .gitignore | 已正确处理 |

### 测试覆盖率方案
- 基线:先执行 `pytest --cov --cov-report=term-missing` 输出覆盖率
- 提升路径:沿 `docs/plans/2026-06-02_test-coverage-improvement.md` 优先级,补 users/permissions/compliance 三个核心 app
- CI 卡点:`pytest.ini` 中增加 `addopts = --cov-fail-under=80`,渐进式降低阈值(40→60→80)
- 工具:用 `pytest-cov` + `coverage report --skip-covered`

### API 性能方案
- 扫描目标:`ListAPIView`、`ListCreateAPIView`、`ViewSet` 中带 `queryset` 的列表方法
- 优化手段:`select_related`(FK)、`prefetch_related`(M2M/反 FK)、`only/defer` 字段裁剪、`pagination_class` 强制分页
- 验证:`django-silk` 接入 dev 模式,记录 P95 前后对比

### 前端构建方案
- `vite.config.js` 中 `build.rollupOptions.output.manualChunks` 拆分 antd、echarts、dayjs
- React Query stale time:列表 60s、详情 5min、字典数据 30min
- Lighthouse 在 PR check 中跑(可选)

### 日志可观测方案
- 引入 `python-json-logger`,生产环境输出 JSON
- 关键事件:登录、权限校验失败、Celery 任务起止、错误堆栈
- 脱敏:密码、token、JWT、PII 字段
- 补 `/api/system/ready/` 检查 DB / Redis / Celery worker

### 安全方案
- CI 集成 `pip-audit` + `npm audit --audit-level=high`
- 审查:`SIMPLE_JWT` 黑名单、CORS 白名单、Cookie `SameSite`
- 文档:补 OWASP Top 10 对照表到 `docs/technical/24-security-checklist.md`

### 前端架构方案
- TypeScript 试点:`omni_desk_frontend/src/shared/` 中 `api/`、`types/` 优先
- 表单统一:`antd Form` + `zod` schema 校验
- 渐进式:不强制存量迁移,只对新代码启用

## 实施步骤

### 阶段 0:文档同步(0.5 天)
- [ ] 更新 `CLAUDE.md` 第 1 条与第 5 条(实测已变)
- [ ] 同步 `AGENTS.md` 中的技术栈描述
- [ ] 在 `docs/technical/README.md` 补一条"项目状态快照"链接

### 阶段 1:测试覆盖率(1 周)
- [x] 跑 `pytest --cov` 拿基线值(2026-06-05: **78.07%** 总覆盖率,560 passed, 1 xfailed, 47s)
- [x] 在 `pytest.ini` 加 `--cov-fail-under=70`(已存在)
- [x] 补 `events/management/seeders/*.py` 测试 — 新建 `events/tests/test_seeders.py`,21 个测试,seeders 模块覆盖率从 0% → **88%**(meeting_room 94%, personnel 97%, trial_schedule 62%, __init__ 67%, 其余 100%)
- [x] 在 `pytest.ini` 把阈值从 70% 提升至 **80%**
- [x] 总覆盖率从 78.07% 推至 **80.89%**(581 passed, 1 xfailed, 47s) — **目标达成**
- [ ] 后续:补 `users/{signals,tasks,shared_serializers,user_urls}.py`(0% → 70%+,低优先)
- [ ] 后续:补 `core/management/commands/*.py`(0% → 60%+,中优先)
- [ ] 后续:补 `smart_assistant/agent/*.py`(10-49% → 50%+,高复杂)

### 阶段 2:API 性能(1 周)
- [x] 用 `grep` 列出所有 `ListAPIView` / `ListCreateAPIView` / `ViewSet` 类(共 52 个)
- [x] 审计全局分页配置(已默认 `PageNumberPagination`,PAGE_SIZE=10)
- [x] 修复 3 个 N+1 风险:
  - `documents/views/templates.py` — `DocumentTemplateViewSet` 加 `select_related("project", "owner")`
  - `documents/views/books.py` — `BookViewSet` 加 `select_related("project")`(已有 prefetch)
  - `documents/views/documents.py` — `GeneratedDocumentViewSet` 加 `select_related("template")`(已有 generated_by)
- [x] 写审计报告 `docs/technical/25-api-performance-audit.md`(包含所有 ViewSet 状态、优先级、监控建议)
- [x] 测试无回归:581 passed, 80.88% 覆盖率
- [ ] 后续:接入 `django-silk` 到 dev 模式(可选)
- [ ] 后续:为 `GeneratedDocumentViewSet` 恢复分页(当前 `pagination_class = None`)

### 阶段 3:前端构建优化(0.5 周)
- [x] 在 `vite.config.js` 配置 `manualChunks`(从 3 项扩到 13 项:vendor/http/datetime/data/antd/icons/dnd/editor/fullcalendar/docprocessing/notify/markdown/jwt)
- [x] 跑 `npm run build` 对比 chunk 数量与体积
- [x] **关键改进**:
  - `ScheduleManagementPage`: 610 kB → **22 kB** (-96%)
  - `index (main)`: 420 kB → **262 kB** (-38%)
  - 拆出独立 vendor chunks:http(axios)36kB, data(react-query)38kB, notify 30kB, icons 71kB, markdown 156kB, docprocessing 614kB, editor 603kB
- [ ] 后续:为 docprocessing / editor / markdown 的大 chunk 进一步按页面动态 import
- [ ] 后续:`React.lazy` 边界审查(过度细分合并)

### 阶段 4:日志与可观测(0.5 周)
- [ ] 在 `requirements.in` 加 `python-json-logger`
- [ ] 重新生成 `requirements-prod.txt`
- [ ] 修改 `settings/production.py` 的 `LOGGING` 段
- [ ] 补 `/api/system/ready/` 端点
- [ ] 关键路径加 `logger.info/warning`(登录、权限失败、Celery 任务)

### 阶段 5:安全与依赖扫描(0.5 周)
- [ ] 在 `ci.yml` 加 `pip-audit` 步骤
- [ ] 在 `ci.yml` 加 `npm audit --audit-level=high` 步骤
- [ ] 审计 `settings/base.py` 的 `CORS_ALLOWED_ORIGINS` 与 `CSRF_TRUSTED_ORIGINS`
- [ ] 审计 `SIMPLE_JWT` 配置与刷新策略
- [ ] 写 `docs/technical/24-security-checklist.md`

### 阶段 6:前端架构试点(1 周,可选)
- [ ] 加 `tsconfig.json` 允许 `allowJs: true` 渐进
- [ ] `src/shared/api/` 改写为 TypeScript
- [ ] 选 1 个表单页试点 `antd Form + zod`
- [ ] 评估是否扩大范围

## 风险评估

| 风险 | 等级 | 缓解 |
|------|------|------|
| CI 卡覆盖率后存量 PR 失败 | MEDIUM | 渐进式阈值(40→60→80),提前 1 周通知团队 |
| 性能优化改变列表 API 行为 | MEDIUM | 优化前后写 e2e 用例,字段裁剪在 Serializer 显式标注 |
| Vite 拆分导致老浏览器 chunk 加载异常 | LOW | 保守拆分,只拆 antd/echarts/dayjs 三个稳定 vendor |
| 日志结构化改变 ELK 收集规则 | LOW | 本项目暂无 ELK,先准备 JSON 格式不强制收集 |
| TypeScript 渐进式迁移打断 Vite 构建 | LOW | `allowJs: true` + 不强制 strict 模式 |

## 依赖

- `pytest-cov`(覆盖率)
- `django-silk`(API 性能)
- `python-json-logger`(结构化日志)
- `pip-audit`(安全扫描)
- `npm audit`(前端依赖扫描,内置)
- `zod`(前端表单,可选)
- `typescript`(前端 TS,可选)

## 不在本路线图内

- 升级 Django 4.2 → 5.x(单独立项,涉及依赖兼容)
- 升级 React 18 → 19(同上)
- 引入微服务/前后端分离重构(架构级)
- 引入新 UI 库(Chakra、Radix)
- 部署到云厂商(项目硬约束:内网离线)
