# 优化路线图续写设计(2026-06-16)

> 版本:v1
> 状态:已批准(用户 2026-06-16 确认)
> 关联:`docs/plans/2026-06-05_project-optimization-roadmap.md`(P0/P1/P2 三级 8 模块路线图)

## 一、背景与目标

### 背景

OmniDesk(Django 4.2 + React 18.3 全栈业务管理平台)于 2026-06-05 制定了 8 模块优化路线图,10 天内已大幅推进:

| 已完成项 | 状态 |
|----------|------|
| 总覆盖率 ≥ 80%(pytest.ini `--cov-fail-under=80`) | ✅ |
| 前端构建 chunk 拆分(ScheduleManagementPage -96%) | ✅ |
| API 性能审计 + 3 个 N+1 修复(`25-api-performance-audit.md`) | ✅ |
| JSON 结构化日志 + `/api/system/ready/` 端点 | ✅ |
| 安全扫描集成(bandit + pip-audit + npm audit) | ✅ |
| `docs/technical/24-security-checklist.md`(6 个 CVE 修复) | ✅ |
| smart-assistant 优化 P0-P6 + 阶段 3 14 任务 | ✅ |

### 本次目标

推完 2026-06 路线图剩余的 **6 项未完成项**,全部按独立 PR/feature 分支交付。

### 验收标准

- 6 个 PR 全部合并到 main
- 每个 PR 独立可测、可回滚
- 覆盖率不下降(维持 ≥ 80%)
- CI 全绿(backend + frontend + security + lint)
- 不破坏 Windows 7 / 离线部署 / Django LTS 强约束

## 二、范围

### In Scope(6 个 PR)

| PR# | 范围 | 分支 | 工作量 |
|-----|------|------|--------|
| PR-1 | 后端/分页修复 | `fix/viewset-pagination-restore` | 0.5 d |
| PR-2 | 后端/关键路径日志 | `feat/key-path-logger` | 1.5 d |
| PR-3 | 后端/django-silk dev | `feat/django-silk-dev` | 0.5 d |
| PR-4 | 前端/shared/api → TS | `refactor/shared-api-typescript` | 2 d |
| PR-5 | 前端/zod 表单试点 | `feat/zod-form-pilot` | 1 d |
| PR-6 | 前端/动态 import | `feat/lazy-chunk-optimization` | 0.5 d |

### Out of Scope(明确不做)

- Django 4.2 → 5.x / React 18 → 19(单独立项,需依赖兼容评估)
- `smart_assistant/agent/*` 覆盖率(已在 smart-assistant-opt 子项目完成)
- `users/{signals,tasks,shared_serializers,user_urls}` 测试(低优先,后续)
- `core/management/commands/*` 测试(中优先,后续)
- 自动从 drf-spectacular 生成 TS 类型(可后续)
- 引入新 UI 库 / 微服务拆分 / 云端部署

## 三、技术方案

### PR-1:ViewSet 分页恢复

**问题:** 4 个 ViewSet 显式 `pagination_class = None`,返回完整列表,存在数据膨胀风险。

```
documents/views/documents.py:13:    pagination_class = None
users/views/views.py:185:              pagination_class = None  (待定位)
permissions/views.py:29:               pagination_class = None
events/views.py:764:                   pagination_class = None
```

**方案:**
1. **每个位置先看上下文**:
   - `documents/views/documents.py` (GeneratedDocumentViewSet) — 文档列表,需分页 → 恢复
   - `users/views.py:185` — 看 viewset 类型与用法,小集合(如下拉)可保留 None + 加 max 限制
   - `permissions/views.py:29` — 权限下拉通常需要全集,保留 None 但封顶 1000 条
   - `events/views.py:764` — 看 viewset 类型,按业务决策
2. **强依赖"返回全集"的位置:** 不改 `pagination_class`,但加 `queryset` 截断 + 单元测试断言最大条数 ≤ N
3. **真分页修复的位置:** 移除 `pagination_class = None`,沿用全局 `PageNumberPagination(PAGE_SIZE=10)`

**风险缓解:**
- `grep` 4 处对应前端调用方,确认无前端依赖"无分页"响应结构
- 加 e2e 测试断言文档列表有 `count`/`next`/`previous` 字段
- 先在 PR 中标记哪些保留 None(透明决策)

**测试:**
- `documents/tests/test_documents_viewset.py`:分页元数据存在
- E2E:文档管理页面正常加载并显示分页器

**Acceptance:**
- ✅ 至少 `GeneratedDocumentViewSet` 恢复分页
- ✅ 4 处全部给出明确决策(恢复 vs 保留 None + 限制)
- ✅ 所有决策在 PR 描述中标注理由
- ✅ 无前端回归

### PR-2:关键路径结构化日志

**目标:** 让生产环境排障时能 grep 到关键事件,且不泄露 PII。

**关键事件清单:**

| 事件 | 触发位置 | 现有状态 | 日志级别 |
|------|----------|----------|----------|
| 登录成功 | `users/views.py` 登录 view | 待确认 | `info` |
| 登录失败(密码错/账号锁) | 同上 | 待确认 | `warning` |
| JWT 刷新失败 | `axiosConfig.js` 对应后端中间件 | 待确认 | `warning` |
| 权限校验失败 | DRF permission class 或 `permissions/views.py` | 待确认 | `warning` |
| Celery 任务开始 | `events/tasks.py`、`core/tasks.py`、`*/*/tasks.py` | 部分已有 | `info` |
| Celery 任务成功 | 同上 | 部分已有 | `info` |
| Celery 任务失败/重试 | 同上 | 部分已有 | `error` |

**日志格式规范:**
- 使用已有 `python-json-logger`(生产环境自动 JSON)
- 字段:`timestamp` / `level` / `event` / `user_id`(非 email)/ `endpoint` / `task_name` / `duration_ms` / `extra`

**脱敏规范(永不记录):**
- 密码明文 / hash
- JWT access / refresh token
- Authorization header 值
- 请求 body 完整内容
- 用户 email / 手机号(用 user_id 替代)

**实现方式:**
- `from omni_desk_backend.observability import get_logger` 统一获取 logger
- 命名规则:`logger = logging.getLogger("omni_desk.<app>.<event>")`
- 测试用 `caplog` fixture 验证记录字段

**测试:**
- `users/tests/test_auth.py` 验证登录失败有 warning 日志
- `events/tests/test_tasks.py` 验证 Celery 任务开始有 info 日志
- 用 `caplog.records` 断言 `event` / `user_id` 字段

**Acceptance:**
- ✅ 6 类事件至少 4 类有结构化日志
- ✅ 脱敏规范在文档中明示
- ✅ caplog 测试覆盖主要事件
- ✅ 无敏感数据泄漏到日志(手工验证)

### PR-3:django-silk dev 接入

**目标:** dev 模式启用 SQL profiling,开发期间可访问 `/silk/` 看慢查询。

**约束:**
- **仅 dev / local 设置启用**,生产环境永不接入
- `requirements-dev.in` 加 `django-silk`(dev 依赖)
- `INSTALLED_APPS`、`MIDDLEWARE`、`URL` 全部条件化
- 不影响 prod 构建

**配置草稿:**

```python
# settings/local.py / settings/development.py
if DEBUG and os.environ.get("ENABLE_SILK") == "1":
    INSTALLED_APPS += ["silk"]
    MIDDLEWARE.insert(0, "silk.middleware.SilkyMiddleware")
    # urls.py: path("silk/", include("silk.urls", namespace="silk"))
```

**使用方式:**
- 设置 `ENABLE_SILK=1` 环境变量启用
- 访问 `/silk/` 查看 SQL profiling
- 文档写明启用步骤

**文档:**
- 新建 `docs/technical/29-performance-profiling.md`
- 内容:django-silk 启用、SQL 慢查询、请求耗时分析

**Acceptance:**
- ✅ `pip install -r requirements-dev.txt` 不影响 prod 构建
- ✅ `ENABLE_SILK=1` 启动后 `/silk/` 可访问
- ✅ prod 启动时 silk 完全不加载(无 import 副作用)
- ✅ 文档清晰

### PR-4:`src/shared/api` → TypeScript

**范围:** `omni_desk_frontend/src/shared/api/*.js` (11 个文件) → `.ts`/`.tsx`

**文件清单:**

```
apiClient.js
apiClient.test.js
axiosConfig.js
axiosConfig.test.js
compliance.js
deepseek.js
memoApi.js
ollama.js
pageConfigApi.js
pageConfigApi.test.js
permissionsApi.js
permissionsApi.test.js
responseHandler.additional.test.js
responseHandler.js
responseHandler.test.js
sequenceApi.js
sequenceApi.test.js
trialApi.js
trials.js
```

**策略:**
- **优先顺序:** `apiClient` → `axiosConfig` → `responseHandler`(基础设施)→ 业务 API(compliance/memoApi/...)
- 类型基础已存在:`api.d.ts` 已有 `ApiResponse<T>` / `PaginatedResponse<T>` / `PaginationParams` / `ApiError` 等
- **手工标类型**(不引入 `openapi-typescript`,避免新工具依赖)
- 测试文件保持 `.test.js` 不动(jest 配置兼容)

**实施细节:**
- `axiosConfig.js`:导出 `AxiosInstance`、`RequestInterceptor` 类型
- `apiClient.js`:泛型 `apiGet<T>(url): Promise<T>`、`apiPost<T, R>(url, body): Promise<R>`
- 业务 API:按后端 viewset 的 serializer 定义 `interface` 标注入参/出参

**验证:**
- `tsc --noEmit` 0 错误
- `npm run lint` 通过
- `npm test` 不回归
- `npm run build` 通过(25-30s)

**Acceptance:**
- ✅ 所有 11 个非测试 .js 文件转为 .ts
- ✅ 无 `any`(必须时用 `unknown` + 类型守卫)
- ✅ `tsc --noEmit` 0 错误
- ✅ 现有测试不修改即可运行

### PR-5:zod 表单试点

**目标:** 建立"antd Form + zod"模式样板,为后续全量替换铺路。

**试点页面:登录页**(风险最低,业务简单,容易快速验证)。

**集成模式(在登录页实现):**

```ts
import { z } from "zod";

const LoginSchema = z.object({
  username: z.string().min(3, "用户名至少 3 字符").max(64),
  password: z.string().min(8, "密码至少 8 字符").max(128),
});

type LoginFormValues = z.infer<typeof LoginSchema>;

// antd Form: Form.useForm<LoginFormValues>()
// onFinish: LoginSchema.safeParse(values),失败则 antd Form.setFields
// onFinishFailed: 转换 zod 错误为 antd 错误
```

**依赖:**
- `omni_desk_frontend/package.json` 加 `zod`(最新稳定版)
- 锁定版本写入 `package-lock.json`

**文档:**
- 在 `docs/technical/16-smart-assistant.md` 旁新建 `30-form-validation-pattern.md`
- 内容:zod + antd Form 集成模式、错误处理、与 i18n 协同(若有)

**测试:**
- 单测:LoginSchema 边界用例(短/长/空/特殊字符)
- 组件测试:登录页提交空表单 → 显示错误

**Acceptance:**
- ✅ 登录页用 zod schema 校验,不再用 antd 自带 rules
- ✅ 文档章节写明模式与扩展指南
- ✅ 错误提示与原版一致(用户无感)
- ✅ 可作为模板复用到其他表单

### PR-6:动态 import 优化

**目标:** 把 `editor` / `docprocessing` / `markdown` 三个最大 chunk 从初始依赖链拆出。

**当前状态:**
- `vite.config.js` 已配 `manualChunks`,但这些 chunk 仍被初始依赖链拉到 main
- 文档处理 / 编辑器 / Markdown 渲染页面只在用户访问时加载

**策略:**
- `src/routes/index.js` 把这些页面的 import 改为 `React.lazy(() => import('@/pages/...'))`
- 配合 `<Suspense fallback={<Spin />}>` 包裹路由
- 跑 `npm run build` 对比 chunk 数量、首屏 main bundle 体积
- 在 Chrome 109 / Edge 109 跑 dev server,验证所有路由可访问

**文件改动范围(预估):**
- `src/routes/index.js` — 路由 lazy 化
- 必要时的 fallback 组件(可复用 antd `Spin`)

**验证:**
- `npm run build` 体积报告
- `lighthouse` (可选) LCP < 2.5s
- 实际访问每个路由确保可用

**Acceptance:**
- ✅ `editor` / `docprocessing` / `markdown` 不在 main bundle
- ✅ 所有路由可正常加载(无 JS 报错)
- ✅ `docs/technical/22-win7-compatibility.md` 加一行:动态 import 在 Chrome 109 支持
- ✅ main bundle 体积下降(数值记录在 PR 描述)

## 四、实施顺序与并行性

### 串行顺序(单开发者)

```
PR-1 (0.5d) → PR-2 (1.5d) → PR-3 (0.5d) → PR-4 (2d) → PR-5 (1d) → PR-6 (0.5d)
       ↑ 修真实风险   ↑ 可观测性   ↑ 性能工具   ↑ 类型化     ↑ 验证模式  ↑ 构建优化
```

**总工期:6 个工作日**

### 并行可能(2 个开发者)

| 后端开发者 | 前端开发者 |
|-----------|-----------|
| PR-1, PR-2, PR-3 | PR-4, PR-5, PR-6 |

两组无依赖,完全并行。

### 每个 PR 强制流程

每个 PR 都必须遵循 `feature-branch-workflow.md`:

```
1. git switch -c <type>/<scope>  # 从最新 main 拉新分支
2. 写代码 + 写测试 + commit(可多次)
3. pytest / build / smoke test 本地通过
4. git push -u origin <branch>
5. gh pr create
6. 等 CI 绿 → gh pr checks --watch
7. AI 检阅 → 用户 merge
8. 合并后 git push origin --delete + git branch -d
```

每个 PR 描述必须包含:
- 关联本次设计文档(本文件)
- Acceptance checklist
- 测试覆盖说明
- 截图/数据(若有)

## 五、风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| PR-1 分页修改破坏前端契约 | 中 | 决策前 grep 前端调用方,加 e2e 测试,PR 描述标注决策依据 |
| PR-2 日志泄露 PII | 中 | 脱敏规范在文档明示,PR review 检查日志字段,caplog 测试覆盖 |
| PR-3 silk 影响 prod 启动 | 低 | 条件分支严控,prod 完全不 import silk |
| PR-4 TS 转换类型定义不准确 | 中 | 优先基础设施,业务 API 用 any 过渡(标 TODO),后续 PR 完善 |
| PR-5 zod 错误提示不一致 | 低 | 与原 antd rules 提示文案对齐 |
| PR-6 React.lazy 在 Win7 Chrome 109 异常 | 低 | 实测验证,有问题回退 |
| CI 在 TS 转换期误报 | 低 | `tsc --noEmit` 单独跑,与 jest 解耦 |

## 六、依赖

### 后端新增

- `django-silk`(dev-only,写 `requirements-dev.in`)

### 前端新增

- `zod`(latest stable)

### 已有依赖(复用)

- `python-json-logger`(阶段 4 已装)
- `pytest` + `pytest-cov`(覆盖率)
- TypeScript + `tsconfig.json`(阶段 6 试点已配)
- Vite 5.4 manualChunks(阶段 3 已配)

## 七、Definition of Done

每个 PR 的 DoD:

- [ ] 所有 acceptance 标准达成(本文件 §三 每 PR 列项)
- [ ] 覆盖率不下降(`pytest --cov-fail-under=80` 仍通过)
- [ ] CI 全绿(backend / frontend / security / lint)
- [ ] PR 描述含关联本设计文件的链接
- [ ] 代码 review 通过(AI + 人工)
- [ ] 合并后分支已删除

整个项目的 DoD:

- [ ] 6 个 PR 全部合并
- [ ] 路线图所有 `[ ]` 项(本设计覆盖范围)变 `[x]`
- [ ] 主项目 README 或 CHANGELOG 提及本次优化(可选)
- [ ] 新文档章节纳入 `docs/technical/README.md` 章节目录

## 八、关联文档

- 上游路线图:`docs/plans/2026-06-05_project-optimization-roadmap.md`
- 安全基线:`docs/technical/24-security-checklist.md`
- API 性能审计:`docs/technical/25-api-performance-audit.md`
- 项目元信息:`CLAUDE.md`、`AGENTS.md`
- 流程规范:`~/.claude/rules/common/feature-branch-workflow.md`
