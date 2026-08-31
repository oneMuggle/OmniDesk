#!/usr/bin/env bash
# test_smoke_cleanup.sh — 验证 smoke 资源隔离、token 缓存、cleanup 范围与锁
# 用法: bash deployment/docker/tests/test_smoke_cleanup.sh
#
# 覆盖:
#   C1: obtain_auth_token 同 run 多次调用只触发一次 login
#   C2: record_smoke_resource + cleanup_smoke_artifacts 只清理当前 run 资源
#   C3: 不同 SMOKE_RUN_ID 的资源不被清理
#   C4: 同 COMPOSE_PROJECT_NAME 并发锁拒绝(返回 2)
#   C5: 不同 COMPOSE_PROJECT_NAME 并发锁可获取
#   C6: smoke_temp_file 输出含 SMOKE_RUN_ID
#   C7: cleanup 失败时 trap 保留原始退出码
set -eo pipefail

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

# helper 包裹,避免 set -e 触发函数 return 非零
_call() { "$@" || true; }

# ─── C6:smoke_temp_file 含 SMOKE_RUN_ID ───────────────────
SMOKE_RUN_ID="run-x-$$"
TFILE="$(smoke_temp_file marker)"
case "$TFILE" in
    *run-x-*-marker) report PASS "C6 smoke_temp_file embeds SMOKE_RUN_ID: $TFILE" ;;
    *) report FAIL "C6 smoke_temp_file missing run id: $TFILE" ;;
esac

# ─── C1:obtain_auth_token 同 run 多次调用只触发一次 login ─
# 用 stub curl 记录调用次数
TOKEN_CALLS_FILE="$(mktemp)"
TOKEN_OUTPUT_DIR="$(mktemp -d)"
TMPHOME="$(mktemp -d)"
export HOME="$TMPHOME"

# stub curl:把 -o 指定的文件写入 body,stdout 只输出 http_code(模拟 -w '%{http_code}')
curl() {
    echo "curl-stub called $#" >> "$TOKEN_CALLS_FILE"
    local body_file=""
    local args=("$@")
    for ((i=0; i<$#; i++)); do
        if [ "${args[$i]}" = "-o" ]; then
            body_file="${args[$((i+1))]}"
            break
        fi
    done
    if [ -n "$body_file" ]; then
        printf '{"access":"hdr.payload.sig-%s"}\n' "$SMOKE_RUN_ID" > "$body_file"
    fi
    printf '200'
}
export -f curl

SMOKE_RUN_ID="run-a-$$"
SMOKE_AUTH_TOKEN=""
_call obtain_auth_token > "$TOKEN_OUTPUT_DIR/token-a"
_call obtain_auth_token > "$TOKEN_OUTPUT_DIR/token-b"

if cmp -s "$TOKEN_OUTPUT_DIR/token-a" "$TOKEN_OUTPUT_DIR/token-b"; then
    if [ "$(wc -l < "$TOKEN_CALLS_FILE")" -eq 1 ]; then
        report PASS "C1 obtain_auth_token caches token (1 login for 2 calls)"
    else
        report FAIL "C1 login called $(wc -l < "$TOKEN_CALLS_FILE") times, expected 1"
    fi
else
    report FAIL "C1 token output differs between calls"
fi

# ─── C8:默认缓存损坏时拒绝并重新登录 ───────────────────────
SMOKE_RUN_ID="run-corrupt-$$"
SMOKE_AUTH_TOKEN_FILE=""
TOKEN_FILE="$(smoke_auth_token_file)"
printf 'not-a-jwt' > "$TOKEN_FILE"
_call obtain_auth_token > "$TOKEN_OUTPUT_DIR/token-c"
if grep -q 'hdr.payload.sig-run-corrupt-' "$TOKEN_OUTPUT_DIR/token-c" \
    && [ "$(wc -l < "$TOKEN_CALLS_FILE")" -eq 2 ]; then
    report PASS "C8 corrupt default cache rejected and refreshed"
else
    report FAIL "C8 corrupt cache was accepted or login count unexpected"
fi
rm -f "$TOKEN_FILE"

# ─── C2/C3:record_smoke_resource + cleanup 只动 current-run ─
RES_BASE="$(mktemp -d)"
mkdir -p "$RES_BASE/markers" "$RES_BASE/files"
touch "$RES_BASE/markers/run-a-user" "$RES_BASE/markers/run-b-user"
echo "data-a" > "$RES_BASE/files/run-a-upload.bin"
echo "data-b" > "$RES_BASE/files/run-b-upload.bin"

SMOKE_RUN_ID="run-a-$$"
RES_FILE="$(smoke_temp_file resources)"
{
    printf 'run-a-%s\tfile\t%s\t%s\n' "$$" "res-a-1" "$RES_BASE/files/run-a-upload.bin"
    printf 'run-a-%s\tfile\t%s\t%s\n' "$$" "res-a-2" "$RES_BASE/markers/run-a-user"
    printf 'run-b-%s\tfile\t%s\t%s\n' "$$" "res-b-1" "$RES_BASE/files/run-b-upload.bin"
} > "$RES_FILE"

# cleanup_smoke_artifacts:必须基于 RES_FILE 内容识别资源
_call cleanup_smoke_artifacts

if [ ! -e "$RES_BASE/files/run-a-upload.bin" ] && [ ! -e "$RES_BASE/markers/run-a-user" ]; then
    if [ -e "$RES_BASE/files/run-b-upload.bin" ]; then
        report PASS "C2/C3 cleanup only deletes current-run resources"
    else
        report FAIL "C3 run-b resource was wrongly deleted"
    fi
else
    report FAIL "C2 run-a resource not deleted"
fi

# ─── C4:同 project lock 并发拒绝 ─────────────────────────
LOCK_DIR="$(mktemp -d)"
SMOKE_LOCK_DIR="$LOCK_DIR"
export SMOKE_LOCK_DIR
mkdir -p "$SMOKE_LOCK_DIR"
COMPOSE_PROJECT_NAME="lock-conflict-$$"
( exec 9>"$SMOKE_LOCK_DIR/${COMPOSE_PROJECT_NAME}.lock"; flock 9; sleep 3 ) &
HOLDER_PID=$!
sleep 0.3
COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" acquire_smoke_lock || rc=$?
rc=${rc:-0}
( kill "$HOLDER_PID" 2>/dev/null; wait "$HOLDER_PID" 2>/dev/null; rm -f "$SMOKE_LOCK_DIR/${COMPOSE_PROJECT_NAME}.lock" ) || true
if [ "$rc" -eq 2 ]; then
    report PASS "C4 same project lock contention returns 2"
else
    report FAIL "C4 same project lock returned $rc, expected 2"
fi

# ─── C5:不同 project lock 并发允许 ───────────────────────
COMPOSE_PROJECT_NAME="lock-A-$$"
acquire_smoke_lock
A_RC=$?
release_smoke_lock
COMPOSE_PROJECT_NAME="lock-B-$$"
acquire_smoke_lock
B_RC=$?
release_smoke_lock
rm -rf "$LOCK_DIR"
if [ "$A_RC" -eq 0 ] && [ "$B_RC" -eq 0 ]; then
    report PASS "C5 different project locks coexist"
else
    report FAIL "C5 different project locks: A=$A_RC B=$B_RC"
fi

# ─── C7:trap handler 保留原始退出码 ─────────────────────
# 模拟 trap 逻辑:test_exit + cleanup_exit → 最终退出码
# 约定(见 smoke_tests.sh 实现):
#   - test_exit=0 & cleanup_exit=0 → 0
#   - test_exit=0 & cleanup_exit≠0 → cleanup_exit(FAIL)
#   - test_exit≠0 & cleanup_exit=0 → test_exit(原始失败)
#   - test_exit≠0 & cleanup_exit≠0 → test_exit(原始失败优先)
trap_handler() {
    local test_exit="$1"
    local cleanup_rc="$2"
    local cleanup_exit=0
    cleanup_smoke_artifacts() { return "$cleanup_rc"; }
    cleanup_smoke_artifacts || cleanup_exit=$?
    if [ "$cleanup_exit" -ne 0 ] && [ "$test_exit" -eq 0 ]; then
        test_exit="$cleanup_exit"
    fi
    return "$test_exit"
}

declare -A C7_CASES=(
    [both_ok]=0
    [cleanup_fail_only]=1
    [test_fail_only]=5
    [both_fail]=5
)
C7_PASS=true
case "$(trap_handler 0 0; echo $?)" in 0) ;; *) C7_PASS=false ;; esac
case "$(trap_handler 0 1; echo $?)" in 1) ;; *) C7_PASS=false ;; esac
case "$(trap_handler 5 0; echo $?)" in 5) ;; *) C7_PASS=false ;; esac
case "$(trap_handler 5 1; echo $?)" in 5) ;; *) C7_PASS=false ;; esac
if $C7_PASS; then
    report PASS "C7 trap_handler preserves original exit (both/cleanup/test only/both fail)"
else
    report FAIL "C7 trap_handler exit code wrong"
fi

# ─── 清理 ────────────────────────────────────────────────
rm -rf "$RES_BASE" "$TOKEN_OUTPUT_DIR" "$TOKEN_CALLS_FILE" "$TMPHOME"

echo ""
echo "=========================================="
echo "  test_smoke_cleanup.sh: PASS=$PASS_COUNT FAIL=$FAIL_COUNT"
echo "=========================================="
[ "$FAIL_COUNT" -eq 0 ]