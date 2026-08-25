# 离线部署冒烟测试可靠性实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or **superpowers:executing-plans** to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 OmniDesk 源码目录和离线部署包中的部署测试、冒烟测试、升级恢复测试和浏览器验收具备统一路径、健康、HTTP、资源隔离和失败传播契约。

**Architecture:** 保留现有 Bash 测试框架，新增 `smoke_common.sh` 作为上下文、Compose、锁、结果和 HTTP 辅助层。源码模式和离线包模式都通过同一组入口运行；离线包使用 `verify`、`deploy-test`、`smoke` 完成真实 tar 加载和隔离 Compose 验证；升级恢复和前端浏览器 E2E 作为独立集成门禁接入 CI。

**Tech Stack:** Bash 5、Docker Compose v2、PostgreSQL、Redis、Celery、Django 4.2、Python 3.10、React 18.3、Vite、Jest、Playwright、GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-08-23-offline-smoke-reliability-design.md`

## Global Constraints

- 所有测试脚本必须支持源码目录和离线包目录，不依赖当前 shell 工作目录。
- 默认 `SMOKE_STRICT=1`，未授权 `SKIP` 和 `WARN` 必须使最终测试失败。
- 默认 `SMOKE_ALLOW_NETWORK_SKIP=0`，网络瞬态只有显式设置为 `1` 才能降级为 `SKIP`。
- 默认 `SMOKE_ALLOW_RATE_LIMIT_SKIP=0`，HTTP 429 只有显式设置为 `1` 才能降级为 `WARN`。
- 测试资源必须使用 `SMOKE_RUN_ID=<UTC 秒>-<PID>` 隔离，并由 cleanup trap 回收。
- 同一 `COMPOSE_PROJECT_NAME` 的 destructive smoke 必须通过 `flock` 互斥，锁冲突返回退出码 `2`。
- 核心服务缺失、非 running、starting 超时或 unhealthy 必须 `FAIL`；只有明确 optional 服务可以 `SKIP`。
- HTTP 2xx 且满足接口字段约定才算 `PASS`；业务 4xx/5xx、未知状态码、空响应和网络错误默认 `FAIL`。
- `verify` 通过只代表离线包结构完整，不代表服务已部署可用。
- 离线验证必须使用 `pull_policy: never`，不得依靠网络拉取镜像或外部资源。
- 不改变生产 API、认证、CORS、限流和 RAGFlow 业务语义。
- 不把真实 `.env.production`、密钥、证书或凭据复制到仓库、镜像层或离线包。
- 每个任务先写失败测试或可重复 shell 复现，再实现最小修复，再运行局部验证。
- Python 命令必须使用 `/home/fz/anaconda3/envs/OmniDesk/bin/python`，禁止污染 base 或系统 Python。
- destructive smoke、升级恢复和备份测试只允许在独立 Compose project、独立 volume 和隔离输出目录执行。
- 成功运行产生的截图、trace、临时日志和临时 bundle 必须清理；失败诊断才可保留在 `test-artifacts/`。

## 文件职责地图

### 共享部署测试层

- Create: `deployment/docker/smoke_common.sh`：解析脚本/bundle 上下文，提供 Compose 调用、锁、临时文件、结果计数、健康和 HTTP 判定。
- Create: `deployment/docker/tests/test_smoke_common.sh`：验证源码与 bundle 路径、env 解析、run id、临时文件和锁行为。
- Create: `deployment/docker/tests/test_smoke_health.sh`：使用 stub docker/curl 验证 unhealthy、状态码和严格模式。
- Modify: `deployment/docker/smoke_tests.sh`：接入共享 helper，收紧服务、HTTP、认证、业务探针、cleanup 和并发行为。
- Modify: `deployment/docker/deploy_tests.sh`：接入共享 helper，检查容器 health 和协议状态。
- Modify: `deployment/docker/validate_artifacts.sh`：支持显式 bundle/source artifact 参数并使用统一结果码。

### 协议与资源隔离层

- Create: `deployment/docker/tests/test_smoke_cleanup.sh`：验证 token cache、run-id 资源和 cleanup 仅删除当前 run。
- Create: `deployment/docker/tests/test_smoke_protocols.sh`：验证 version、CORS、RAGFlow optional 和 lazy resource 判定。
- Create: `omni_desk_backend/core/management/commands/cleanup_smoke_data.py`：仅当 Task 3 的 API-only cleanup 失败测试证明无法精确删除资源时创建，命令按 run id 清理数据库和 media。
- Create: `omni_desk_backend/core/tests/test_cleanup_smoke_data.py`：仅与上述管理命令同时创建，验证不删除非 smoke 数据。

### 离线包和部署入口

- Create: `deployment/docker/tests/test_offline_bundle_test_entrypoints.sh`：验证生成 bundle 的三个子命令和失败传播。
- Modify: `deployment/docker/package_offline_bundle.sh`：复制共享 helper、部署测试、完整 smoke、artifact validator 和生成入口。
- Modify: `deployment/docker/validate_artifacts.sh`：校验 manifest、checksum、required image tar 和 bundle/source 双模式。
- Modify generated template in `deployment/docker/package_offline_bundle.sh`：生成 `scripts/deploy.sh verify|deploy-test|smoke`。
- Modify: `deployment/docker/tests/test_offline_bundle_layout.sh`：移除仅目录存在的弱断言，增加真实入口和失败场景。
- Modify: `deployment/docker/tests/test_deploy_image_tags.sh`：从脚本自身位置解析 package 脚本，消除 cwd 依赖。

### 升级恢复和前端验收

- Modify: `deployment/docker/upgrade.sh`：真实切换目标/源镜像、执行恢复动作并严格推进终态。
- Modify: `deployment/docker/rollback.sh`：恢复失败时进入 `SAFE_STOPPED`，健康检查失败返回非零。
- Modify: `deployment/docker/tests/test_upgrade_integration.sh`：增加 stub compose 对恢复动作的行为断言。
- Modify: `deployment/docker/tests/test_upgrade_failure_recovery.sh`：增加终态、源镜像、服务停止和 restore 断言。
- Modify: `omni_desk_frontend/package.json`、`package-lock.json`：增加 Playwright 依赖和 `test:e2e`。
- Create: `omni_desk_frontend/playwright.config.js`：固定 base URL、输出目录、重试和报告。
- Create: `omni_desk_frontend/e2e/auth-and-routes.spec.js`：登录、权限、token refresh、lazy route 和静态资源流程。

### CI 和文档

- Modify: `.github/workflows/ci.yml`：保留开发拓扑快速测试，新增或调用严格部署验证 job。
- Modify: `.github/workflows/deploy-test.yml`：让 PR/目标分支可达，执行离线包闭环和 E2E。
- Create: `deployment/docker/tests/test_ci_deployment_gate.sh`：检查 required workflow 不含 fail-open 配置。
- Modify: `docs/technical/README.md` and `docs/technical/23-offline-deployment.md`: record entrypoints, result semantics and environment variables。
- Modify: `deployment/docker/README.md`：记录源码模式和 bundle 模式命令。
- Modify: `docs/superpowers/specs/2026-08-23-offline-smoke-reliability-design.md`：实现结束后标记验收项，不在中途改变设计边界。

---

### Task 1: 建立共享测试上下文和路径契约

**Files:**
- Create: `deployment/docker/smoke_common.sh`
- Create: `deployment/docker/tests/test_smoke_common.sh`
- Modify: `deployment/docker/smoke_tests.sh:1-35,302-325`
- Modify: `deployment/docker/deploy_tests.sh:1-35`
- Modify: `deployment/docker/validate_artifacts.sh:1-20,70-105`

**Interfaces:**
- Produces `init_smoke_context [base_url]`, `compose <args...>`, `resolve_artifact_dir [dir]`, `smoke_temp_file <name>`, `acquire_smoke_lock`, `release_smoke_lock`, `result <PASS|FAIL|WARN|SKIP> <message>` and `finalize_results`。
- `result` 初始化并更新 `PASS`、`FAIL`、`WARN`、`SKIP` counters；`finalize_results` 在 `SMOKE_STRICT=1` 时对非授权 `WARN`/`SKIP` 返回非零，并检查所有 required checks 已执行。
- `init_smoke_context` exports `SCRIPT_DIR`, `BUNDLE_DIR`, `COMPOSE_DIR`, `COMPOSE_FILE_PATH`, `ENV_FILE_PATH`, `COMPOSE_PROJECT_NAME`, `BASE_URL` and `SMOKE_RUN_ID`。
- `compose` always invokes `docker compose -p "$COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE_PATH" --env-file "$ENV_FILE_PATH" "$@"`。
- `validate_artifacts.sh` accepts `--image-dir <dir>`, `--manifest <file>` and `--checksums <file>`；omitted values resolve from source or bundle layout。

- [ ] **Step 1: Write the failing path and lock tests.**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/deployment/docker/smoke_common.sh"

fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT
mkdir -p "$fixture/scripts" "$fixture/compose"
touch "$fixture/compose/docker-compose.offline.yml"
printf 'COMPOSE_PROJECT_NAME=fixture\n' > "$fixture/compose/.env.production"

SMOKE_SCRIPT_DIR="$fixture/scripts" init_smoke_context http://localhost:8088
[ "$COMPOSE_FILE_PATH" = "$fixture/compose/docker-compose.offline.yml" ]
[ "$ENV_FILE_PATH" = "$fixture/compose/.env.production" ]
[ "$BASE_URL" = "http://localhost:8088" ]
case "$SMOKE_RUN_ID" in *-*) ;; *) exit 1 ;; esac
case "$(smoke_temp_file marker)" in /tmp/omnidesk-smoke-*-marker) ;; *) exit 1 ;; esac
```

先删除 compose 文件再运行同一测试，断言 `init_smoke_context` 返回非零；这样第一轮可以在 helper 尚不存在时可靠失败，第二轮覆盖文件存在与路径解析。

- [ ] **Step 2: Run the test to verify the helper is absent or incomplete.**

```bash
bash deployment/docker/tests/test_smoke_common.sh
```

Expected before implementation: `FAIL` because `smoke_common.sh` or `init_smoke_context` does not exist, or because the current scripts cannot resolve the bundle layout.

- [ ] **Step 3: Implement the minimal helper.**

Use script-relative resolution and explicit overrides：

```bash
init_smoke_context() {
    BASE_URL="${1:-${SMOKE_BASE_URL:-http://localhost}}"
    SCRIPT_DIR="${SMOKE_SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)}"
    BUNDLE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    if [ -f "$SCRIPT_DIR/docker-compose.offline.yml" ]; then
        COMPOSE_DIR="$SCRIPT_DIR"
    else
        COMPOSE_DIR="$BUNDLE_DIR/compose"
    fi
    COMPOSE_FILE_PATH="${SMOKE_COMPOSE_FILE:-$COMPOSE_DIR/docker-compose.offline.yml}"
    ENV_FILE_PATH="${SMOKE_ENV_FILE:-$COMPOSE_DIR/.env.production}"
    [ -f "$COMPOSE_FILE_PATH" ] || { printf 'ERROR: compose file not found: %s\n' "$COMPOSE_FILE_PATH" >&2; return 1; }
    [ -f "$ENV_FILE_PATH" ] || { printf 'ERROR: env file not found: %s\n' "$ENV_FILE_PATH" >&2; return 1; }
    COMPOSE_PROJECT_NAME="${SMOKE_PROJECT_NAME:-$(awk -F= '$1 == "COMPOSE_PROJECT_NAME" {print substr($0, index($0, "=") + 1); exit}' "$ENV_FILE_PATH") }"
    COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME% }"
    COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-omnidesk}"
    SMOKE_RUN_ID="${SMOKE_RUN_ID:-$(date -u +%s)-$$}"
    export BASE_URL SCRIPT_DIR BUNDLE_DIR COMPOSE_DIR COMPOSE_FILE_PATH ENV_FILE_PATH COMPOSE_PROJECT_NAME SMOKE_RUN_ID
}

compose() {
    docker compose -p "$COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE_PATH" --env-file "$ENV_FILE_PATH" "$@"
}

smoke_temp_file() {
    printf '/tmp/omnidesk-smoke-%s-%s' "$SMOKE_RUN_ID" "$1"
}
```

实现不得执行 env 文件，避免将任意 env 内容当作 shell 代码。

- [ ] **Step 4: Add lock and artifact-resolution helpers.**

`acquire_smoke_lock` 在 `${SMOKE_LOCK_DIR:-/tmp/omnidesk-smoke-locks}` 创建 project-specific lock file，使用 `flock -n`；冲突打印 `SKIP: smoke lock is held for <project>` 并返回 `2`。`release_smoke_lock` 关闭当前 FD 并只删除当前进程创建的 lock file。`resolve_artifact_dir` 优先显式参数，其次 bundle `images/`，最后 source `exported_images/`；都不存在时返回非零。

- [ ] **Step 5: Adapt the three consumers to source the helper from their own location.**

每个脚本先解析自身目录，再 source `smoke_common.sh`、调用 `init_smoke_context`，将直接 `docker compose` 调用替换为 `compose`。删除会静默跳过完整测试的 cwd-dependent `scripts/` 和 `..` fallback。

- [ ] **Step 6: Run focused and existing shell tests.**

```bash
bash deployment/docker/tests/test_smoke_common.sh
cd deployment/docker
for f in tests/test_*.sh; do bash "$f"; done
```

Expected: helper test 与现有部署 shell tests 全部通过；从 repository root 或 `deployment/docker` 启动都不改变结果。

- [ ] **Step 7: Commit.**

```bash
git add deployment/docker/smoke_common.sh deployment/docker/tests/test_smoke_common.sh deployment/docker/smoke_tests.sh deployment/docker/deploy_tests.sh deployment/docker/validate_artifacts.sh
git commit -m "fix: unify deployment test context paths"
```

---

### Task 2: Make service health and HTTP failures fail closed

**Files:**
- Create: `deployment/docker/tests/test_smoke_health.sh`
- Modify: `deployment/docker/smoke_common.sh`
- Modify: `deployment/docker/smoke_tests.sh:120-208,327-461`
- Modify: `deployment/docker/deploy_tests.sh:44-125`

**Interfaces:**
- Produces `check_service_health <service> [required|optional]`, `request_with_status <method> <url> <body_file> [curl args...]`, `classify_http_status <code> <label>`。
- `check_service_health` 更新共享 `FAIL`/`SKIP`/`PASS` counters，并在 required 失败时返回非零。
- `request_with_status` 接受 `request_with_status <method> <url> <body_file> [curl args...]`，使用 `curl --output "$body_file" --write-out '%{http_code}'`，stdout 只输出 numeric status；调用方必须单独验证 body fields。
- `classify_http_status` 对 `000`、2xx、4xx、5xx 和未知 status 使用全局 skip overrides。

- [ ] **Step 1: Write failing unhealthy and HTTP tests.**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/deployment/docker/smoke_common.sh"

FAIL=0
PASS=0
WARN=0
SKIP=0
check_service_health_from_values backend running unhealthy required
[ "$FAIL" -eq 1 ]

SMOKE_ALLOW_NETWORK_SKIP=0
if classify_http_status 503 health >/dev/null 2>&1; then
    exit 1
fi
[ "$FAIL" -eq 2 ]
```

使用 stub `docker` 和 stub `curl` 验证 `running + unhealthy` 不会被当作 all-running，JSON 503 不会被当作 PASS。

- [ ] **Step 2: Run the focused test to observe the current false pass.**

```bash
bash deployment/docker/tests/test_smoke_health.sh
```

Expected before implementation: `FAIL`，因为 helper 未定义，或现有分支对 `running + unhealthy` 保持 `FAIL=0`。

- [ ] **Step 3: Implement pure status classification first.**

实现纯函数：

```bash
check_service_health_from_values() {
    local service="$1" state="$2" health="$3" requirement="${4:-required}"
    if [ "$state" = "running" ] && [ "$health" = "healthy" ]; then
        result PASS "$service healthy"
        return 0
    fi
    if [ "$requirement" = "optional" ] && [ "$state" = "absent" ]; then
        result SKIP "$service optional service disabled"
        return 0
    fi
    result FAIL "$service state=$state health=$health"
    return 1
}
```

调用方只使用大写 `STATE`、`HEALTH`，不得再引用未定义的小写变量。

- [ ] **Step 4: Implement `request_with_status` and strict status classification.**

函数必须把 curl 网络错误映射为 `000`，把 response body 写入给定文件，并单独返回 curl exit status。`classify_http_status` 只对 2xx 调用 `result PASS`；4xx、5xx 和 unknown 调用 `result FAIL`；429 仅在 `SMOKE_ALLOW_RATE_LIMIT_SKIP=1` 时 `WARN`；000 仅在 `SMOKE_ALLOW_NETWORK_SKIP=1` 时 `SKIP`。

- [ ] **Step 5: Replace health and reverse-proxy checks in both scripts.**

`smoke_tests.sh` 和 `deploy_tests.sh` 分离容器状态/health 与 HTTP status 检查。`/api/health/` 要求 HTTP 200、`status=ok`、`database=ok`、`redis=ok`；`/api/system/ready/` 要求 HTTP 200 和所有 required readiness fields。反向代理拒绝 401、404、500、502、503。

- [ ] **Step 6: Run focused tests and all shell tests.**

```bash
bash deployment/docker/tests/test_smoke_health.sh
cd deployment/docker
for f in tests/test_*.sh; do bash "$f"; done
```

Expected: status tests 通过；`bash -n` 通过；没有 `running + unhealthy` 分支输出 PASS。

- [ ] **Step 7: Run the scoped backend regression test.**

```bash
cd omni_desk_backend
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest smart_assistant/tests/ -q --no-cov
```

Expected: PASS；不能通过弱化 smoke contract 修复后端测试。

- [ ] **Step 8: Commit.**

```bash
git add deployment/docker/smoke_common.sh deployment/docker/tests/test_smoke_health.sh deployment/docker/smoke_tests.sh deployment/docker/deploy_tests.sh
git commit -m "fix: make smoke health failures block deployment"
```

---

### Task 3: Isolate authentication, test data, cleanup and concurrency

**Files:**
- Create: `deployment/docker/tests/test_smoke_cleanup.sh`
- Modify: `deployment/docker/smoke_common.sh`
- Modify: `deployment/docker/smoke_tests.sh:80-245,748-960,989-1025`
- Create only after API-only cleanup failure is demonstrated: `omni_desk_backend/core/management/commands/cleanup_smoke_data.py`
- Create with the management command: `omni_desk_backend/core/tests/test_cleanup_smoke_data.py`

**Interfaces:**
- Produces `obtain_auth_token`, `cleanup_smoke_artifacts`, `record_smoke_resource`, `acquire_smoke_lock` and `release_smoke_lock`。
- `obtain_auth_token` 在当前 shell 设置并缓存 `SMOKE_AUTH_TOKEN`，同一运行只发起一次登录请求，并在 fallback 时记录 guest user id。
- 每个写入操作使用含 `SMOKE_RUN_ID` 的 marker。
- `cleanup_smoke_artifacts` 只删除 current-run resources，任一期望 cleanup action 失败则返回非零。

- [ ] **Step 1: Write tests for one token request and run-scoped resources.**

创建 stub HTTP/filesystem commands。测试调用 `obtain_auth_token` 两次并断言 login stub count 为 `1`；创建 `run-a` 与 `run-b` marker，清理 `run-a` 后断言 `run-b` 仍存在。

```bash
TOKEN_CALLS_FILE="$(mktemp)"
TOKEN_OUTPUT_DIR="$(mktemp -d)"
SMOKE_RUN_ID=run-a
SMOKE_AUTH_TOKEN=""
obtain_auth_token >"$TOKEN_OUTPUT_DIR/token-a"
obtain_auth_token >"$TOKEN_OUTPUT_DIR/token-b"
cmp "$TOKEN_OUTPUT_DIR/token-a" "$TOKEN_OUTPUT_DIR/token-b"
[ "$(wc -l < "$TOKEN_CALLS_FILE")" -eq 1 ]
rm -rf "$TOKEN_OUTPUT_DIR" "$TOKEN_CALLS_FILE"
```

- [ ] **Step 2: Run the test to confirm the current repeated-login/fixed-marker failure.**

```bash
bash deployment/docker/tests/test_smoke_cleanup.sh
```

Expected: `FAIL`，因为当前 smoke path 可能多次 guest-login，且使用固定 marker 或 temp path。

- [ ] **Step 3: Implement token cache and resource recording.**

使用 shell variables 缓存 token/user id。优先 `SMOKE_TEST_USER`/`SMOKE_TEST_PASSWORD`；缺失时 guest-login 一次。所有 generated ids/paths 写入 `smoke_temp_file resources` 返回的 run-specific 文件，每行固定为 `kind<TAB>id<TAB>path`。不得将资源值作为 shell source 执行。

- [ ] **Step 4: Add run-id markers to upload, memo, volume, schema, shadow database and backup operations.**

固定 marker 改为 `smoke_${SMOKE_RUN_ID}`。backup 使用隔离目录 `${SMOKE_BACKUP_DIR:-$(dirname "$(smoke_temp_file backup)")}`，并在 restore 前记录路径。cleanup 禁止不带 run id 的 broad wildcard。

- [ ] **Step 5: Implement cleanup trap preserving the original result.**

```bash
trap '
    test_exit=$?
    cleanup_exit=0
    cleanup_smoke_artifacts || cleanup_exit=$?
    if [ "$cleanup_exit" -ne 0 ]; then
        result FAIL "smoke cleanup failed"
        [ "$test_exit" -eq 0 ] && test_exit="$cleanup_exit"
    fi
    exit "$test_exit"
' EXIT
```

若 cleanup 失败而测试原本成功，最终退出非零；若测试已失败，保留原始失败并打印 cleanup failures。

- [ ] **Step 6: Add the management command only after API-only cleanup fails.**

命令必须要求 `--run-id`，只接受安全 run-id 格式，按精确 `smoke_<run-id>` marker 删除记录和 media，并拒绝缺失/非法参数。不得接受 raw table、arbitrary path 或 SQL fragment。Backend tests 覆盖删除 current-run、保留 different-run、拒绝 invalid run id。

```bash
cd omni_desk_backend
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest core/tests/test_cleanup_smoke_data.py -q --no-cov
```

- [ ] **Step 7: Test same-project and different-project locking.**

两个 background shell 使用相同 `SMOKE_PROJECT_NAME`：第二个必须退出 `2`。不同 project name 的两个进程都必须获取锁并退出 `0`。锁目录使用临时路径并由 trap 删除。

- [ ] **Step 8: Run focused cleanup and shell tests.**

```bash
bash deployment/docker/tests/test_smoke_cleanup.sh
cd deployment/docker
for f in tests/test_*.sh; do bash "$f"; done
```

Expected: token count 为 1；另一个 run 的资源不被清理；同 project 冲突被拒绝；没有固定 `/tmp` marker 残留。

- [ ] **Step 9: Commit.**

```bash
git add deployment/docker/smoke_common.sh deployment/docker/tests/test_smoke_cleanup.sh deployment/docker/smoke_tests.sh
if [ -f omni_desk_backend/core/management/commands/cleanup_smoke_data.py ]; then git add omni_desk_backend/core/management/commands/cleanup_smoke_data.py omni_desk_backend/core/tests/test_cleanup_smoke_data.py; fi
git commit -m "fix: isolate and clean smoke test data"
```

---

### Task 4: Strengthen authenticated protocols, optional services and dynamic assets

**Files:**
- Create: `deployment/docker/tests/test_smoke_protocols.sh`
- Modify: `deployment/docker/smoke_common.sh`
- Modify: `deployment/docker/smoke_tests.sh:435-461,963-1075`
- Modify: `deployment/docker/docker-compose.offline.yml:189-247` only if explicit optional metadata is required by the test
- Modify: `omni_desk_frontend/src/routes/lazyImports.js` only if the current route manifest cannot enumerate critical lazy routes

**Interfaces:**
- Produces `check_version_endpoint <token>`, `check_cors_preflight <origin>`, `check_optional_ragflow`, `check_lazy_routes`。
- `check_version_endpoint` validates HTTP 200 and compares `version/channel` with manifest fields。
- `check_cors_preflight` validates allow-origin, methods, headers and credentials for legal origin and rejects illegal origin。
- `check_optional_ragflow` prints disabled `SKIP` or checks both RAGFlow services and backend connectivity。
- `check_lazy_routes` validates configured critical route assets and distinguishes static-manifest coverage from browser coverage。

- [ ] **Step 1: Write failing protocol tests.**

Stub curl responses for:

```text
GET /api/system/version/ -> 200 with version mismatch
OPTIONS /api/auth/login/ -> 204 without Access-Control-Allow-Headers
RAGFlow disabled -> no containers
```

Assert version mismatch and missing CORS headers return nonzero；disabled RAGFlow prints `SKIP: RAGFlow optional service disabled` and never prints PASS。

- [ ] **Step 2: Run protocol tests before implementation.**

```bash
bash deployment/docker/tests/test_smoke_protocols.sh
```

Expected: `FAIL`，因为当前 version check 不比较 manifest identity，且 CORS/RAGFlow checks 不执行完整 contract。

- [ ] **Step 3: Implement authenticated version and manifest comparison.**

使用项目环境提供的 JSON parser 解析 `BUILD-MANIFEST.json`；字段缺失、匿名访问、version 或 channel 不一致均失败。不得用 grep 代替可用的 JSON parser。

- [ ] **Step 4: Implement legal and illegal CORS preflight checks.**

发送 `OPTIONS`，带 `Origin`、`Access-Control-Request-Method` 和 `Access-Control-Request-Headers`。合法 origin 必须返回 200/204 及完整 allow headers；synthetic illegal origin 不得被 reflection 或允许。

- [ ] **Step 5: Implement optional RAGFlow handling.**

从 resolved Compose configuration/manifest 推导 enabled state，不从失败 curl 推导。disabled 输出显式 SKIP；enabled 必须检查 `ragflow-mysql`、`ragflow` 存在且 healthy，检查 endpoint 和 backend-to-RAGFlow connectivity。

- [ ] **Step 6: Replace fixed twenty-chunk probing with manifest-driven checks.**

从 built index 或 generated asset manifest 提取每个 JS/CSS/font/manifest URL，归一化到 `BASE_URL`，逐个请求并对非 2xx 失败。无 browser runner 时标签为 `static asset coverage`，不得声称 route coverage。

- [ ] **Step 7: Run focused protocol tests and frontend build asset checks.**

```bash
bash deployment/docker/tests/test_smoke_protocols.sh
cd omni_desk_frontend
npm run build
```

Expected: protocol tests 通过，生成资源可枚举且不含 external URL。按照仓库现有规则清理生成的 build output。

- [ ] **Step 8: Commit.**

```bash
if [ -f deployment/docker/docker-compose.offline.yml ]; then
    git add deployment/docker/docker-compose.offline.yml
fi
if [ -f omni_desk_frontend/src/routes/lazyImports.js ]; then
    git add omni_desk_frontend/src/routes/lazyImports.js
fi
git commit -m "test: strengthen smoke protocol coverage"
```

第二条 `git add` 只在实际存在修改时执行；实现者不得用 `|| true` 吞掉测试或提交失败。

---

### Task 5: Make offline bundle verification and test entrypoints executable

**Files:**
- Create: `deployment/docker/tests/test_offline_bundle_test_entrypoints.sh`
- Modify: `deployment/docker/package_offline_bundle.sh:475-721`
- Modify generated `deploy.sh` template inside `deployment/docker/package_offline_bundle.sh`
- Modify: `deployment/docker/validate_artifacts.sh:1-171`
- Modify: `deployment/docker/tests/test_offline_bundle_layout.sh`
- Modify: `deployment/docker/tests/test_deploy_image_tags.sh`

**Interfaces:**
- Generated `./scripts/deploy.sh verify` validates files, manifest, checksums and required image tar files。
- Generated `./scripts/deploy.sh deploy-test [base_url]` runs bundled deploy test with resolved Compose/env paths。
- Generated `./scripts/deploy.sh smoke [base_url]` runs bundled smoke test with resolved Compose/env paths。
- `validate_artifacts.sh` uses bundle `images/` and root metadata；source mode continues using `exported_images/`。
- `deploy.sh` derives `BASE_URL` from `FRONTEND_HOST_PORT`，explicit argument takes precedence and port 80 maps to `http://localhost`。

- [ ] **Step 1: Write failing bundle entrypoint tests.**

Create a synthetic bundle with `scripts`, `compose`, `images`, manifest and checksum. Assert generated script dispatches all commands:

```bash
for command in verify deploy-test smoke; do
    grep -q "${command}" "$bundle/scripts/deploy.sh"
done
```

Stub `docker load` to fail for one tar and assert `deploy-test` returns nonzero. Stub Compose health wait to fail and assert the command returns nonzero instead of printing deployment complete.

- [ ] **Step 2: Run entrypoint tests before implementation.**

```bash
bash deployment/docker/tests/test_offline_bundle_test_entrypoints.sh
```

Expected: `FAIL`，因为当前 generated bundle 缺少可靠的 entrypoints，且 deploy.sh 对 image-load、health、smoke failure 只 WARN。

- [ ] **Step 3: Expand package script copy lists.**

复制 `smoke_common.sh`、`deploy_tests.sh`、`validate_artifacts.sh`、`smoke_tests.sh`、`test_helpers.sh`、`upgrade.sh`、`rollback.sh`、`upgrade_state.sh` 和 required verification scripts 到 `scripts/`，保留 executable mode；不复制 `.env.production` 或 credentials。

- [ ] **Step 4: Make `validate_artifacts.sh` fail closed for required metadata.**

显式 CLI args 优先。要求 `BUILD-MANIFEST.json`、`CHECKSUMS.sha256`、Compose/env 文件和每个 required image tar。checksum 必须验证 bundle root 的精确文件。缺失或 mismatch 返回非零；RAGFlow optional assets 由 manifest enabled state 决定。

- [ ] **Step 5: Implement generated `deploy.sh verify`.**

`verify` 执行 bundle validator 并原样传播 exit code；不得启动容器或修改 bundle 外的 host 文件。

- [ ] **Step 6: Implement generated `deploy.sh deploy-test`.**

按顺序：调用 `verify`；加载每个 `images/*.tar` 并在首个失败时中止；导出 `SMOKE_COMPOSE_FILE`、`SMOKE_ENV_FILE`、`SMOKE_PROJECT_NAME`、derived `BASE_URL`；使用 `pull_policy: never` 和隔离 project 启动 Compose；等待 required services healthy；运行 bundled `deploy_tests.sh`；cleanup 不覆盖测试失败码。

- [ ] **Step 7: Implement generated `deploy.sh smoke`.**

要求 bundle context，解析 `BASE_URL`，source bundled `smoke_common.sh`，获取 lock 并运行 full smoke。不隐式 load/pull image，返回 full smoke exit code。

- [ ] **Step 8: Make package test independent of caller cwd.**

`test_deploy_image_tags.sh` 从自身路径计算 `ROOT`，使用绝对路径调用 package script，并从 repository root 与 `deployment/docker` 各执行一次。

- [ ] **Step 9: Generate a temporary bundle and run all three commands.**

使用 disposable output directory 和现有 package command：

```bash
bash deployment/docker/package_offline_bundle.sh --help
bash deployment/docker/tests/test_offline_bundle_test_entrypoints.sh
```

Docker 可用时，从 generated bundle root 执行：

```bash
./scripts/deploy.sh verify
./scripts/deploy.sh deploy-test
./scripts/deploy.sh smoke
```

Expected: missing files、checksum errors、load failures、health failures 均返回非零；成功命令返回零。运行后删除 temporary bundle。

- [ ] **Step 10: Run all shell tests and commit.**

```bash
cd deployment/docker
for f in tests/test_*.sh; do bash "$f"; done
git add package_offline_bundle.sh validate_artifacts.sh tests/test_offline_bundle_test_entrypoints.sh tests/test_offline_bundle_layout.sh tests/test_deploy_image_tags.sh
git commit -m "fix: make offline bundle tests executable"
```

---

### Task 6: Implement real upgrade and rollback recovery assertions

**Files:**
- Modify: `deployment/docker/tests/test_upgrade_integration.sh`
- Modify: `deployment/docker/tests/test_upgrade_failure_recovery.sh`
- Modify: `deployment/docker/upgrade.sh:69-132,254-426`
- Modify: `deployment/docker/rollback.sh:124-298`
- Modify: `deployment/docker/upgrade_state.sh` only when a missing transition is required by the existing state contract

**Interfaces:**
- `upgrade.sh` receives source context and target bundle context，记录两份 manifest identity，并暴露可测试 recovery action functions。
- Recovery 必须 stop target services、restore source image tag、在需要时 restore database/media、start source services、verify health，然后才 `RECOVERY_COMMITTED`。
- Recovery 失败必须保留 `SAFE_STOPPED`、非零退出和 diagnostics。
- `rollback.sh` 的 restore/post-restore health 失败必须非零，不能只输出 warning。

- [ ] **Step 1: Add failing stub-compose integration tests.**

fake Compose executable 记录 command log，并按配置让 migration、target health、backup、interruption 或 media restore 失败。migration failure 必须断言：

```bash
grep -q 'stop target' "$COMMAND_LOG"
grep -q 'restore source image' "$COMMAND_LOG"
grep -q 'restore database' "$COMMAND_LOG"
grep -q 'health source' "$COMMAND_LOG"
[ "$(jq -r .state "$STATE_FILE")" = "RECOVERY_COMMITTED" ]
```

recovery health failure 必须断言 state `SAFE_STOPPED` 和 nonzero exit。

- [ ] **Step 2: Run existing and new integration tests before implementation.**

```bash
bash deployment/docker/tests/test_upgrade_integration.sh
bash deployment/docker/tests/test_upgrade_failure_recovery.sh
```

Expected: 现有测试可能只通过 state/text assertions，新行为 assertions 因未执行真实 recovery action 而失败。

- [ ] **Step 3: Separate source and target manifest/tag resolution.**

source version 从 current deployment manifest 或 recorded state 获取；target tag 从 target bundle manifest 获取。missing、malformed 或相同 identity 在 stop services 前拒绝。禁止两者都从 `BACKEND_IMAGE_TAG` 获取。

- [ ] **Step 4: Make backup failure a hard stop.**

删除 backup failure 后的 interactive continue。记录 failure、进入 safe state 并返回 nonzero。backup metadata/checksum 在 target startup 前完成验证。

- [ ] **Step 5: Implement recovery action sequence.**

failure after target activation 时依次：stop target services；restore source image references；在 migration/data changed 时 restore database；media changed 时 restore media；start source services；执行 `/api/health/`、`/api/system/ready/` 和 authenticated version checks；验证完成后写 `RECOVERY_COMMITTED`。

- [ ] **Step 6: Make rollback health and media failures blocking.**

`rollback.sh` 使用 shared status contract 或等价 strict check。required media restore 缺 backend、restore command failure 或 post-restore health failure 必须进入 `SAFE_STOPPED` 并非零，cleanup 不覆盖原始 error。

- [ ] **Step 7: Strengthen state assertions.**

只为 source/target identity、recovery outcome 所需字段更新 `test_upgrade_state.sh`。`RECOVERY_COMMITTED` 仅在 recorded health verification 后合法；`SAFE_STOPPED` 保留 upgrade id 和 failure reason。

- [ ] **Step 8: Run all upgrade tests and syntax checks.**

```bash
bash deployment/docker/tests/test_upgrade_integration.sh
bash deployment/docker/tests/test_upgrade_state.sh
bash deployment/docker/tests/test_upgrade_failure_recovery.sh
bash deployment/docker/tests/test_rollback_safety.sh
bash -n deployment/docker/upgrade.sh deployment/docker/rollback.sh deployment/docker/upgrade_state.sh
```

Expected: 每个 injected failure 都验证真实 recovery command、terminal state 和 nonzero status。

- [ ] **Step 9: Commit.**

```bash
git add deployment/docker/upgrade.sh deployment/docker/rollback.sh deployment/docker/upgrade_state.sh deployment/docker/tests/test_upgrade_integration.sh deployment/docker/tests/test_upgrade_failure_recovery.sh deployment/docker/tests/test_upgrade_state.sh deployment/docker/tests/test_rollback_safety.sh
git commit -m "fix: verify upgrade recovery actions"
```

---

### Task 7: Add browser-level frontend deployment tests

**Files:**
- Modify: `omni_desk_frontend/package.json`
- Modify: `omni_desk_frontend/package-lock.json`
- Create: `omni_desk_frontend/playwright.config.js`
- Create: `omni_desk_frontend/e2e/auth-and-routes.spec.js`
- Create: `omni_desk_frontend/e2e/helpers/api-fixtures.js`
- Modify: `.gitignore` only if Playwright output is not already excluded under `test-artifacts/`

**Interfaces:**
- Produces npm script `test:e2e` running Playwright against `E2E_BASE_URL` (default `http://localhost`)。
- Uses `E2E_USERNAME`、`E2E_PASSWORD`、`E2E_BASE_URL`、`E2E_AUTH_MODE`；no credentials committed。
- Traces/screenshots/videos only under `test-artifacts/screenshots/`。
- Browser unavailable means deployment acceptance fails；a separate diagnostic job may report unavailable browser as skipped but cannot mark acceptance passed。

- [ ] **Step 1: Add dependency and deliberately failing smoke spec.**

用 Node 20/npm 10 更新 lockfile，并加入：

```json
"test:e2e": "playwright test"
```

首次测试：

```js
test('protected route redirects anonymous users to login', async ({ page }) => {
  await page.goto('/control-panel');
  await expect(page).toHaveURL(/\/login/);
});
```

- [ ] **Step 2: Run the test before configuration.**

```bash
cd omni_desk_frontend
npm run test:e2e -- --list
```

Expected: `FAIL`，因为 Playwright config/browser dependency 尚不存在。

- [ ] **Step 3: Add Playwright configuration with fixed artifact paths.**

配置 `testDir: './e2e'`、`baseURL: process.env.E2E_BASE_URL || 'http://localhost'`、CI one worker、CI retries、`trace: 'retain-on-failure'`、failure screenshot/video，reporter output 在 `../test-artifacts/screenshots/`。不得添加 external URL/CDN dependency。

- [ ] **Step 4: Implement authentication and route fixtures.**

使用 env credentials 或 documented guest-login fixture。需要凭据的测试缺少凭据时以明确错误失败。不得把 token 写入 logs/screenshots/traces；使用真实 login/refresh flow，不 mock Axios。

- [ ] **Step 5: Add critical browser journeys.**

覆盖 anonymous protected redirect、valid login、refresh 后 session 保持、expired access token refresh、refresh failure 回 login、普通用户访问 admin route 的 unauthorized UI、critical generated lazy routes 及 JS/CSS/font/manifest request 状态。失败信息只包含 URL/status，不包含 Authorization header/token。

- [ ] **Step 6: Run browser tests against real Nginx endpoint.**

启动 isolated production/offline stack，然后执行：

```bash
cd omni_desk_frontend
E2E_BASE_URL="${E2E_BASE_URL:-http://localhost}" npm run test:e2e
```

Expected: critical journeys 通过 Nginx；不能以 Vite dev server 作为部署证据。成功后删除 `test-artifacts/screenshots/` 中 artifacts。

- [ ] **Step 7: Run existing frontend checks.**

```bash
cd omni_desk_frontend
npm test -- --watchAll=false
npm run lint
npm run build
```

Expected: Jest、lint、build 全部 green。

- [ ] **Step 8: Commit.**

```bash
git add omni_desk_frontend/package.json omni_desk_frontend/package-lock.json omni_desk_frontend/playwright.config.js omni_desk_frontend/e2e
if [ -f .gitignore ]; then
    git add .gitignore
fi
git commit -m "test: add browser deployment smoke coverage"
```

第二条 `git add` 不得用于隐藏实现或测试失败；若 `.gitignore` 无修改，直接忽略该命令的无文件结果。

---

### Task 8: Make CI execute the strict deployment contract

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/deploy-test.yml`
- Create: `deployment/docker/tests/test_ci_deployment_gate.sh`
- Modify: `deployment/docker/deploy_tests.sh` only if CI-specific arguments are required
- Modify: `deployment/docker/package_offline_bundle.sh` only if CI package metadata needs an explicit commit identity

**Interfaces:**
- Required jobs separately report shell tests、artifact verification、offline deploy-test、full smoke、upgrade recovery 和 browser E2E。
- Required deployment jobs fail on required error；不使用 `continue-on-error: true` 或 `SMOKE_STRICT=0`。
- CI-generated `VERSION`、image tags、manifest、current commit 和 Compose project identity 一致。

- [ ] **Step 1: Write workflow contract test.**

断言 required deployment sections 不含：

```text
continue-on-error: true
SMOKE_STRICT=0
pull_policy: missing
manual docker compose exec ... migrate as the only production-entrypoint check
```

允许显式命名的 advisory jobs 保留 `continue-on-error`；deployment acceptance job 不得保留。

- [ ] **Step 2: Run workflow contract test against current workflows.**

```bash
bash deployment/docker/tests/test_ci_deployment_gate.sh
```

Expected: current informational smoke 和 `pull_policy: missing` 行为被测试识别为 `FAIL`。

- [ ] **Step 3: Add required shell-test job.**

job 从 `deployment/docker` 运行：

```bash
for f in tests/test_*.sh; do bash "$f"; done
```

同时使用 absolute script paths 从 repository root 执行 path-sensitive tests。只上传失败 diagnostics。

- [ ] **Step 4: Add isolated offline package verification job.**

构建/取得 current package，运行 `verify`，load all image tar，设置 `pull_policy: never`，启动 unique Compose project，运行 `deploy-test` 与 full `smoke`。设置 `SMOKE_STRICT=1`、`SMOKE_ALLOW_NETWORK_SKIP=0` 和由 job id 生成的 `SMOKE_RUN_ID`。`if: always()` 清理 project/volumes，但不得覆盖 test result。

- [ ] **Step 5: Add required upgrade/recovery and browser E2E stages.**

upgrade job 使用 disposable source/target fixtures 运行 failure-injection tests。browser job 启动 real Nginx-backed stack 并执行 `npm run test:e2e`；凭据只来自 GitHub Actions secrets 或 job-local generated users。

- [ ] **Step 6: Make workflow identity checks explicit.**

加载 image 前比较 `VERSION`、manifest `version/channel/commit`、image labels/tags、Compose env image/project variables；任一 required identity 不一致即失败。开发 Compose quick test 保留但标为非 offline acceptance。

- [ ] **Step 7: Run static workflow assertions and shell tests locally.**

```bash
bash deployment/docker/tests/test_ci_deployment_gate.sh
cd deployment/docker
for f in tests/test_*.sh; do bash "$f"; done
```

Expected: required workflow checks 通过，required step 无 fail-open 配置。

- [ ] **Step 8: Commit.**

```bash
git add .github/workflows/ci.yml .github/workflows/deploy-test.yml deployment/docker/tests/test_ci_deployment_gate.sh
git commit -m "ci: enforce offline deployment smoke gates"
```

---

### Task 9: Run full integration validation and update deployment documentation

**Files:**
- Modify: `docs/technical/README.md`
- Modify: `docs/technical/23-offline-deployment.md`
- Modify: `deployment/docker/README.md`
- Modify: `docs/superpowers/specs/2026-08-23-offline-smoke-reliability-design.md`
- Test artifacts: `test-artifacts/` only for failure diagnostics

**Interfaces:**
- 文档必须展示 source/bundle commands、required env、result semantics、cleanup 和 `verify`/`deploy-test`/`smoke`/upgrade recovery 差异。
- spec acceptance items 只能在对应 command 实际通过后标记。

- [ ] **Step 1: Start isolated Compose and verify production entrypoint behavior.**

使用如下 shell 变量生成实际值，不在命令中使用未替换占位符：

```bash
RUN_ID="$(date -u +%s)-$$"
PROJECT="omnidesk-validation-${RUN_ID}"
SMOKE_PROJECT_NAME="$PROJECT" SMOKE_RUN_ID="$RUN_ID" docker compose -p "$PROJECT" -f deployment/docker/docker-compose.offline.yml up -d
```

不先手工执行 migration；断言 backend entrypoint 执行 migration、optional static collection、readiness 和 worker health。记录 project name，最终清理。

- [ ] **Step 2: Run source-mode deployment and smoke tests.**

```bash
RUN_ID="$(date -u +%s)-$$"
PROJECT="omnidesk-validation-${RUN_ID}"
SMOKE_PROJECT_NAME="$PROJECT" SMOKE_STRICT=1 SMOKE_ALLOW_NETWORK_SKIP=0 SMOKE_RUN_ID="$RUN_ID" ./deployment/docker/deploy_tests.sh http://localhost
SMOKE_PROJECT_NAME="$PROJECT" SMOKE_STRICT=1 SMOKE_ALLOW_NETWORK_SKIP=0 SMOKE_RUN_ID="$RUN_ID" ./deployment/docker/smoke_tests.sh http://localhost
```

Expected: required services healthy、required probes pass、cleanup 不留 current-run records/files。

- [ ] **Step 3: Generate and validate a fresh offline bundle.**

在 disposable output directory 生成 package，从 bundle root 执行：

```bash
./scripts/deploy.sh verify
./scripts/deploy.sh deploy-test
./scripts/deploy.sh smoke
```

Expected: checksum、manifest、tar load、`pull_policy: never`、health、deploy test、full smoke 全部通过且不需要 external network。

- [ ] **Step 4: Run failure-injection acceptance checks.**

在 isolated project 中分别注入 core unhealthy、backend health 503 JSON、business 4xx/5xx、missing required image tar、corrupt checksum、target migration failure、source recovery health failure；每项都必须 nonzero 并输出 diagnostic。最后一项必须是 `SAFE_STOPPED`，不能是 `RECOVERY_COMMITTED`。

- [ ] **Step 5: Run concurrency and cleanup acceptance checks.**

同 project 两个 smoke：第二个退出 `2`；不同 project 两个 smoke 均可运行。按 exact `SMOKE_RUN_ID` 检查 database/media/output，成功 cleanup 后无 current-run residue。

- [ ] **Step 6: Run repository test suites in correct environments.**

```bash
cd deployment/docker
for f in tests/test_*.sh; do bash "$f"; done
cd ../../omni_desk_backend
/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test -q
cd ../omni_desk_frontend
npm test -- --watchAll=false
npm run lint
npm run build
```

只有 isolated Nginx-backed stack 运行时才执行 `npm run test:e2e`。不使用 base/system Python。

- [ ] **Step 7: Run security and code review before completion.**

检查最终 diff 的 shell injection、arbitrary path deletion、secret leakage、unquoted variables、swallowed exit codes、unsafe SQL/path handling 和 cleanup scope。实现完成后必须调用 code-reviewer 和 security-reviewer，CRITICAL/HIGH 必须修复。

- [ ] **Step 8: Update docs and mark verified acceptance items.**

记录 defaults：

```text
SMOKE_STRICT=1
SMOKE_ALLOW_NETWORK_SKIP=0
SMOKE_ALLOW_RATE_LIMIT_SKIP=0
SMOKE_RUN_ID=<UTC 秒>-<PID>
```

说明 `verify` 为 structural、`deploy-test` 为 startup、`smoke` 为 deployed behavior、upgrade recovery 为 source restoration。只有对应测试结果实际通过，才能在 spec 中标记 `[x]`。

- [ ] **Step 9: Remove successful artifacts and verify working tree.**

删除成功 screenshots、traces、temporary bundles、test backups 和 generated logs；只保留 `test-artifacts/` 中有意保留的 failure diagnostics。确认没有 `.env.production`、token、certificate 或 credential staged。

- [ ] **Step 10: Commit documentation and final verification.**

```bash
git add docs/technical deployment/docker/README.md docs/superpowers/specs/2026-08-23-offline-smoke-reliability-design.md
git commit -m "docs: document reliable offline smoke workflow"
```

## Expected Verification Matrix

| Layer | Command | Required result |
|---|---|---|
| Shared shell helper | `bash deployment/docker/tests/test_smoke_common.sh` | PASS |
| Health and HTTP | `bash deployment/docker/tests/test_smoke_health.sh` | PASS |
| Cleanup and lock | `bash deployment/docker/tests/test_smoke_cleanup.sh` | PASS |
| Protocols | `bash deployment/docker/tests/test_smoke_protocols.sh` | PASS |
| Bundle entrypoints | `bash deployment/docker/tests/test_offline_bundle_test_entrypoints.sh` | PASS |
| Upgrade recovery | `bash deployment/docker/tests/test_upgrade_integration.sh` and `test_upgrade_failure_recovery.sh` | PASS |
| All deployment shell tests | `cd deployment/docker && for f in tests/test_*.sh; do bash "$f"; done` | PASS |
| Backend | `/home/fz/anaconda3/envs/OmniDesk/bin/python -m pytest --ds=omni_desk_backend.settings.test -q` | PASS and CI coverage gate remains satisfied |
| Frontend Jest/lint/build | `npm test`, `npm run lint`, `npm run build` | PASS |
| Browser E2E | `npm run test:e2e` against Nginx | PASS |
| Offline package | `verify`, `deploy-test`, `smoke` from bundle root | PASS without network pulls |
| Failure injection | unhealthy, 503, business error, missing tar, checksum, migration/recovery failures | all fail closed |

## Risk Controls

- Never run full destructive smoke against an existing production Compose project or volume.
- Never use `rm -rf` on a path not created by the current test run; validate run-id prefix before cleanup.
- Never pass arbitrary user-controlled values as SQL, shell source, table names or file paths.
- Never print JWTs, passwords, cookies, authorization headers or secret environment values in logs or browser artifacts.
- Never replace a failing required check with `|| true`, `continue-on-error`, a broad `SKIP`, or a text-only success heuristic.
- Never claim browser route coverage when only static asset validation ran.
- Never commit real environment files, generated credentials, backups, Docker tar files or screenshots.
