#!/usr/bin/env bash
# test_ci_deployment_gate.sh — Task 8 Step 1:CI workflow 部署契约测试
#
# 覆盖计划 Task 8 Step 1:
#   - deployment acceptance job 不能含 `continue-on-error: true`
#     (CI 检查 job / 显式 advisory step 允许)
#   - deployment acceptance job 不能用 `SMOKE_STRICT=0`(只允许 SMOKE_STRICT=1)
#   - 整个 workflow 内 pull_policy: missing 必须保留为 never(全局离线契约)
#     (仅显式 advisory/diagnostic 步骤允许临时降级)
#   - 不能以孤立的 `docker compose exec ... migrate` 作为唯一产线入口检查
#     (必须有 deploy_tests.sh 或 smoke_tests.sh 真实业务探针)
#
# 使用方法:
#   bash deployment/docker/tests/test_ci_deployment_gate.sh
#
# 设计:基于文本/grep 断言,无需执行 workflow;不依赖 docker / python。
#
# 规则分类:
#   - acceptance job:deploy-*, upgrade-*, offline-*, smoke-*, e2e-*, browser,
#     recovery-*, deploy-test → 应用全部严格规则
#   - CI 检查 job:lint-*, test-*, typecheck, security, build-*, check-*,
#     docker-integration → 仅应用 pull_policy: never 全局规则,允许 advisory
#     continue-on-error(开发快速测试,非 offline acceptance)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../test_helpers.sh
source "$SCRIPT_DIR/../test_helpers.sh"

# 此脚本位于 deployment/docker/tests/,向上 3 级 = repo root
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
WORKFLOWS_DIR="$REPO_ROOT/.github/workflows"

PASS_COUNT=0
FAIL_COUNT=0

# ─── 工具函数 ──────────────────────────────────────────────
check_file_exists() {
    if [ -f "$1" ]; then
        pass "file exists: $1"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        fail "file MISSING: $1"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

# 判断 job 是否为 deployment acceptance(应用全部严格规则)
# 用法:is_acceptance_job <job_name>
is_acceptance_job() {
    local name="$1"
    if echo "$name" | grep -qE "^(deploy-|deploy$|upgrade-|upgrade$|offline-|smoke-|e2e-|browser|recovery-)"; then
        return 0
    fi
    return 1
}

# 校验单个 workflow 文件
# 用法:assert_workflow_contract <file>
assert_workflow_contract() {
    local file="$1"
    echo ""
    echo "--- 检查: $file ---"

    # 解析每个顶层 job 段
    local in_job=0
    local job_name=""
    local job_has_continue=0
    local job_has_advisory_step=0
    local job_line_start=0
    local line_num=0

    # 累计 job 内 step 列表(用于判定 advisory step 命名)
    local last_step_name=""

    while IFS= read -r line; do
        line_num=$((line_num + 1))
        # 顶层 job 名(2 空格缩进 + 标识符 + :)
        if echo "$line" | grep -qE "^  [a-zA-Z_][a-zA-Z0-9_-]*:$"; then
            # 收尾上一个 job
            if [ "$in_job" -eq 1 ]; then
                _check_job_continuation "$file" "$job_name" "$job_line_start" \
                    "$job_has_continue" "$job_has_advisory_step"
            fi
            in_job=1
            job_name=$(echo "$line" | sed -E 's/^  ([a-zA-Z_][a-zA-Z0-9_-]*):.*/\1/')
            job_has_continue=0
            job_has_advisory_step=0
            job_line_start=$line_num
            last_step_name=""
            continue
        fi
        # step 名(6 空格缩进 - name:)
        if echo "$line" | grep -qE "^      - name:"; then
            last_step_name=$(echo "$line" | sed -E 's/^      - name:[[:space:]]*(.*)$/\1/')
            # 显式 advisory 命名的 step:允许该 step 后续的 continue-on-error
            if echo "$last_step_name" | grep -qiE "(advisory|informational|best-effort|non-blocking|dry-run|comment-only)"; then
                job_has_advisory_step=1
            fi
            continue
        fi
        # 检查 step 内 continue-on-error: true
        if echo "$line" | grep -qE "^[[:space:]]+continue-on-error:[[:space:]]*(true|yes|1)[[:space:]]*(#.*)?$"; then
            # step 上一行是 advisory 命名 → 允许
            local prev_step="$last_step_name"
            if echo "$prev_step" | grep -qiE "(advisory|informational|best-effort|non-blocking|dry-run|comment-only|upload)"; then
                : # step 显式 advisory/upload,允许 continue-on-error
            else
                job_has_continue=1
            fi
        fi
    done < "$file"
    # 收尾最后一个 job
    if [ "$in_job" -eq 1 ]; then
        _check_job_continuation "$file" "$job_name" "$job_line_start" \
            "$job_has_continue" "$job_has_advisory_step"
    fi

    # ── 全 workflow 级规则 ────────────────────────────────

    # 2) SMOKE_STRICT=0 只允许在非 acceptance job
    #    (CI 检查 job 的 informational smoke 可用 SMOKE_STRICT=0)
    #    acceptance job 内含 SMOKE_STRICT=0 → FAIL
    if grep -qE "SMOKE_STRICT=0" "$file"; then
        # 检查是否在 acceptance job 内 — 用 awk 切片定位
        local bad_smoke_strict=0
        local in_acc_job=0
        local cur_job=""
        local lineno=0
        while IFS= read -r l; do
            lineno=$((lineno + 1))
            if echo "$l" | grep -qE "^  [a-zA-Z_][a-zA-Z0-9_-]*:$"; then
                cur_job=$(echo "$l" | sed -E 's/^  ([a-zA-Z_][a-zA-Z0-9_-]*):.*/\1/')
                if is_acceptance_job "$cur_job"; then
                    in_acc_job=1
                else
                    in_acc_job=0
                fi
            fi
            if [ "$in_acc_job" -eq 1 ] && echo "$l" | grep -qE "SMOKE_STRICT=0"; then
                bad_smoke_strict=1
                fail "  [$file L$lineno] acceptance job '$cur_job' 含 SMOKE_STRICT=0(部署验收必须 SMOKE_STRICT=1)"
                FAIL_COUNT=$((FAIL_COUNT + 1))
            fi
        done < "$file"
        if [ "$bad_smoke_strict" -eq 0 ]; then
            pass "  [$file] SMOKE_STRICT=0 仅在 CI 检查 job(非 acceptance)"
            PASS_COUNT=$((PASS_COUNT + 1))
        fi
    else
        pass "  [$file] 无 SMOKE_STRICT=0"
        PASS_COUNT=$((PASS_COUNT + 1))
    fi

    # 部署 acceptance workflow 必须显式声明 SMOKE_STRICT=1
    if echo "$file" | grep -q "deploy-test"; then
        if grep -qE "SMOKE_STRICT=1" "$file"; then
            pass "  [$file] 含 SMOKE_STRICT=1(部署严格模式)"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            fail "  [$file] deploy-test workflow 必须设置 SMOKE_STRICT=1"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    fi

    # 3) pull_policy: missing 是全局离线契约,任何处出现都需显式 advisory 注释
    if grep -qE "pull_policy:[[:space:]]+missing" "$file"; then
        local missing_lines
        missing_lines=$(grep -nE "pull_policy:[[:space:]]+missing" "$file" | wc -l)
        local advisory_near=0
        local all_missing
        all_missing=$(grep -nE "pull_policy:[[:space:]]+missing" "$file" | cut -d: -f1)
        for ln in $all_missing; do
            local context_start=$((ln - 2))
            [ "$context_start" -lt 1 ] && context_start=1
            local context
            context=$(sed -n "${context_start},${ln}p" "$file")
            if echo "$context" | grep -qiE "(advisory|diagnostic|debug|dry-run|comment-only)"; then
                advisory_near=$((advisory_near + 1))
            fi
        done
        if [ "$missing_lines" -gt 0 ] && [ "$advisory_near" -eq 0 ]; then
            fail "  [$file] 含 pull_policy: missing(部署 acceptance 必须保留 never,全局规则)"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        else
            pass "  [$file] pull_policy: missing 仅在显式 advisory 步骤($advisory_near/$missing_lines)"
            PASS_COUNT=$((PASS_COUNT + 1))
        fi
    else
        pass "  [$file] 无 pull_policy: missing(保持 offline 契约)"
        PASS_COUNT=$((PASS_COUNT + 1))
    fi

    # 4) 不能以孤立的 docker compose exec ... migrate 作为唯一产线入口检查
    if grep -qE "docker compose exec.*migrate" "$file" && \
       ! grep -qE "(deploy_tests\.sh|smoke_tests\.sh)" "$file"; then
        fail "  [$file] 仅用 'docker compose exec ... migrate' 验证(应跑 deploy_tests.sh / smoke_tests.sh)"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    else
        pass "  [$file] deploy-tests / smoke-tests 入口检查存在(或无 exec migrate)"
        PASS_COUNT=$((PASS_COUNT + 1))
    fi
}

# 内部:在解析到 job 边界时输出该 job 的 continue-on-error 校验
_check_job_continuation() {
    local file="$1"
    local job_name="$2"
    local job_line_start="$3"
    local job_has_continue="$4"
    local job_has_advisory_step="$5"

    if [ "$job_has_continue" -ne 1 ]; then
        return
    fi
    # CI 检查 job 允许 step-level advisory continue-on-error
    if is_acceptance_job "$job_name"; then
        fail "  [$file L$job_line_start] acceptance job '$job_name' 含非 advisory continue-on-error(部署 acceptance 不允许)"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    else
        pass "  [$file L$job_line_start] CI 检查 job '$job_name' 含 advisory continue-on-error(允许)"
        PASS_COUNT=$((PASS_COUNT + 1))
    fi
}

# ─── 检查 workflow 文件存在 ──────────────────────────────
echo ""
echo "=== CI 部署契约测试 ==="
echo ""

check_file_exists "$WORKFLOWS_DIR/ci.yml"
check_file_exists "$WORKFLOWS_DIR/deploy-test.yml"

# ─── 检查 ci.yml ─────────────────────────────────────────
assert_workflow_contract "$WORKFLOWS_DIR/ci.yml"

# ─── 检查 deploy-test.yml ───────────────────────────────
assert_workflow_contract "$WORKFLOWS_DIR/deploy-test.yml"

# ─── P0:部署拓扑、前端代理和镜像身份契约 ───────────────────
DEPLOY_TESTS_SH="$REPO_ROOT/deployment/docker/deploy_tests.sh"
DEPLOY_WORKFLOW="$WORKFLOWS_DIR/deploy-test.yml"

if grep -qE 'for service in .*nginx' "$DEPLOY_TESTS_SH"; then
    fail "  [$DEPLOY_TESTS_SH] required service 不得包含不存在的 nginx service"
    FAIL_COUNT=$((FAIL_COUNT + 1))
else
    pass "  [$DEPLOY_TESTS_SH] required service 不包含独立 nginx"
    PASS_COUNT=$((PASS_COUNT + 1))
fi

if grep -q 'REACT_APP_API_BASE_URL' "$DEPLOY_TESTS_SH"; then
    fail "  [$DEPLOY_TESTS_SH] 不得依赖构建后 frontend 容器中的 REACT_APP_API_BASE_URL"
    FAIL_COUNT=$((FAIL_COUNT + 1))
else
    pass "  [$DEPLOY_TESTS_SH] 使用 HTTP 代理行为验证前端 API"
    PASS_COUNT=$((PASS_COUNT + 1))
fi

if grep -qE 'omni-desk-(backend|frontend):v0\.4\.0' "$DEPLOY_WORKFLOW"; then
    fail "  [$DEPLOY_WORKFLOW] required build 不得固定使用 v0.4.0 镜像标签"
    FAIL_COUNT=$((FAIL_COUNT + 1))
else
    pass "  [$DEPLOY_WORKFLOW] required build 不固定使用旧镜像标签"
    PASS_COUNT=$((PASS_COUNT + 1))
fi

if grep -qE '^  browser-e2e:' "$DEPLOY_WORKFLOW" || grep -qE '^    needs: deploy-test$' "$DEPLOY_WORKFLOW"; then
    fail "  [$DEPLOY_WORKFLOW] Browser E2E 不得依赖另一 Runner 的 deploy-test localhost"
    FAIL_COUNT=$((FAIL_COUNT + 1))
else
    pass "  [$DEPLOY_WORKFLOW] Browser E2E 与部署服务保持同一 job 生命周期"
    PASS_COUNT=$((PASS_COUNT + 1))
fi

if awk '
    /^  deploy-test:/ { in_deploy=1; next }
    /^  [a-zA-Z_][a-zA-Z0-9_-]*:/ && in_deploy { exit found ? 0 : 1 }
    in_deploy && /npm run test:e2e/ { found=1 }
    END { if (in_deploy && found) exit 0; if (in_deploy) exit 1; exit 1 }
' "$DEPLOY_WORKFLOW"; then
    pass "  [$DEPLOY_WORKFLOW] deploy-test job 包含 Browser E2E"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    fail "  [$DEPLOY_WORKFLOW] deploy-test job 必须执行 Browser E2E"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

# ─── 总结 ────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  CI 部署契约测试"
echo "=========================================="
echo "  PASS: $PASS_COUNT"
echo "  FAIL: $FAIL_COUNT"
echo ""

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "STATUS: FAILED — $FAIL_COUNT 项部署契约违规"
    exit 1
fi
echo "STATUS: ALL PASSED"
exit 0