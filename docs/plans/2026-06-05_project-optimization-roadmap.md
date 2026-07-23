# 项目优化路线图(2026-06-05, 更新于 2026-07-18)

## 背景与目标

OmniDesk 是 Django 4.2 + React 18.3 全栈业务管理平台,**最新统计**: 42 个 Django apps, 26,816 行 Python 代码, 32,933 行前端代码, 9 条 CI workflow, 13 个部署脚本。已具备离线部署、Windows 7 兼容、版本管理、Docker 三层保障等能力。

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
- [x] 在 `requirements.in` 加 `python-json-logger==2.0.7`
- [x] 重新生成 `requirements-prod.txt`(pip-compile 已写入锁文件)
- [x] 修改 `settings/production.py` 的 `LOGGING` 段 — 使用 `pythonjsonlogger.jsonlogger.JsonFormatter` 输出 JSON
  - 注意:v2.0.7 的类路径是 `pythonjsonlogger.jsonlogger.JsonFormatter`,v3+ 才改名 `.json.JsonFormatter`
- [x] 补 `/api/system/ready/` 端点(`core/api.py` + `core/urls.py`)
  - 检查 DB / Redis(Cache) / Celery 三个依赖
  - Celery 检查使用 `inspect.ping(timeout=1.0)`,失败不阻塞
  - 200 表示就绪,503 表示未就绪
  - 4 个新测试覆盖(TestReadinessCheck)
- [x] 测试无回归:585 passed, 80.85% 覆盖率
- [ ] 后续:关键路径加 `logger.info/warning`(登录、权限失败、Celery 任务) — 需逐个功能加

### 阶段 5:安全与依赖扫描(0.5 周)
- [ ] 在 `ci.yml` 加 `pip-audit` 步骤
- [ ] 在 `ci.yml` 加 `npm audit --audit-level=high` 步骤
- [ ] 审计 `settings/base.py` 的 `CORS_ALLOWED_ORIGINS` 与 `CSRF_TRUSTED_ORIGINS`
- [ ] 审计 `SIMPLE_JWT` 配置与刷新策略
- [ ] 写 `docs/technical/24-security-checklist.md`

### 阶段 6:前端架构试点(1 周,可选)
- [x] 加 `tsconfig.json` 允许 `allowJs: true` 渐进(allowJs=true / checkJs=false / noEmit=true / strict=false)
- [x] 试点 `src/shared/types/api.d.ts` — 6 个共享类型:`ApiResponse<T>` / `PaginatedResponse<T>` / `PaginationParams` / `ApiError` / `TimeRange` / `IdRef`
- [x] 验证:`tsc --noEmit` 0 错误 + `npm run build` 通过(25.32s)
- [ ] 后续:把 `src/shared/api/` 改写为 TypeScript(下次会话)
- [ ] 后续:选 1 个表单页试点 `antd Form + zod`(下次会话)
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

---

## 2026-07-18 更新：新增发现（4 个维度深度审计）

> 以下问题为 2026-07-18 全项目审计新发现，按优先级补充到本路线图。

### 🔴 P0 — 安全问题（本周必须修复）

| # | 问题 | 位置 | 修复方案 | 预计时间 |
|---|------|------|----------|----------|
| **S-C1** | **TLS 私钥已提交 Git** | `utils/nginx/certs/server.key` | 吊销证书 + `git filter-repo` 清除历史 + `.gitignore` 排除 `certs/` | 2h |
| **S-C2** | **DRF 未设置默认权限类** | `settings/base.py:222-233` | 添加 `DEFAULT_PERMISSION_CLASSES: ["rest_framework.permissions.IsAuthenticated"]` | 30min |
| **S-C3** | **XSS：搜索结果未转义** | `UnifiedSearchBar.jsx:37,41` | `dangerouslySetInnerHTML` 用 `sanitizeHtml()` 包裹 | 15min |
| **S-H3+H4** | **ZIP 导入缺路径遍历检查** | `book_import.py:93,110` | 检查 `..` 路径（Zip Slip 攻击）+ 清理封面文件名 | 1h |
| **SEC-1** | **`.env.local` 已提交到 git** | `omni_desk_backend/.env.local` | 加入 .gitignore + `git rm --cached` + 轮换密钥 | 30min |
| **SEC-2** | **密码复用** | `deployment/docker/.env` | SECRET_KEY 和 POSTGRES_PASSWORD 生成独立值 | 15min |
| **SEC-3** | **Redis 密码暴露** | `deploy_tests.sh:157`, `smoke_tests.sh:184` | `-a` flag 改用 `REDISCLI_AUTH` 环境变量 | 15min |
| **SEC-4** | **`deploy_docker.sh` 销毁数据** | `deploy_docker.sh:29` | `down --volumes` 移除 `--volumes` flag | 5min |

### 🔴 P1 — 高优先级（1-2 周）

| # | 问题 | 位置 | 修复方案 | 预计时间 |
|---|------|------|----------|----------|
| **DEP-1** | **Django 4.2 已 EOL** | 全局 | 启动 Django 5.2 LTS 升级计划 | 1 周 |
| **DEP-2** | **requirements-prod.txt 含 alpha 包** | pip-compile 命令 | 移除 `--pre` flag，重新生成锁文件 | 15min |
| **CI-1** | **CI 严重冗余** | `build-and-push-images.yml`, `deploy-test.yml` | build-and-push 改为 workflow_run 触发，删除 test job | 2h |
| **CI-2** | **CI job 无 timeout** | 所有 9 个 workflow | 添加 `timeout-minutes`: lint 15min, test 30min, build 60min | 30min |
| **CI-3** | **`PIP_NO_CACHE_DIR=off` 含义反转** | 后端 Dockerfile:9 | 改为 `PIP_NO_CACHE_DIR=1` | 5min |
| **CI-4** | **volume mount 路径不匹配** | `docker-compose.yml:49` | `/app` vs WORKDIR `/usr/src/app` 统一 | 10min |
| **BE-1** | **`SECRET_KEY` 缺失静默降级** | `settings/base.py:34-47` | `production.py` 中阻止启动 | 30min |
| **BE-2** | **78% 异常无日志** | 275 个 except 块 | 批量添加 `logger.exception()` | 2 天 |
| **BE-3** | **smart_assistant 巨型 App** | 119 文件，17,562 行，占后端 44% | 拆分为 core + agents + tools | 1-2 周 |
| **BE-4** | **executor.py 882 行** | `smart_assistant/agents/executor.py` | 拆分为 pipeline + checkpoint + subtask_runner | 2 天 |
| **FE-1** | **10+ 未使用前端依赖** | package.json | 移除 openai(10MB)、react-dnd、react-tooltip 等 | 30min |
| **FE-2** | **13 个超大组件(>300 行)** | 前端 ScheduleManagementPage 909 行等 | 拆分为子组件 | 40h |
| **FE-3** | **React.memo 使用率 0%** | 整个前端 | 为 Sidebar、ToolResult 等添加 memo | 2h |
| **FE-4** | **`key={index}` 反模式** | 24 处 | 替换为稳定 key | 3h |

### 🟡 P2 — 中优先级（1 个月）

| # | 问题 | 位置 | 修复方案 | 预计时间 |
|---|------|------|----------|----------|
| **DS-1** | **smoke_tests.sh 变量 bug** | lines 85, 89 | `$state` → `$STATE`, `$health` → `$HEALTH` | 10min |
| **DS-2** | **rollback.sh 备份编号 bug** | lines 61-65 | pipe to while 子 shell，改用 `nl` | 15min |
| **DS-3** | **无 dry-run 支持** | upgrade.sh, rollback.sh | 添加 `--dry-run` flag | 4h |
| **DS-4** | **无结构化日志** | 所有部署脚本 | 添加 `log()` 函数 + 时间戳 | 3h |
| **DOC-1** | **无 Swagger/OpenAPI 文档** | 144 个路由仅 43% 有文档 | 配置 `drf-spectacular` | 1 天 |
| **DOC-2** | **7+ 已完成计划未清理** | `docs/plans/` | 删除已完成计划文件 | 30min |
| **DOC-3** | **用户手册零截图** | 14 篇手册 | 各补 1-2 张截图 | 1 周 |
| **BE-5** | **19 处 `.all()` 无分页保护** | views.py | 添加 `pagination_class` | 1 天 |
| **BE-6** | **52 处原始 SQL 查询** | 后端 | 审查并添加 select_related/prefetch_related | 8h |
| **BE-7** | **Serializer `fields = "__all__"` 过度暴露** | 30+ 处 | 改为显式字段列表 | 1 天 |

### 🟢 P3 — 低优先级（持续改进）

| # | 问题 | 修复方案 |
|---|------|----------|
| **BE-8** | Sidebar 重复代码 | 统一 Sidebar.jsx + BaseSidebar.jsx |
| **BE-9** | docprocessing chunk 608KB | 动态 import 懒加载 |
| **BE-10** | 178 处内联箭头函数 | 提取为 useCallback |
| **CI-5** | lint-backend 无 pip cache | 添加 `cache: 'pip'` |
| **CI-6** | prod compose 无资源限制 | 从 offline compose 复制限制 |
| **BE-11** | `print()` 语句残留 | 替换为 logger |
| **BE-12** | 无统一异常处理中间件 | 配置 DRF `DEFAULT_EXCEPTION_HANDLER` |

---

### 2026-07-18 实施路线图

#### 阶段 7: 安全加固（第 1 周）

- [ ] S-C1: 吊销证书 + 清除 git 历史中的私钥
- [ ] S-C2: 添加 DRF 默认权限类
- [ ] S-C3: 修复 UnifiedSearchBar XSS
- [ ] S-H3+H4: ZIP 导入路径遍历检查
- [ ] SEC-1: 清理 .env.local 提交
- [ ] SEC-2: 修复密码复用
- [ ] SEC-3: 修复 Redis 密码暴露
- [ ] SEC-4: 修复 deploy_docker.sh 数据销毁
- [ ] DEP-2: 移除 requirements-prod.txt 的 --pre

**预计时间**: 8 小时

#### 阶段 8: CI/CD 优化（第 2 周）

- [ ] CI-1: 消除 CI 冗余
- [ ] CI-2: 添加 CI timeout
- [ ] CI-3: 修复 PIP_NO_CACHE_DIR
- [ ] CI-4: 统一 volume mount 路径

**预计时间**: 4 小时

#### 阶段 9: 后端关键修复（第 3-4 周）

- [ ] BE-1: SECRET_KEY 缺失阻止启动
- [ ] BE-2: 批量添加异常日志
- [ ] BE-4: 拆分 executor.py
- [ ] BE-5: 审查 .all() 无分页保护

**预计时间**: 5 天

#### 阶段 10: 前端性能优化（第 5-6 周）

- [ ] FE-1: 移除未使用依赖
- [ ] FE-3: 添加 React.memo
- [ ] FE-4: 修复 key={index}
- [ ] FE-2: 拆分 ScheduleManagementPage + SmartChatPage

**预计时间**: 50 小时

#### 阶段 11: 部署脚本修复（第 7 周）

- [ ] DS-1: 修复 smoke_tests.sh 变量 bug
- [ ] DS-2: 修复 rollback.sh 备份编号
- [ ] DS-3: 添加 --dry-run 支持
- [ ] DS-4: 添加结构化日志

**预计时间**: 8 小时

#### 阶段 12: 文档补全（第 8-10 周）

- [ ] DOC-1: 配置 drf-spectacular
- [ ] DOC-2: 清理已完成计划
- [ ] DOC-3: 用户手册补截图

**预计时间**: 2 周

---

### 预期收益（更新后）

| 维度 | 优化前 | 优化后 | 收益 |
|------|--------|--------|------|
| CI 时间 | ~26 min/push | ~11 min/push | **节省 15 min/push** |
| Bundle 大小 | 3.9 MB | ~2.5 MB | **节省 1.4 MB (36%)** |
| 安全漏洞 | 8 个 P0 + 8 个 HIGH | 0 个 P0 | **消除关键风险** |
| 测试覆盖 | 80.89% | 85%+ | 提升 4%+ |
| 超大组件 | 13 个 >300 行 | <5 个 | **可维护性大幅提升** |
| 文档覆盖 | API 43% | API 100% | **自动化文档** |

---

### 风险评估（更新）

| 风险 | 等级 | 缓解 |
|------|------|------|
| TLS 私钥清除后证书需重新颁发 | HIGH | 提前准备新证书 |
| DRF 默认权限改变后 API 访问失败 | HIGH | 灰度发布 + 回滚预案 |
| Django 5.2 升级破坏依赖兼容 | HIGH | 先在 develop 分支测试 2 周 |
| 移除 openai 依赖后发现有隐藏引用 | LOW | 先 grep 验证 |
| 拆分组件导致回归 bug | MEDIUM | 添加测试覆盖后再拆分 |
| CI 优化后 workflow_run 触发失败 | LOW | 保留手动触发选项 |

---

### 审计方法论

本次审计使用 4 个并行 agent 分别分析：
1. **后端代码质量** — 代码规模、测试覆盖、依赖健康度、代码模式
2. **前端性能** — Bundle 大小、代码分割、React 性能、组件质量
3. **DevOps/CI-CD** — GitHub Actions、Docker、部署脚本、环境管理
4. **安全与文档** — Django settings、XSS/注入、文档完整性、代码注释

审计命令清单见附录 A。
