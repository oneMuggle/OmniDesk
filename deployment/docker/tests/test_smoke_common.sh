#!/usr/bin/env bash
# test_smoke_common.sh — 验证 smoke_common.sh 的路径解析、run id、临时文件、锁、artifact 解析
# 用法: bash deployment/docker/tests/test_smoke_common.sh
#
# ROOT 计算:tests → docker → deployment → <project root>,共 3 级 `..`
set -eo pipefail

# 单独关 -u:helper 函数用了 : "${VAR:=default}" 之类,但本地变量赋值更稳

PASS_COUNT=0
FAIL_COUNT=0
report() {
    case "$1" in
        PASS) PASS_COUNT=$((PASS_COUNT + 1)); printf '  \033[32mPASS\033[0m: %s\n' "$2" ;;
        FAIL) FAIL_COUNT=$((FAIL_COUNT + 1)); printf '  \033[31mFAIL\033[0m: %s\n' "$2" ;;
    esac
}

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/deployment/docker/smoke_common.sh"

# ─── T1:source 模式路径 + BASE_URL + run id + temp file ─────
fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT
mkdir -p "$fixture/scripts" "$fixture/compose"
touch "$fixture/compose/docker-compose.offline.yml"
printf 'COMPOSE_PROJECT_NAME=fixture\n' > "$fixture/compose/.env.production"

if SMOKE_SCRIPT_DIR="$fixture/scripts" init_smoke_context http://localhost:8088; then
    if [ "$COMPOSE_FILE_PATH" = "$fixture/compose/docker-compose.offline.yml" ] \
        && [ "$ENV_FILE_PATH" = "$fixture/compose/.env.production" ] \
        && [ "$BASE_URL" = "http://localhost:8088" ] \
        && [ "$COMPOSE_PROJECT_NAME" = "fixture" ]; then
        report PASS "T1 source mode resolves compose/env/project from bundle"
    else
        report FAIL "T1 source mode path mismatch: COMPOSE=$COMPOSE_FILE_PATH ENV=$ENV_FILE_PATH BASE_URL=$BASE_URL PROJ=$COMPOSE_PROJECT_NAME"
    fi
    case "$SMOKE_RUN_ID" in
        *-*) ;;
        *) report FAIL "T1 SMOKE_RUN_ID missing PID suffix: $SMOKE_RUN_ID" ;;
    esac
    case "$(smoke_temp_file marker)" in
        /tmp/omnidesk-smoke-*-marker) ;;
        *) report FAIL "T1 smoke_temp_file wrong format: $(smoke_temp_file marker)" ;;
    esac
else
    report FAIL "T1 init_smoke_context returned non-zero"
fi

# ─── T2:compose 文件缺失时 init 应失败 ─────────────────────
fixture2="$(mktemp -d)"
# 注意:不创建 docker-compose.offline.yml
rm -rf "$fixture"
if ! SMOKE_SCRIPT_DIR="$fixture2/scripts" init_smoke_context http://localhost 2>/dev/null; then
    report PASS "T2 missing compose file returns non-zero"
else
    report FAIL "T2 missing compose file did not fail"
fi
rm -rf "$fixture2"

# ─── T3:bundle 模式(SCRIPT_DIR 内无 compose,parent/compose 有) ──
fixture3="$(mktemp -d)"
trap 'rm -rf "$fixture3"' EXIT
mkdir -p "$fixture3/scripts" "$fixture3/compose"
touch "$fixture3/compose/docker-compose.offline.yml"
printf 'COMPOSE_PROJECT_NAME=bundle\n' > "$fixture3/compose/.env.production"
# 关键:SCRIPT_DIR 内没有 compose 文件,但 BUNDLE_DIR/compose 有
if SMOKE_SCRIPT_DIR="$fixture3/scripts" init_smoke_context http://localhost; then
    if [ "$COMPOSE_FILE_PATH" = "$fixture3/compose/docker-compose.offline.yml" ]; then
        report PASS "T3 bundle mode falls back to ../compose"
    else
        report FAIL "T3 bundle mode wrong compose: $COMPOSE_FILE_PATH"
    fi
else
    report FAIL "T3 bundle mode init failed unexpectedly"
fi

# ─── T4:lock 冲突返回退出码 2 ─────────────────────────────
# 用后台子进程占住 lock file,模拟另一个 smoke run 在并发执行
mkdir -p "${SMOKE_LOCK_DIR:-/tmp/omnidesk-smoke-locks}"
LOCK_PROJ="lock-test-$$-$RANDOM"
LOCK_FILE="${SMOKE_LOCK_DIR:-/tmp/omnidesk-smoke-locks}/${LOCK_PROJ}.lock"
# 子进程持锁 5 秒,等 acquire_smoke_lock 跑完再 kill
( exec 9>"$LOCK_FILE"; flock 9; sleep 5 ) &
HOLDER_PID=$!
# 给子进程一点时间拿到锁
sleep 0.3
# set -e 兼容:用 || true 吸收期望的失败退出码
COMPOSE_PROJECT_NAME="$LOCK_PROJ" acquire_smoke_lock || rc=$?
rc=${rc:-0}
# kill/wait 在子 shell 中执行,不让 set -e 终止主脚本
( kill "$HOLDER_PID" 2>/dev/null; wait "$HOLDER_PID" 2>/dev/null; rm -f "$LOCK_FILE" ) || true
if [ "$rc" -eq 2 ]; then
    report PASS "T4 lock contention returns exit code 2"
else
    report FAIL "T4 lock contention returned $rc, expected 2"
fi

# ─── T5:resolve_artifact_dir 缺失时失败 ───────────────────
# 清空 SCRIPT_DIR/BUNDLE_DIR 让 candidates 找不到
SCRIPT_DIR="/nonexistent/$$/scripts"
BUNDLE_DIR="/nonexistent/$$/bundle"
if resolve_artifact_dir "" >/dev/null 2>&1; then
    report FAIL "T5 resolve_artifact_dir should fail for nonexistent"
else
    report PASS "T5 resolve_artifact_dir fails for nonexistent"
fi

# ─── T6:部署脚本必须按 bundle 标准布局解析校验器 ───────────
# validate_artifacts.sh 位于 scripts/,从 bundle 根目录运行也不能依赖 cwd 中的同名文件。
DEPLOY_TESTS="$ROOT/deployment/docker/deploy_tests.sh"
SMOKE_TESTS="$ROOT/deployment/docker/smoke_tests.sh"
if grep -Fq 'VALIDATE_ARTIFACTS_SCRIPT="$SCRIPT_DIR/validate_artifacts.sh"' "$SMOKE_TESTS" \
    && ! grep -Fq '[ -x "./validate_artifacts.sh" ]' "$SMOKE_TESTS"; then
    report PASS "T6 smoke_tests resolves validator from SCRIPT_DIR"
else
    report FAIL "T6 smoke_tests still assumes bundle-root validate_artifacts.sh"
fi

# ─── T7:deploy_tests 受保护 version 与 Redis 必须复用上下文 ───
if grep -q 'obtain_auth_token' "$DEPLOY_TESTS" \
    && grep -q 'ENV_FILE_PATH' "$DEPLOY_TESTS" \
    && ! grep -q 'grep "\^REDIS_PASSWORD=" .env.production' "$DEPLOY_TESTS"; then
    report PASS "T7 deploy_tests reuses auth token and resolved env path"
else
    report FAIL "T7 deploy_tests does not reuse auth/env context"
fi

echo ""
echo "=========================================="
echo "  test_smoke_common.sh: PASS=$PASS_COUNT FAIL=$FAIL_COUNT"
echo "=========================================="
[ "$FAIL_COUNT" -eq 0 ]
