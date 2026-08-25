#!/usr/bin/env bash
# test_smoke_protocols.sh — 验证协议层辅助函数的契约
# 用法: bash deployment/docker/tests/test_smoke_protocols.sh
#
# 覆盖:
#   P1: check_version_endpoint — 200 + version+channel 与 manifest 一致 → PASS
#   P2: check_version_endpoint — version 不一致 → FAIL
#   P3: check_version_endpoint — channel 不一致 → FAIL
#   P4: check_version_endpoint — HTTP 非 200 → FAIL(用 stub 测)
#   P5: check_cors_preflight — 合法 origin + 完整 allow headers → PASS
#   P6: check_cors_preflight — 合法 origin 但缺 Access-Control-Allow-Headers → FAIL
#   P7: check_cors_preflight — 非法 origin 不被反射/允许 → PASS(被拒)
#   P8: check_optional_ragflow — disabled → SKIP, 不允许出现 PASS
#   P9: check_optional_ragflow — enabled + 两服务 healthy → PASS
#   P10: check_optional_ragflow — enabled 但 ragflow-mysql absent → FAIL
#   P11: check_lazy_routes — manifest 中 URL 都 200 → PASS
#   P12: check_lazy_routes — manifest 中一个 URL 404 → FAIL
set -uo pipefail

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
reset_counters() {
    PASS=0; FAIL=0; WARN=0; SKIP=0
    export PASS FAIL WARN SKIP
}

# ─── P1:check_version_endpoint 一致 → PASS ────────────────
reset_counters
VERSION_BODY="$(mktemp)"
printf '{"version":"1.2.3","channel":"stable"}' > "$VERSION_BODY"
check_version_endpoint 200 "$VERSION_BODY" "1.2.3" "stable"
RC=$?
rm -f "$VERSION_BODY"
if [ "$PASS" -eq 1 ] && [ "$FAIL" -eq 0 ] && [ "$RC" -eq 0 ]; then
    report PASS "P1 version/channel match -> PASS"
else
    report FAIL "P1 wrong: PASS=$PASS FAIL=$FAIL RC=$RC"
fi

# ─── P2:version 不一致 → FAIL ────────────────────────────
reset_counters
VERSION_BODY="$(mktemp)"
printf '{"version":"0.9.0","channel":"stable"}' > "$VERSION_BODY"
check_version_endpoint 200 "$VERSION_BODY" "1.2.3" "stable"
RC=$?
rm -f "$VERSION_BODY"
if [ "$FAIL" -eq 1 ] && [ "$RC" -ne 0 ]; then
    report PASS "P2 version mismatch -> FAIL"
else
    report FAIL "P2 wrong: FAIL=$FAIL RC=$RC"
fi

# ─── P3:channel 不一致 → FAIL ─────────────────────────────
reset_counters
VERSION_BODY="$(mktemp)"
printf '{"version":"1.2.3","channel":"beta"}' > "$VERSION_BODY"
check_version_endpoint 200 "$VERSION_BODY" "1.2.3" "stable"
RC=$?
rm -f "$VERSION_BODY"
if [ "$FAIL" -eq 1 ] && [ "$RC" -ne 0 ]; then
    report PASS "P3 channel mismatch -> FAIL"
else
    report FAIL "P3 wrong: FAIL=$FAIL RC=$RC"
fi

# ─── P4:HTTP 非 200 → FAIL ───────────────────────────────
reset_counters
VERSION_BODY="$(mktemp)"
printf '{}' > "$VERSION_BODY"
check_version_endpoint 503 "$VERSION_BODY" "1.2.3" "stable"
RC=$?
rm -f "$VERSION_BODY"
if [ "$FAIL" -eq 1 ] && [ "$RC" -ne 0 ]; then
    report PASS "P4 HTTP 503 -> FAIL"
else
    report FAIL "P4 wrong: FAIL=$FAIL RC=$RC"
fi

# ─── P5:CORS 合法 origin + 完整 allow headers → PASS ──────
reset_counters
HEADERS_BODY="$(mktemp)"
{
    printf 'HTTP/1.1 204 No Content\r\n'
    printf 'Access-Control-Allow-Origin: http://localhost:3000\r\n'
    printf 'Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n'
    printf 'Access-Control-Allow-Headers: Content-Type, Authorization\r\n'
    printf 'Access-Control-Allow-Credentials: true\r\n'
    printf '\r\n'
} > "$HEADERS_BODY"
check_cors_preflight 204 "$HEADERS_BODY" "http://localhost:3000" "POST" "Content-Type, Authorization"
RC=$?
rm -f "$HEADERS_BODY"
if [ "$PASS" -eq 1 ] && [ "$FAIL" -eq 0 ] && [ "$RC" -eq 0 ]; then
    report PASS "P5 legal CORS preflight -> PASS"
else
    report FAIL "P5 wrong: PASS=$PASS FAIL=$FAIL RC=$RC"
fi

# ─── P6:CORS 合法 origin 但缺 Allow-Headers → FAIL ────────
reset_counters
HEADERS_BODY="$(mktemp)"
{
    printf 'HTTP/1.1 204 No Content\r\n'
    printf 'Access-Control-Allow-Origin: http://localhost:3000\r\n'
    printf 'Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n'
    printf 'Access-Control-Allow-Credentials: true\r\n'
    printf '\r\n'
} > "$HEADERS_BODY"
check_cors_preflight 204 "$HEADERS_BODY" "http://localhost:3000" "POST" "Content-Type, Authorization"
RC=$?
rm -f "$HEADERS_BODY"
if [ "$FAIL" -eq 1 ] && [ "$RC" -ne 0 ]; then
    report PASS "P6 missing Allow-Headers -> FAIL"
else
    report FAIL "P6 wrong: FAIL=$FAIL RC=$RC"
fi

# ─── P7:CORS 非法 origin 不被反射 → PASS(被拒) ──────────
reset_counters
HEADERS_BODY="$(mktemp)"
printf 'HTTP/1.1 403 Forbidden\r\n\r\n' > "$HEADERS_BODY"
check_cors_preflight 403 "$HEADERS_BODY" "http://evil.example.com" "POST" "Content-Type, Authorization"
RC=$?
rm -f "$HEADERS_BODY"
# 期望:非法 origin 被拒,403 → PASS(契约:拒了就是 PASS)
if [ "$PASS" -eq 1 ] && [ "$RC" -eq 0 ]; then
    report PASS "P7 illegal origin rejected -> PASS"
else
    report FAIL "P7 wrong: PASS=$PASS FAIL=$FAIL RC=$RC (illegal origin must be rejected)"
fi

# ─── P8:check_optional_ragflow disabled → SKIP ────────────
reset_counters
check_optional_ragflow "disabled" "" ""
RC=$?
if [ "$SKIP" -ge 1 ] && [ "$PASS" -eq 0 ]; then
    report PASS "P8 RAGFlow disabled -> SKIP only (no PASS)"
else
    report FAIL "P8 wrong: SKIP=$SKIP PASS=$PASS RC=$RC"
fi

# ─── P9:check_optional_ragflow enabled + healthy → PASS ────
reset_counters
check_optional_ragflow "enabled" "running,healthy" "running,healthy"
RC=$?
if [ "$PASS" -ge 1 ] && [ "$FAIL" -eq 0 ]; then
    report PASS "P9 RAGFlow enabled+healthy -> PASS"
else
    report FAIL "P9 wrong: PASS=$PASS FAIL=$FAIL RC=$RC"
fi

# ─── P10:check_optional_ragflow enabled 但 mysql absent → FAIL ──
reset_counters
check_optional_ragflow "enabled" "absent,absent" "running,healthy"
RC=$?
if [ "$FAIL" -ge 1 ] && [ "$PASS" -eq 0 ]; then
    report PASS "P10 RAGFlow enabled but mysql absent -> FAIL"
else
    report FAIL "P10 wrong: PASS=$PASS FAIL=$FAIL RC=$RC"
fi

# ─── P11:check_lazy_routes manifest 全 200 → PASS ─────────
reset_counters
ROUTES_JSON="$(mktemp)"
cat > "$ROUTES_JSON" <<'EOF'
{
  "routes": [
    {"path": "/", "asset": "/static/js/main.js"},
    {"path": "/login", "asset": "/static/js/login.js"}
  ]
}
EOF
request_with_status() {
    printf '200'
}
export -f request_with_status
check_lazy_routes "$ROUTES_JSON"
RC=$?
rm -f "$ROUTES_JSON"
if [ "$PASS" -ge 1 ] && [ "$FAIL" -eq 0 ] && [ "$RC" -eq 0 ]; then
    report PASS "P11 all assets 200 -> PASS"
else
    report FAIL "P11 wrong: PASS=$PASS FAIL=$FAIL RC=$RC"
fi

# ─── P12:check_lazy_routes 一个 URL 404 → FAIL ────────────
reset_counters
ROUTES_JSON="$(mktemp)"
cat > "$ROUTES_JSON" <<'EOF'
{
  "routes": [
    {"path": "/", "asset": "/static/js/main.js"},
    {"path": "/login", "asset": "/static/js/login.js"}
  ]
}
EOF
request_with_status() {
    case "$2" in
        */login.js) printf '404' ;;
        *) printf '200' ;;
    esac
}
export -f request_with_status
check_lazy_routes "$ROUTES_JSON"
RC=$?
rm -f "$ROUTES_JSON"
if [ "$FAIL" -ge 1 ] && [ "$RC" -ne 0 ]; then
    report PASS "P12 one asset 404 -> FAIL"
else
    report FAIL "P12 wrong: PASS=$PASS FAIL=$FAIL RC=$RC"
fi

echo ""
echo "=========================================="
echo "  test_smoke_protocols.sh: PASS=$PASS_COUNT FAIL=$FAIL_COUNT"
echo "=========================================="
[ "$FAIL_COUNT" -eq 0 ]