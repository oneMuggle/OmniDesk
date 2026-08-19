# 部署前测试与可观测性加固计划

**日期**: 2026-08-17
**状态**: 待评审
**范围**: 测试体系补强 + 冒烟测试补盲 + 日志链路打通

---

## 1. 背景与目标

### 背景

在内网离线部署前对项目做了一次全面评估,覆盖四个维度:后端测试、前端测试、冒烟测试/发布验证、日志与可观测性。

**实测基线**(2026-08-17,`pytest --cov=.` 全量跑):

| 指标 | 实测值 | 说明 |
|---|---|---|
| 后端测试通过 | 2571 passed, 2 xfailed, 11 xpassed, 0 failed | 189 秒 |
| 后端业务代码覆盖率 | **83.57%** (12651/15139 行) | 已剔除测试文件自身 |
| 后端含测试文件覆盖率 | 92.69% | CI 门禁读的是这个数(虚高) |
| 测试代码占总行数 | 58.9% | |
| 前端测试文件数 | 115 | features 源文件 190 + shared 89 |
| 前端覆盖率阈值 | branches 18% / lines 24% | `jest.config.js:28-33`,强制生效但水位极低 |
| 后端 CI 门禁 | `--cov-fail-under=80` | `ci.yml:91`,真实生效,近期全绿 |

**结论概括**:

- 后端测试**扎实**,可以放行
- 前端覆盖率门槛**形同虚设**,关键降级路径无测试
- E2E **完全是坏的**(选择器全部失效且不在 CI 跑,因此无人发现)
- 冒烟测试内核扎实,但"配置错了仍能跑"这类故障全漏
- 日志 request_id 骨架优秀,但**前后端两端都断了**,线上出问题无法快速定位

### 目标

1. 补上"内网现场会真炸"的冒烟检查项(CORS/CSRF/Cookie、真实账密登录)
2. 打通日志链路,使一次用户请求可从浏览器串到 Django 再串到 Celery
3. 让浏览器侧错误对运维可见(当前完全失明)
4. 修复或移除坏掉的 E2E,消除"有 E2E"的虚假安全感
5. 消除已知配置矛盾(browserslist vs vite target)

### 不在本次范围

- 前端覆盖率提升到 80%(工作量过大,本次只抬到 40% 作为止血)
- 引入 ELK / Sentry(内网环境约束)
- 后端整体覆盖率提升(已达 83.57%,仅补个别高危模块)

---

## 2. 涉及的文件与模块

### 后端

| 文件 | 改动类型 |
|---|---|
| `omni_desk_backend/ragflow_service/views.py:64,79,94,106` | 补 `exc_info=True` |
| `omni_desk_backend/ragflow_service/client.py:109,113` | 补 `exc_info=True` |
| `omni_desk_backend/documents/file_processing.py:59,74,104,114,126` | 补 `exc_info=True` |
| `omni_desk_backend/file_processing/tasks.py:32,37` | 补 `exc_info=True` |
| `omni_desk_backend/llm_service/ollama_client.py:89,124` | 补 `exc_info=True` |
| `omni_desk_backend/permissions/views.py:73` | 补 `exc_info=True` |
| `omni_desk_backend/events/views/trials.py:88` | 补 `exc_info=True` |
| `omni_desk_backend/smart_assistant/views/chat_sync.py:184` | 移除 token 明文 |
| `omni_desk_backend/core/exception_handler.py` | **新增** DRF 异常处理器 |
| `omni_desk_backend/core/api.py` | **新增** 前端错误上报端点 |
| `omni_desk_backend/observability/events.py` | 新增事件常量 |
| `omni_desk_backend/omni_desk_backend/settings/base.py:189` | 新增 celery logger 配置 |
| `omni_desk_backend/events/schedule_generator.py` | 补测试(当前 15.2%) |

### 前端

| 文件 | 改动类型 |
|---|---|
| `omni_desk_frontend/src/shared/api/axiosConfig.ts` | 回写 `X-Request-ID` |
| `omni_desk_frontend/src/shared/utils/logger.js` | 增加后端上报通道 |
| `omni_desk_frontend/src/shared/components/ErrorBoundary.jsx:16` | 接入上报 |
| `omni_desk_frontend/src/main.jsx` | 注册全局错误监听 |
| `omni_desk_frontend/package.json:54` | browserslist 改 `chrome >= 109` |
| `omni_desk_frontend/jest.config.js:28-33` | 阈值抬到 40% |
| `omni_desk_frontend/e2e/paperless-integration.spec.js` | **删除**(决策项 1) |
| `omni_desk_frontend/playwright.config.js` | **删除**(若存在) |
| `omni_desk_frontend/src/features/admin/components/SystemConfigTab.test.jsx:5` | 删除 skip 空壳 |
| `omni_desk_frontend/src/features/dify-apps/pages/DifyAppList.test.jsx:5` | 删除 skip 空壳 |

### 部署与 CI

| 文件 | 改动类型 |
|---|---|
| `deployment/docker/smoke_tests.sh` | 新增阶段 12/13 |
| `deployment/docker/docker-compose.offline.yml:103` | healthcheck 切 `/api/system/ready/` |
| `deployment/docker/docker-compose.prod.yml:42` | gunicorn 补 `--error-logfile -` |
| `.github/workflows/deploy-test.yml` | 接入 `smoke_tests.sh`(P1-4) |
| `.github/workflows/ci.yml` | 不变(E2E 已移除,无新增 job) |

---

## 3. 技术方案

### 3.1 日志链路打通(核心)

当前 request_id 传播链路:

```
浏览器 ──✗断── Django Middleware ──✓── ContextVar ──✓── Celery task header ──✓── worker
                (core/middleware.py:10)   (observability/context.py:15)  (celery.py:19-65)
```

已实现部分质量很高(`SafeTextFormatter` 处理字段缺失、`task_prerun/postrun` 信号恢复上下文),
**只需补上浏览器这一端**。

**方案**:

1. 前端 axios response interceptor 读取 `X-Request-ID` 响应头,存入内存变量
2. request interceptor 将其写入下一次请求的 `X-Request-ID` header
3. 后端 `RequestIdMiddleware` 已支持读取入站 header(`core/middleware.py:12`),无需改动

### 3.2 前端错误上报

**当前状态**:`ErrorBoundary.jsx:16` 只调 `logger.error`,而 `logger.js:7` 实现是
`console.error` —— 内网现场无法访问浏览器 console,等于完全失明。

**方案**:

```
window.onerror              ─┐
window.unhandledrejection   ─┼─→ logger.report() ─→ navigator.sendBeacon()
ErrorBoundary.componentDidCatch ─┘                        ↓
                                          POST /api/system/client-error/
                                          (AllowAny + 限流 + payload 脱敏 + 结构化落日志)
```

用 `sendBeacon` 而非 `fetch`,避免页面卸载时丢包。端点认证策略选 **AllowAny + 强限流**(决策项 2):

- 决策依据:本次目标"部署前尽量暴露问题",未登录错误是盲区,需覆盖
- DDoS 风险用**强限流**(10/min/IP) + payload 重复去重控制
- 前端 `logger.report()` 上报前**过滤敏感字段**(`password`/`token`/`refresh`/`secret` 键)
- 后端 throttle 类用 DRF `UserRateThrottle`,scope 独立命名为 `client_error`

### 3.3 冒烟测试补盲

在 `smoke_tests.sh` 现有 11 阶段后追加:

**阶段 12 — 鉴权与跨域链路**

| 检查 | 期望 | 失败动作 |
|---|---|---|
| `curl -H "Origin: <配置域名>" -i /api/auth/guest-login/` | 返回 `Access-Control-Allow-Origin` | FAIL |
| `curl -H "Origin: http://evil.com"` | 被拒 | FAIL |
| 真实账密 POST `/api/auth/login/`(用 `.env` 注入的 smoke 专用账号) | 200 + JWT | FAIL |
| 登录响应 `Set-Cookie` 的 `Secure` 属性 | 与 `.env.production` 的 `USE_HTTPS` 一致 | FAIL |

> 第 4 条直接对应 CLAUDE.md 已记录的第 10 条坑(USE_HTTPS 配错导致登录立即丢会话)。
> 第 3 条覆盖 `test.py` 用 MD5 hasher、`production.py` 用 argon2 的差异风险。

**阶段 13 — readiness 与静态资源**

| 检查 | 期望 |
|---|---|
| `curl /api/system/ready/` | 200 且 `checks.database/cache/celery` 全 ok |
| 从 `index.html` 解析 lazy chunk 引用并逐个 curl | 全部 200 |

`/api/system/ready/` 在 `core/api.py:148` **已实现但无人调用** —— 同时检 DB + Redis + Celery
三依赖,比当前 healthcheck 用的 `/api/health/`(只检 DB)强得多,属于现成资产闲置。

### 3.4 E2E 决策

`e2e/paperless-integration.spec.js` 当前状态:

- 引用 7 个 `data-testid`(`upload-doc-btn` / `document-list` / `search-bar` 等),**src 下一个都不存在**(已 grep 确认)
- 登录用 `input[name="username"]`,但 Login 页是 Ant Design Form(只有 placeholder)
- CI 中 0 处调用 playwright,因此这个必然失败的文件从未被发现

**决策**:**移除**(决策项 1,理由三条):

1. paperless-ngx 服务依赖内网未必就绪(部署脚本里没有它的镜像),E2E 接 CI 必然频繁红灯
2. documents 模块 API 已有 `test_documents_api.py` 覆盖,端到端保护不缺失,只是缺 UI 验证
3. 真正可被推迟到 P2(待 paperless 服务确认就绪后),而不是赶在部署前

**执行**:

- 删 `omni_desk_frontend/e2e/paperless-integration.spec.js`
- 删 `omni_desk_frontend/playwright.config.js`(若存在)
- 不再保留任何"假装有 E2E"的痕迹
- 在 `package.json` 的 `scripts` 中移除 playwright 相关命令(若存在)
- 后续若 paperless 服务确认就绪,**P2 阶段重建**

---

## 4. 实施步骤

### 阶段 P0 — 上线前必须完成

- [ ] **P0-1** 前端全局错误上报
  - [ ] 后端新增 `POST /api/system/client-error/`(认证 + 限流 + 结构化日志)
  - [ ] 前端 `logger.js` 增加 `report()` 走 `sendBeacon`
  - [ ] `main.jsx` 注册 `window.onerror` 与 `unhandledrejection`
  - [ ] `ErrorBoundary.jsx:16` 接入上报
  - [ ] 补对应单元测试
- [ ] **P0-2** axios 回写 `X-Request-ID`,打通前后端链路 + 测试
- [ ] **P0-3** 补齐 8 处 `logger.error` 的 `exc_info=True`(纯机械改动)
- [ ] **P0-4** `chat_sync.py:184` 移除 `confirm_token` 明文(改记 `tool_name` 或 token 前 4 字符)
- [ ] **P0-5** `smoke_tests.sh` 新增阶段 12(CORS/CSRF/Cookie + 真实账密登录)
- [ ] **P0-6** compose healthcheck 切到 `/api/system/ready/`

**验收标准**:一次前端报错能在 `docker logs backend | grep req=<id>` 中查到,
且该 rid 能关联到对应的 Celery 任务日志。

### 阶段 P1 — 上线前尽量完成

**全部纳入本次发布范围**(决策项 4,P1-6 推迟至下个发布周期)。

- [ ] **P1-1** 删除坏掉的 E2E(`paperless-integration.spec.js` + playwright 配置,见 §3.4)
- [ ] **P1-2** browserslist 统一为 `chrome >= 109`,验证构建产物无 ES2022+ 语法
- [ ] **P1-3** 补 `events/schedule_generator.py` 测试(当前 15.2% → 目标 70%)
- [ ] **P1-4** `smoke_tests.sh` 接入 `deploy-test.yml`;阶段 10 的 SKIP 改 FAIL
- [ ] **P1-5** 删除 `describe.skip` 空壳测试(SystemConfigTab / DifyAppList 等)
- [ ] **P1-7** `smoke_tests.sh` 新增阶段 13(readiness + 静态 chunk)
- [ ] **P1-8** 新增 DRF `EXCEPTION_HANDLER`,保证未捕获 500 带 rid + 堆栈

**P1-6(前端覆盖率阈值 18% → 40%)推迟**:此改动影响团队开发节奏(任何新代码若未达 40% 将导致 CI 红),
属于政治性决策,需团队共识,不与本批次一同发布。下个发布周期单独评估。

### 阶段 P2 — 上线后迭代

- [ ] **P2-1** `axiosConfig.test.js` 重写:删除 simulate 函数,改真实 axios mock,覆盖并发 401 队列
- [ ] **P2-2** 补 `ErrorBoundary` / `LazyComponent` 测试(离线部署 chunk 失败降级)
- [ ] **P2-3** Celery logger 纳入 Django LOGGING(`base.py:189` 加 `celery` 键)
- [ ] **P2-4** `observability/events.py` 补事件常量,替换全项目 magic string
- [ ] **P2-5** 补低覆盖模块:`inventory_service.py`(21.2%) / `smart_assistant/views/tasks.py`(31.8%) / `documents/views/books.py`(45.8%)
- [ ] **P2-6** gunicorn 补 `--error-logfile -` 与 `--capture-output`
- [ ] **P2-7** 编写《生产事故排查 SOP》→ `docs/technical/41-incident-response.md`

---

## 5. 风险评估与依赖

### 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| 前端错误上报端点被刷爆(错误循环触发上报) | 高 | 后端限流 + 前端本地去重(同一 error message 60s 内只报一次) |
| 上报端点本身要求认证,但未登录时的错误报不上来 | 中 | 端点设 `AllowAny` + 严格限流,或前端在未认证时降级为 console |
| 冒烟阶段 12 需要真实账密,凭据管理 | 中 | 用专用 smoke 账号,凭据走 `.env` 注入,不硬编码 |
| browserslist 改 109 后构建产物变化 | 中 | 改动后必须在 Chrome 109 实机或等价环境验证 |
| 阶段 10 SKIP 改 FAIL 后冒烟频繁红灯 | 中 | 先观察一个发布周期,确认非误报再强制 |
| E2E 补 testid 需要改大量业务组件 | 低 | 若工作量超预期,退回选项 B(移除) |

### 依赖

- P0-1 的前端上报依赖后端端点先落地 → **P0-1 内部有序**
- P0-5 冒烟阶段 12 依赖已有的 `.env.production` 配置项(`USE_HTTPS` / `CORS_ALLOWED_ORIGINS`)
- P1-4 接入 CI 依赖 P0-5/P1-7 的新阶段先稳定
- P1-1 若选"修复",依赖前端组件补 testid,与 P1-6 覆盖率提升有重叠工作面

### 已知无需处理

评估中曾被误报、经实测排除的问题(记录以免后续重复调查):

- ~~后端覆盖率仅 27.74%,CI 门禁失效~~ → 实测业务代码 83.57%,CI 门禁真实生效
- ~~前端 coverageThreshold 不强制~~ → `npm test` 会 fail,确实强制,只是水位低
- ~~smoke_tests.sh 完全不在任何流程~~ → 随离线包分发,由 `upgrade.sh:418` / `rollback.sh:297` 调用,
  仅"不在 CI"这点成立

---

## 6. 决策记录(已确认)

| # | 决策项 | 选择 | 关键依据 |
|---|---|---|---|
| 1 | E2E 走哪条路 | **B. 移除** | paperless 服务依赖未必就绪;documents API 已有覆盖 |
| 2 | 错误上报端点认证 | **B. AllowAny + 限流(10/min/IP)+ payload 脱敏** | 未登录错误是盲区;内网 DDoS 非主要威胁 |
| 3 | smoke 真实账密账号 | **B. 专用 smoke 账号 + .env 注入** | 符合 CLAUDE.md 凭据规范 |
| 4 | P1 范围 | **P1-1/2/3/4/5/7/8 全做;P1-6(阈值)推迟** | 阈值改动属政治性决策,单独评估 |

### smoke 账号细节(决策项 3 补充)

- **账号名**:`smoke-test-bot`(待用户提供正式名)
- **凭据注入**:`.env.production` 增 `SMOKE_TEST_USER` / `SMOKE_TEST_PASSWORD`
- **权限范围**:仅 `api/system/client-error/` 之外的**登录端点**(实际由 DRF 默认控制,无需额外配置;若权限过大则在 User 上设 `is_staff=False, is_superuser=False` + 仅授予 `auth.login` 权限组)
- **生命周期**:账号常驻,密码定期轮换
- **CI 同步**:GH Actions secrets 配 `SMOKE_TEST_USER/PASSWORD`,与 `.env.production` 同值

---

## 7. 证据索引

评估过程的关键实测命令,便于复核:

```bash
# 后端全量测试 + 覆盖率
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --cov=. --cov-report=term -q
# → 2571 passed, TOTAL 92.69%(含测试文件),业务代码 83.57%

# 确认 E2E testid 不存在
grep -rn 'data-testid="upload-doc-btn"' omni_desk_frontend/src   # → 空

# 确认 CI 覆盖率门禁真实存在
grep -n "cov-fail-under" .github/workflows/ci.yml                # → ci.yml:91

# 确认 CI 不跑 E2E
grep -rn "playwright" .github/workflows/                          # → 空

# 确认 browserslist 与 vite target 矛盾
grep -A3 browserslist omni_desk_frontend/package.json             # → chrome >= 86
grep -n "target: 'chrome109'" omni_desk_frontend/vite.config.js   # → 46,51,58
```
