# 核心链路断点修复计划

## 背景与目标

核心链路巡检显示，Django 后端和 React 前端的基础测试总体稳定，但真实部署验收、离线包、升级回滚以及部分前后端接口之间存在断点。主要问题集中在：部署验收检查了不存在的服务、CI 使用过期镜像标签、Browser E2E 跨 Runner 访问 localhost、离线包脚本依赖工作目录、回滚依赖未随包发布、两套制品校验 schema 不一致，以及修改密码和部分前端认证/权限链路契约漂移。

本计划目标是恢复以下可验证闭环：

```text
构建镜像 → 生成离线包 → 校验制品 → 离线部署 → 健康检查
→ 业务冒烟 → 浏览器验收 → 升级 → 备份验证 → 回滚
```

修复必须保持离线优先、严格模式 fail-closed、Windows 7/Chrome 109 兼容要求，并避免凭静态扫描结果臆测仍在使用的业务功能。

## 涉及的文件与模块

### 部署、离线包与 CI

- `deployment/docker/deploy_tests.sh`
- `deployment/docker/package_offline_bundle.sh`
- `deployment/docker/verify.sh`
- `deployment/docker/validate_artifacts.sh`
- `deployment/docker/verify_backup_batch.sh`
- `deployment/docker/smoke_common.sh`
- `deployment/docker/smoke_tests.sh`
- `deployment/docker/deploy_offline.sh`
- `deployment/docker/rollback.sh`
- `deployment/docker/tests/` 下相关 shell 测试
- `deployment/docker/docker-compose.offline.yml`
- `.github/workflows/deploy-test.yml`
- `.github/workflows/ci.yml`（仅在需要补充契约门禁时修改）

### 前端、后端接口与 E2E

- `omni_desk_frontend/src/features/profile/components/ChangePasswordForm.jsx`
- `omni_desk_frontend/src/features/profile/components/__tests__/ChangePasswordForm.test.jsx`
- `omni_desk_frontend/src/features/auth/` 下认证上下文、Axios 和测试
- `omni_desk_frontend/src/features/auth/components/ProtectedRoute.jsx`
- `omni_desk_frontend/src/routes/index.jsx`
- `omni_desk_frontend/e2e/helpers/api-fixtures.js`
- `omni_desk_frontend/e2e/auth-and-routes.spec.js`
- `omni_desk_backend/users/` 及相关 API contract 测试（仅在确认需要补齐 `export-trials` 时扩展）

### 计划与文档

- `docs/plans/2026-08-26_core-chain-breakpoint-repair.md`
- 若业务契约确认发生变化，再同步 `docs/technical/` 对应章节，不新增与现有手册重复的历史文档。

## 技术方案

### 1. 部署拓扑与 CI 验收

以当前离线 Compose 为事实来源：`frontend` 同时提供静态资源和 API 反向代理，不为不存在的 `nginx` 服务新增临时容器。部署测试的 required 服务只包含 Compose 中实际存在且对验收必要的服务。前端 API 配置检查改为验证构建/代理契约，而不是读取构建后不会存在的 `REACT_APP_API_BASE_URL` 运行时变量。

CI 使用 `deployment/docker/VERSION` 动态生成 backend/frontend 镜像 tag，并在身份校验阶段确保 VERSION、manifest、Compose 镜像引用一致。Browser E2E 与启动 Compose 的步骤放入同一个 Runner/job，保证浏览器访问的 `localhost` 就是被验收的服务；清理步骤使用 `if: always()`。

### 2. 离线包路径与制品契约

脚本统一以自身位置推导源码树或 bundle 根目录，生成绝对路径，禁止依赖调用者 `$PWD`。bundle 的唯一生产制品契约为：

```text
<bundle>/images/
<bundle>/CHECKSUMS.sha256
<bundle>/BUILD-MANIFEST.json
<bundle>/VERSION
```

`verify.sh` 和 `validate_artifacts.sh` 先将输入归一化到上述结构，再执行相同的文件、checksum、manifest 和镜像可加载性检查。打包清单必须包含回滚所需的 `verify_backup_batch.sh`，并由 `verify.sh` 强制检查。

### 3. 备份批次安全闸

`verify_backup_batch.sh` 对 `metadata.json` 的 `restore_verified` 执行 JSON 类型和值校验，只有布尔值 `true` 才通过；字符串 `"true"`、数字、`false`、`null` 和缺失字段均拒绝。外部 verifier 与 `deploy_offline.sh` 的 fallback 必须采用相同语义，并保留 checksum、文件大小、tar 成员路径和批次文件归属校验。

### 4. 业务 API 与认证契约

修改密码前端调用改为后端实际路径 `/api/users/me/change-password/`，同步更新前端测试并增加防止路径漂移的 contract 覆盖。`TrialsPage` 的 `export-trials` 在实施前先确认产品需求和后端完整路由；若仍需使用则补齐后端 endpoint、权限、文件响应和测试，若已废弃则移除前端入口，不保留必然 404 的按钮。

Axios 读取 Web Storage 中的 token 时保护非法 JSON，避免损坏的本地存储阻止所有 API 请求。页面权限不再依赖 `ProtectedRoute` 忽略的 `pageName/pagePath` 隐式参数；在确认现有权限数据结构后，优先由路由显式传入 `permissions`，并保持后端 API 鉴权独立有效。

Playwright 登录 helper 按后端实际 JSON token 响应工作，将 access/refresh token 写入前端使用的 Web Storage，再加载受保护页面；不依赖不匹配的 cookie 行为。缺少 E2E 凭据时继续 fail-fast。

## 实施步骤

### 阶段 P0：恢复部署验收硬门禁

- [x] 为 `deploy_tests.sh` 增加/更新失败用例，覆盖不存在的 `nginx`、实际 Compose 服务列表和 API 代理契约。
- [x] 从 required 服务列表移除不存在的 `nginx`，修正前端 API 配置检查。
- [x] 为 CI 镜像标签动态化先补身份校验测试/脚本断言。
- [x] 修改 `.github/workflows/deploy-test.yml`，让镜像 tag 与 VERSION 一致。
- [x] 合并部署启动、deploy tests、Browser E2E 和 cleanup 到同一可访问服务拓扑。
- [x] 运行 P0 shell/文本契约测试；若 Docker 可用，执行一次真实 Compose 健康检查和部署验收。
- [ ] 补 CI Compose 所需的 `postgres:14-alpine` / `redis:7-alpine` / `mysql:8.0` / `infiniflow/ragflow:v0.16.0` 镜像加载（runner 缺图）。
- [x] 在 deploy-test job 中以 `SMOKE_TEST_USER/PASSWORD` 创建幂等测试账号，并喂入 `E2E_USERNAME/PASSWORD`。
- [x] 用每次运行唯一 `COMPOSE_PROJECT_NAME=omnidesk-ci-${github.run_id}-${github.run_attempt}` 隔离并发验收。
- [x] 修复 E2E helper JWT 写入 Storage（写入 `sessionStorage.authTokens`；补 19/19 单测覆盖 getCredentials/getUserCredentials/requireCredentials/requireUserCredentials/performLogin 全部路径）。
- [x] J6 角色化：引入独立 `E2E_USER_*` 凭据，禁止以用户名关键字决定 skip。

### 阶段 P1：修复离线包布局与制品校验

- [x] 先补源码树与 bundle 两种布局下从任意工作目录执行的路径回归测试。
- [x] 统一 `smoke_common.sh`、`package_offline_bundle.sh`、`deploy_offline.sh`、`rollback.sh` 的绝对路径推导和参数传递。
- [x] 将 `verify_backup_batch.sh` 纳入 offline bundle，并加入 `verify.sh` 必需文件清单。
- [x] 统一 `verify.sh` 与 `validate_artifacts.sh` 的根级制品 schema、文件名大小写和 manifest 字段。
- [x] 增加 package → verify → validate 连续测试；不得只验证源码目录中的静态文件。
- [x] 运行 shell 测试、生成临时 bundle、执行 verify/validate 并检查 bundle 外工作目录调用。

### 阶段 P2：恢复安全闸与业务接口

- [x] 先补 `restore_verified` 缺失、`false`、字符串、非布尔值、路径穿越和 checksum mismatch 测试。
- [x] 实现严格布尔校验，并统一 verifier/fallback 行为。
- [x] 为修改密码路径漂移补前端 API contract 测试。
- [x] 修改 `ChangePasswordForm.jsx` 和对应测试，验证成功与错误响应。
- [x] 调查 `export-trials` 的产品需求、后端 URL 和权限定义；只有契约确认后才补 endpoint 或移除入口。
- [x] 运行后端相关 pytest、前端相关 Jest 和安全输入校验测试。

### 阶段 P3：页面权限与真实浏览器会话

- [ ] 先梳理路由配置、权限 API 返回值和现有 `pageName/pagePath` 使用者，写出显式权限映射测试。
- [ ] 修改 `ProtectedRoute`/路由配置，使关键管理页显式执行权限判断。
- [ ] 补充已登录但无权限、guest、匿名和 admin 场景测试。
- [ ] 补 Axios 非法 token JSON 的回归测试并实现安全清理/认证失败行为。
- [ ] 修改 Playwright helper，使用 Web Storage 建立真实 JWT 浏览器会话。
- [ ] 在同一部署 job 中运行匿名、guest、正常登录、refresh、普通用户访问 admin 和静态资源验收。

### 全量验收与审查

- [ ] 执行后端全量 pytest 与覆盖率检查（目标 ≥80%）。
- [ ] 执行前端 Jest、覆盖率、ESLint 和 Vite build。
- [ ] 执行 shell 单元/集成测试。
- [ ] 在 Docker 可用环境执行真实离线 bundle verify/validate、Compose deploy-test、smoke、升级 dry-run 和回滚验证。
- [ ] 执行 `code-reviewer`，检查逻辑、测试和项目规范。
- [ ] 执行 `security-reviewer`，重点检查 shell 参数、路径处理、认证 token、备份恢复和外部输入。
- [ ] 将已完成步骤标记为 `[x]`；若全部完成，按项目文档规范将有效技术说明并入对应章节并删除本计划文件。

## 验收标准

1. 严格模式下不存在把 `SKIP`/`WARN` 当作成功的部署验收路径。
2. `deploy_tests.sh` 只检查实际 Compose 服务，且不依赖不存在的运行时前端变量。
3. CI 不再使用固定的过期 `v0.4.0` 镜像 tag，镜像身份与 VERSION/manifest 一致。
4. 从任意当前工作目录执行 bundle 脚本均能定位 compose、env、scripts 和 images。
5. 生成的 bundle 同时通过 `verify.sh` 与 `validate_artifacts.sh`，并包含回滚 verifier。
6. `restore_verified` 只有 JSON boolean `true` 才能通过。
7. 修改密码请求命中后端真实 endpoint；疑似导出入口不存在时不会保持死链。
8. 关键路由权限判断与配置一致；真实 JWT token 能驱动浏览器登录和 refresh。
9. 后端、前端、shell、Docker 验收和安全审查均有明确结果，失败项不得被静默跳过。

## 风险评估与依赖

| 风险/依赖 | 影响 | 应对 |
|---|---|---|
| Docker daemon、镜像构建或离线依赖不可用 | 无法完成真实部署验收 | 先完成无 Docker 的契约测试；明确报告真实验收未执行，不宣称通过 |
| E2E secrets 未配置 | Browser E2E 无法登录 | CI 保持 fail-fast；本地使用明确的 guest 模式或专用测试凭据 |
| `export-trials` 产品语义不明确 | 错删功能或新增错误 API | 先查后端路由、前端入口、文档和产品契约，再决定实现/移除 |
| 页面权限映射规则不完整 | 误放行或误拒绝页面 | 先以现有权限 API/菜单数据建立测试，再做最小显式映射 |
| 旧离线包是历史产物 | 仅修改源码不能修复旧包 | 重新生成临时 bundle 验证；旧包不作为修复成功证据 |
| 生产 HTTP/HTTPS 配置差异 | `check --deploy` 警告被误判为故障 | 分离内网 HTTP 验收与 HTTPS 生产安全检查，不降低生产门禁 |
| 修改脚本路径/Compose 参数引入数据风险 | 升级或回滚失败 | 先执行 dry-run 和批次校验，再执行真实恢复；失败保留 SAFE_STOPPED 现场 |
