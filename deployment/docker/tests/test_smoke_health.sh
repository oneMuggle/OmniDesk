#!/usr/bin/env bash
# test_smoke_health.sh — 验证健康检查与 HTTP 状态分类的 fail-closed 语义
# 用法: bash deployment/docker/tests/test_smoke_health.sh
#
# 测试辅助函数(纯函数,不依赖 docker / curl):
#   check_service_health_from_values <service> <state> <health> [required|optional]
#   classify_http_status <code> <label>
#
# 关键约定:
#   - running + unhealthy 必须是 FAIL,不能被吞成 WARN/OK
#   - 业务 4xx/5xx 必须 FAIL
#   - 000 默认 FAIL,只在 SMOKE_ALLOW_NETWORK_SKIP=1 时 SKIP
#   - 429 默认 FAIL,只在 SMOKE_ALLOW_RATE_LIMIT_SKIP=1 时 WARN
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

# helper 函数在 result() 内更新 PASS/FAIL/WARN/SKIP 全局变量
# 测试中重置每个用例的计数,断言相对增量
reset_counters() {
    PASS=0; FAIL=0; WARN=0; SKIP=0
    export PASS FAIL WARN SKIP
}

# helper 调用用 _call 包裹,把期望的失败返回值吸收掉,不让 set -e 触发
_call() { "$@" || true; }

# ─── H1:running + healthy → PASS,counter 增加 1 ───────────
reset_counters
_call check_service_health_from_values backend running healthy required
if [ "$PASS" -eq 1 ] && [ "$FAIL" -eq 0 ]; then
    report PASS "H1 running+healthy increments PASS=1"
else
    report FAIL "H1 running+healthy wrong counters PASS=$PASS FAIL=$FAIL"
fi

# ─── H2:running + unhealthy required → FAIL,counter FAIL=1 ───
reset_counters
_call check_service_health_from_values backend running unhealthy required
if [ "$FAIL" -eq 1 ] && [ "$PASS" -eq 0 ]; then
    report PASS "H2 running+unhealthy required -> FAIL (not WARN)"
else
    report FAIL "H2 unhealthy not FAIL: PASS=$PASS FAIL=$FAIL"
fi

# ─── H3:starting required → FAIL ───────────────────────────
reset_counters
_call check_service_health_from_values worker starting starting required
if [ "$FAIL" -eq 1 ]; then
    report PASS "H3 starting required -> FAIL"
else
    report FAIL "H3 starting not FAIL: PASS=$PASS FAIL=$FAIL"
fi

# ─── H4:exited required → FAIL ─────────────────────────────
reset_counters
_call check_service_health_from_values db exited exited required
if [ "$FAIL" -eq 1 ]; then
    report PASS "H4 exited required -> FAIL"
else
    report FAIL "H4 exited not FAIL: PASS=$PASS FAIL=$FAIL"
fi

# ─── H5:服务不存在(required)→ FAIL ───────────────────────
reset_counters
_call check_service_health_from_values ragflow absent absent required
if [ "$FAIL" -eq 1 ]; then
    report PASS "H5 absent required -> FAIL"
else
    report FAIL "H5 absent required not FAIL: PASS=$PASS FAIL=$FAIL"
fi

# ─── H6:optional absent → SKIP ─────────────────────────────
reset_counters
_call check_service_health_from_values ragflow absent absent optional
if [ "$SKIP" -eq 1 ] && [ "$FAIL" -eq 0 ]; then
    report PASS "H6 absent optional -> SKIP"
else
    report FAIL "H6 absent optional wrong: SKIP=$SKIP FAIL=$FAIL"
fi

# ─── H7:optional running+unhealthy → FAIL(健康,但服务被允许时仍要求健康) ──
reset_counters
_call check_service_health_from_values ragflow running unhealthy optional
if [ "$FAIL" -eq 1 ]; then
    report PASS "H7 optional unhealthy still FAIL (allow absent, not unhealthy)"
else
    report FAIL "H7 optional unhealthy not FAIL: PASS=$PASS FAIL=$FAIL"
fi

# ─── HTTP1:200 → PASS ─────────────────────────────────────
reset_counters
_call classify_http_status 200 health
if [ "$PASS" -eq 1 ] && [ "$FAIL" -eq 0 ]; then
    report PASS "HTTP1 200 -> PASS"
else
    report FAIL "HTTP1 200 wrong: PASS=$PASS FAIL=$FAIL"
fi

# ─── HTTP2:503 → FAIL(不能蒙混成 PASS) ────────────────────
reset_counters
_call classify_http_status 503 health
if [ "$FAIL" -eq 1 ] && [ "$PASS" -eq 0 ]; then
    report PASS "HTTP2 503 -> FAIL"
else
    report FAIL "HTTP2 503 wrong: PASS=$PASS FAIL=$FAIL"
fi

# ─── HTTP3:404 → FAIL ─────────────────────────────────────
reset_counters
_call classify_http_status 404 version
if [ "$FAIL" -eq 1 ]; then
    report PASS "HTTP3 404 -> FAIL"
else
    report FAIL "HTTP3 404 wrong: PASS=$PASS FAIL=$FAIL"
fi

# ─── HTTP4:000 → FAIL(默认,无 ALLOW_NETWORK_SKIP) ─────────
reset_counters
SMOKE_ALLOW_NETWORK_SKIP=0
_call classify_http_status 000 health
if [ "$FAIL" -eq 1 ]; then
    report PASS "HTTP4 000 default -> FAIL"
else
    report FAIL "HTTP4 000 default wrong: PASS=$PASS FAIL=$FAIL SKIP=$SKIP"
fi

# ─── HTTP5:000 + ALLOW_NETWORK_SKIP=1 → SKIP ──────────────
reset_counters
SMOKE_ALLOW_NETWORK_SKIP=1
_call classify_http_status 000 health
if [ "$SKIP" -eq 1 ] && [ "$FAIL" -eq 0 ]; then
    report PASS "HTTP5 000 + ALLOW_NETWORK_SKIP=1 -> SKIP"
else
    report FAIL "HTTP5 000+SKIP wrong: SKIP=$SKIP FAIL=$FAIL"
fi

# ─── HTTP6:429 默认 → FAIL ────────────────────────────────
reset_counters
SMOKE_ALLOW_RATE_LIMIT_SKIP=0
_call classify_http_status 429 rate_limited
if [ "$FAIL" -eq 1 ]; then
    report PASS "HTTP6 429 default -> FAIL"
else
    report FAIL "HTTP6 429 default wrong: PASS=$PASS FAIL=$FAIL WARN=$WARN"
fi

# ─── HTTP7:429 + ALLOW_RATE_LIMIT_SKIP=1 → WARN ───────────
reset_counters
SMOKE_ALLOW_RATE_LIMIT_SKIP=1
_call classify_http_status 429 rate_limited
if [ "$WARN" -eq 1 ] && [ "$FAIL" -eq 0 ]; then
    report PASS "HTTP7 429 + ALLOW_RATE_LIMIT_SKIP=1 -> WARN"
else
    report FAIL "HTTP7 429+SKIP wrong: WARN=$WARN FAIL=$FAIL"
fi

# ─── HTTP8:未知 3xx → FAIL ────────────────────────────────
reset_counters
_call classify_http_status 301 redirect_test
if [ "$FAIL" -eq 1 ]; then
    report PASS "HTTP8 301 -> FAIL (only 2xx is PASS)"
else
    report FAIL "HTTP8 301 wrong: PASS=$PASS FAIL=$FAIL"
fi

# ─── HTTP9:SMOKE_STRICT=1 下 SKIP 必须升级为 FAIL ────────
reset_counters
SMOKE_STRICT=1
SMOKE_ALLOW_NETWORK_SKIP=1
_call classify_http_status 000 health
if [ "$FAIL" -eq 1 ] && [ "$SKIP" -eq 0 ]; then
    report PASS "HTTP9 SMOKE_STRICT=1 promotes SKIP to FAIL"
else
    report FAIL "HTTP9 strict promote wrong: FAIL=$FAIL SKIP=$SKIP"
fi

echo ""
echo "=========================================="
echo "  test_smoke_health.sh: PASS=$PASS_COUNT FAIL=$FAIL_COUNT"
echo "=========================================="
[ "$FAIL_COUNT" -eq 0 ]
