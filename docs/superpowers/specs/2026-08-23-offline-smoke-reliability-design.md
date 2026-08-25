# 离线部署冒烟测试可靠性设计

## 背景与目标

当前 OmniDesk 的 `smoke_tests.sh` 覆盖了核心容器、数据库、Redis、Celery、主要业务接口、卷持久化、备份恢复、CORS 和前端资源，但源码目录、离线包目录和测试脚本之间存在路径契约不一致；同时 `unhealthy` 容器、真实业务 4xx/5xx、限流、测试数据清理和并发资源隔离存在假通过或污染风险。

目标是让源码目录和离线包中的部署验证可以直接执行，并让失败结果可信：

- 健康检查异常必须阻断；
- 业务错误不能默认变成 `SKIP`；
- 测试只使用可回收的隔离数据；
- 同一 Compose 项目不能并发运行冲突的 smoke；
- 离线包必须验证真实的加载和启动闭环；
- 升级失败必须验证真实恢复，而不是只验证状态文件；
- 前端部署验收必须包含浏览器级关键流程，不能把 Jest 或静态资源检查当作 E2E。

## 设计范围

本设计覆盖以下现有边界：

- `deployment/docker/smoke_tests.sh`：完整业务冒烟测试、失败判定、资源清理、并发隔离。
- `deployment/docker/deploy_tests.sh`：基础部署连通性测试和源码/离线包路径兼容。
- `deployment/docker/validate_artifacts.sh`：源码导出目录和离线包 `images/` 目录的统一校验。
- `deployment/docker/package_offline_bundle.sh` 与生成的 `scripts/deploy.sh`：脚本打包、统一入口、端口和 Compose 上下文传递。
- `deployment/docker/upgrade.sh`、`rollback.sh` 及其集成测试：真实目标版本验证和失败恢复。
- `.github/workflows/ci.yml` 及部署验证 workflow：把必要验证接入阻断门禁。
- `omni_desk_frontend`：新增浏览器级部署验收测试入口。

不在本次范围内：

- 重写业务 API；
- 改变生产限流、认证或 CORS 策略；
- 将现有 shell 测试整体重写为 Python；
- 修改 RAGFlow 本身；
- 在生产卷或真实生产凭据上运行 destructive smoke；
- 引入与部署验收无关的前端重构。

## 架构方案

### 统一测试上下文

新增共享 helper `deployment/docker/smoke_common.sh`，负责解析脚本目录、bundle 根目录、Compose 文件、env 文件、Compose project、BASE_URL、run id 和锁，并提供统一的 Compose 调用、临时文件、HTTP 和服务状态辅助函数。

公开接口：

- `init_smoke_context [base_url]`
- `compose <args...>`
- `resolve_artifact_dir [dir]`
- `smoke_temp_file <name>`
- `acquire_smoke_lock`
- `release_smoke_lock`
- `check_service_health <service> [required|optional]`
- `request_with_status <method> <url> [curl args...]`
- `classify_http_status <code> <label>`

上下文变量：

- `SCRIPT_DIR`
- `BUNDLE_DIR`
- `COMPOSE_DIR`
- `COMPOSE_FILE_PATH`
- `ENV_FILE_PATH`
- `COMPOSE_PROJECT_NAME`
- `BASE_URL`
- `SMOKE_RUN_ID`

源码模式默认使用 `deployment/docker/docker-compose.offline.yml` 和 `.env.production`；离线包模式默认使用 `../compose/docker-compose.offline.yml` 和 `../compose/.env.production`。所有路径允许由显式环境变量覆盖，但不依赖调用方当前工作目录。

默认值：

- `SMOKE_BASE_URL=http://localhost`
- `SMOKE_STRICT=1`
- `SMOKE_ALLOW_NETWORK_SKIP=0`
- `SMOKE_ALLOW_RATE_LIMIT_SKIP=0`
- `SMOKE_RUN_ID=<UTC 秒>-<PID>`

`SMOKE_STRICT=1` 时，任何未被明确标记为 optional 的 `SKIP` 都会使运行失败。锁使用 `flock`，同一 `COMPOSE_PROJECT_NAME` 的第二个 destructive smoke 返回退出码 2；退出码 2 表示并发冲突，不伪装成产品测试失败。

### 验证层次

验证分为四层，各层职责不重叠：

1. `verify`：验证离线包文件、checksum、manifest、镜像 tar 和脚本布局，不负责服务可用性。
2. `deploy-test`：验证 Compose 能在隔离项目中启动，核心服务和 worker healthy，生产 entrypoint、迁移、静态文件和基础 API 正常。
3. `smoke`：验证部署后的 HTTP、认证、关键业务、Celery、卷持久化、备份恢复、CORS 和前端资源。
4. `upgrade/rollback-test`：验证真实镜像切换、迁移失败恢复、数据库/media 恢复、恢复后的 health 和状态机终态。

四层复用同一个上下文和结果契约，但 `verify` 不依赖运行中的服务，`deploy-test` 与 `smoke` 不得将 `verify` 的通过解释为部署可用。

## 行为契约

### 结果分类与退出码

结果分类统一为 `PASS`、`FAIL`、`WARN`、`SKIP`。默认规则如下：

- 必需服务缺失、非 running、starting 超时或 unhealthy：`FAIL`。
- 核心服务没有 healthcheck：`FAIL`；明确声明为 optional 的服务才允许 `SKIP`。
- HTTP 2xx 且满足接口内容约定：`PASS`。
- 业务 4xx、5xx、未知状态码和空响应：`FAIL`。
- 429：默认 `FAIL`；只有 `SMOKE_ALLOW_RATE_LIMIT_SKIP=1` 时降级为 `WARN`。
- curl 网络错误或状态码 000：默认 `FAIL`；只有 `SMOKE_ALLOW_NETWORK_SKIP=1` 时允许 `SKIP`。
- optional 服务未启用：必须输出带服务名和原因的 `SKIP`，不能只输出通用 WARN。
- `SMOKE_STRICT=1` 时，`WARN` 和未授权 `SKIP` 均使最终退出码非零。

最终成功条件是 `FAIL=0`、没有未授权 `SKIP`，并且所有 required 检查已经完成。清理逻辑必须保留原始失败码，不能由 `trap` 或 cleanup 覆盖。

### 健康检查

服务健康状态按以下规则解释：

- `running + healthy`：`PASS`；
- `running + starting`：等待逻辑耗尽后 `FAIL`；
- `running + unhealthy`：`FAIL`；
- `exited`、`created`、`restarting` 或服务不存在：`FAIL`；
- 没有 healthcheck：核心服务 `FAIL`，optional 服务明确 `SKIP`。

`/api/health/` 必须返回 HTTP 200，JSON 中 `status=ok`，且数据库和 Redis 状态均为 `ok`。`/api/system/ready/` 必须返回 HTTP 200，并确认迁移、数据库、Redis 和必要依赖 ready。不得仅以 JSON 可解析或容器处于 running 判定成功。

RAGFlow 未启用时输出 `SKIP: RAGFlow optional service disabled`；启用时必须检查 `ragflow-mysql`、`ragflow` 的容器健康、HTTP 可达性以及 backend 到 RAGFlow 的连接。

### HTTP、认证与协议

所有请求使用响应体和 HTTP 状态码分离的接口。检查项包括：

- `/api/health/` 和 `/api/system/ready/`：严格检查状态码与响应字段；
- `/api/system/version/`：必须认证后访问，且 `version/channel` 与 `BUILD-MANIFEST.json` 一致；
- 登录接口：验证合法凭据取得 token，失败响应不得被当作成功；
- 受保护接口：验证合法 token 成功、匿名访问被拒绝；
- 无权限用户访问受限资源：必须得到预期拒绝结果；
- CORS：验证合法 Origin 的 OPTIONS preflight 返回 allow-origin、allow-methods、allow-headers 和 credentials；非法 Origin 不得获得允许的跨域头；
- 前端反向代理：只接受预期 2xx，401、404、500、502、503 等均失败。

### 测试数据和清理

每次运行只使用当前 `SMOKE_RUN_ID` 命名或标记的资源：

- guest 用户或测试账号关联的数据；
- 上传记录和 media 文件；
- memo 记录；
- media marker；
- PostgreSQL smoke schema/table；
- shadow database；
- 本次生成的备份文件；
- `/tmp/omnidesk-smoke-${SMOKE_RUN_ID}-*` 临时文件。

认证 helper 在一次运行内缓存 token，优先使用 `SMOKE_TEST_USER`/`SMOKE_TEST_PASSWORD`，只有配置缺失时才调用 guest-login 一次并记录用户 ID。cleanup 只能删除精确的当前 run 资源；cleanup 失败必须进入结果汇总并报告残留路径或记录，不能静默忽略。

## 离线包闭环

### 固定包布局

离线包应包含：

- `scripts/deploy.sh`
- `scripts/smoke_common.sh`
- `scripts/deploy_tests.sh`
- `scripts/smoke_tests.sh`
- `scripts/validate_artifacts.sh`
- `compose/docker-compose.offline.yml`
- `compose/.env.production.example`
- `images/*.tar`
- `BUILD-MANIFEST.json`
- `CHECKSUMS.sha256`

不得将真实 `.env.production`、密钥、证书或其他凭据复制进包。

### 统一入口

生成的 `scripts/deploy.sh` 提供三个子命令：

- `verify`：检查布局、manifest、checksum、required image tar 和镜像标识，不启动容器；
- `deploy-test [base_url]`：先执行 `verify`，加载镜像，使用 `pull_policy: never` 启动隔离 Compose project，然后运行 bundled `deploy_tests.sh`；
- `smoke [base_url]`：要求服务已经启动，使用统一上下文运行 bundled `smoke_tests.sh`，并原样传播退出码。

执行约束：

1. 缺少核心镜像、manifest、checksum、compose 或 env 文件时立即失败；
2. 任一 `docker load` 失败立即失败，并输出镜像名和错误诊断；
3. `wait_for_healthy` 超时立即失败，不得使用 `|| true` 吞错；
4. bundle 模式所有脚本从自身位置解析路径，不依赖当前工作目录；
5. `BASE_URL` 从 `FRONTEND_HOST_PORT` 推导，显式参数优先，非 80 端口不得丢失；
6. 加载镜像后禁止网络拉取，确保验证 air-gapped 场景；
7. cleanup 使用 `trap`，但不得覆盖 deploy-test 或 smoke 原始退出码；
8. RAGFlow 按 manifest 的 enabled 状态处理：启用时镜像和服务必须检查，禁用时明确输出 optional SKIP。

`verify` 通过只代表包结构完整；只有 `deploy-test` 和 `smoke` 成功，才代表包具备可部署性。

## 升级与回滚恢复

升级和回滚必须验证真实 Docker 行为，而不是只验证状态文件、源码调用或日志文本。

### 升级流程

1. 校验源版本、目标版本、manifest、镜像和备份批次；
2. 创建并验证数据库和 media 备份；
3. 记录源镜像 tag、目标镜像 tag、Compose project、volume 和 upgrade ID；
4. 启动目标版本并执行生产 entrypoint 的迁移、静态文件收集和 readiness 检查；
5. 目标版本完整 smoke 通过后，才进入 `COMMITTED`；
6. 任一步骤失败，停止目标服务，恢复源镜像，必要时恢复数据库和 media，重新启动源版本；
7. 验证源版本 health、readiness、版本接口及数据恢复结果；
8. 只有恢复成功才进入 `RECOVERY_COMMITTED`，否则进入 `SAFE_STOPPED` 并返回非零。

`SRC_IMG_TAG` 必须从当前运行 manifest 或明确记录的源上下文获取，`TGT_IMG_TAG` 必须从目标离线包 manifest 获取，禁止继续从同一个环境变量推导两者。备份失败时不得提供无保护的交互式继续路径。

### 故障注入

升级集成测试至少覆盖：迁移失败、目标 health 失败、备份失败、进程中断、media 恢复失败。每个场景都要断言目标服务停止、源镜像重新启用、数据库/media 恢复调用及结果、恢复后 health，以及正确的终态和退出码。

## 前端浏览器部署验收

前端现有 Jest、lint 和 build 继续保留，用于组件和构建验证；新增受控的 Playwright 浏览器测试入口，用于真实 Nginx 部署验收。浏览器测试不替代 Jest，静态资源检查也不冒充浏览器覆盖。

关键流程：

- 未登录访问受保护路由重定向到登录页；
- 合法登录进入首页，刷新后认证状态正确保持；
- access token 过期时 refresh 成功恢复请求；
- refresh 失败时回到登录页；
- 普通用户访问无权限路由显示预期 unauthorized 页面；
- 访问生成路由清单中的关键 lazy route；
- lazy JS、CSS、字体和 manifest 请求成功；
- 通过真实 Nginx 入口验证，不直接以 Vite dev server 作为部署结论。

测试入口使用固定 lockfile 管理 Playwright 依赖，提供独立的 `test:e2e` 命令。浏览器不可用时必须明确报告“未执行浏览器覆盖”，不能将该情况标记为通过。截图、trace 和视频统一写入 `test-artifacts/screenshots/`，成功运行后清理。

## CI 门禁

CI 分成独立且可诊断的步骤：

1. shell helper、部署脚本和升级状态机单测；
2. frontend Jest、lint、build；
3. backend pytest、coverage 和 deployment check；
4. 使用隔离 Compose project 的生产/离线拓扑 deploy-test；
5. 真实离线包 `verify`、镜像 tar load、`deploy-test` 和完整 `smoke`；
6. 真实升级/回滚故障注入；
7. 真实 Nginx 入口的浏览器 E2E。

必需步骤不得使用 `continue-on-error: true`，不得以 `SMOKE_STRICT=0` 作为部署验收门禁。开发 Compose 的快速连通性测试可以保留，但必须明确标注为非离线部署验收，不能替代 offline compose 闭环。

部署验证 workflow 必须由普通 PR/目标分支门禁可达，而不是仅依赖 `workflow_run` 的发布后触发；镜像 tag、`VERSION`、当前 commit、`BUILD-MANIFEST.json` 和 Compose env 的身份必须在构建和验证阶段一致。镜像加载测试使用 `pull_policy: never`，并在网络不可用时仍能完成。

## 文件与接口变更摘要

新增：

- `deployment/docker/smoke_common.sh`
- `deployment/docker/tests/test_smoke_common.sh`
- `deployment/docker/tests/test_smoke_health.sh`
- `deployment/docker/tests/test_smoke_cleanup.sh`
- `deployment/docker/tests/test_smoke_protocols.sh`
- `deployment/docker/tests/test_offline_bundle_test_entrypoints.sh`
- 前端 Playwright 配置和 E2E 测试目录

修改：

- `deployment/docker/smoke_tests.sh`
- `deployment/docker/deploy_tests.sh`
- `deployment/docker/validate_artifacts.sh`
- `deployment/docker/package_offline_bundle.sh`
- `deployment/docker/upgrade.sh`
- `deployment/docker/rollback.sh`
- `deployment/docker/tests/test_upgrade_integration.sh`
- `deployment/docker/tests/test_upgrade_failure_recovery.sh`
- `.github/workflows/ci.yml` 及部署验证 workflow
- `omni_desk_frontend/package.json` 和 lockfile

仅在 API-only cleanup 无法精确删除 smoke 资源时，才新增 `cleanup_smoke_data` management command 及对应 backend 测试；不预先扩展业务模型或 API。

## 验收标准

1. 在源码目录执行 `./smoke_tests.sh <base_url>` 不需要复制文件或手工创建路径；
2. 在离线包根目录执行 `./scripts/deploy.sh verify`、`deploy-test`、`smoke` 均能找到正确 compose/env/images；
3. 人为制造一个 unhealthy 核心容器时，最终退出码非零并输出 `FAIL`；
4. backend health 返回 503 JSON 时，测试判定 `FAIL`；
5. version endpoint 的 version/channel 与 `BUILD-MANIFEST.json` 不一致时判定 `FAIL`；
6. 完整 run 不留下当前 run 的 guest 用户、上传记录、media 文件、shadow DB 或备份文件；
7. 同一 Compose project 并发执行第二个 destructive smoke 时被锁拒绝，不同 project name 可以并行；
8. 缺少核心镜像、manifest、checksum 或 docker load 失败时，离线入口返回非零；
9. 真实升级故障注入能区分 `RECOVERY_COMMITTED` 与 `SAFE_STOPPED`，并验证源版本恢复后的 health；
10. 前端关键登录、权限、token refresh 和 lazy route 流程通过真实 Nginx 入口的浏览器测试；
11. shell 单测、离线包布局测试、部署测试、backend/frontend 测试和必要 E2E 全部通过；
12. CI 中任一 required 部署验证失败都会阻断 job，且成功结果不会依赖网络或 `continue-on-error`。

## 风险与控制

- 所有 destructive smoke 使用独立 Compose project 和独立 volume，不在现有生产卷上运行；
- cleanup 失败进入最终结果并输出明确残留资源；
- 备份测试使用隔离输出目录，不调用生产保留策略清理；
- 真实凭据只通过环境变量注入，不写入仓库、镜像层或离线包；
- 每个实现阶段先运行局部失败测试，再实现最小修复；
- 浏览器、Docker 或可选服务不可用时，报告实际未覆盖范围，不将缺失环境转换成通过；
- 失败诊断产物统一放入 `test-artifacts/`，成功后删除临时截图、trace、日志和 bundle。
