#!/bin/bash

# deploy_tests.sh — 部署后完整测试（10 个检查阶段）
# 重构自 smoke_tests.sh，增加了关键业务流程、环境变量、静态文件等验证
# 使用方法: ./deploy_tests.sh [base_url]
# 默认测试 http://localhost

# shellcheck disable=SC1091
SMOKE_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export SMOKE_SCRIPT_DIR
source "$SMOKE_SCRIPT_DIR/smoke_common.sh"

if ! init_smoke_context "${1:-}"; then
    echo "ERROR: deploy context init failed; required compose/env not found" >&2
    exit 1
fi

# 不加 -e:result() 自控制流程,需要宽容失败
set -uo pipefail

cleanup_deploy_test_resources() {
    local test_exit="$?"
    cleanup_smoke_artifacts || true
    release_smoke_lock
    exit "$test_exit"
}

trap cleanup_deploy_test_resources EXIT

if ! acquire_smoke_lock; then
    exit 2
fi

# compose() 来自 smoke_common.sh;export 给子 shell 使用
export -f compose

echo "=========================================="
echo "  OmniDesk 部署测试"
echo "  目标: $BASE_URL"
echo "  日期: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# ─── 阶段 1: 容器状态 ───────────────────────────────────────
echo "阶段 1: 容器状态"

if compose ps >/dev/null 2>&1; then
    result "PASS" "Docker compose services available"
else
    result "FAIL" "Docker compose not available"
    echo "FAIL: 无法访问 Docker Compose,退出测试"
    exit 1
fi

# 用 check_service_health 强制 fail-closed:running+unhealthy 必须 FAIL
SERVICES_HEALTHY=true
for service in db redis backend frontend worker; do
    if check_service_health "$service" required; then
        :
    else
        SERVICES_HEALTHY=false
    fi
done

if [ "$SERVICES_HEALTHY" = true ]; then
    result "PASS" "All required services healthy"
else
    result "FAIL" "One or more required services unhealthy"
fi
echo ""

# ─── 阶段 2: 前端可访问性 ───────────────────────────────────
echo "阶段 2: 前端可访问性"

FRONTEND_BODY="$(smoke_temp_file deploy-frontend-body)"
HTTP_CODE=$(request_with_status GET "$BASE_URL/" "$FRONTEND_BODY")
classify_http_status "$HTTP_CODE" "Frontend GET $BASE_URL/"
rm -f "$FRONTEND_BODY"

FRONTEND_BODY="$(smoke_temp_file deploy-frontend-html)"
HTTP_CODE=$(request_with_status GET "$BASE_URL/" "$FRONTEND_BODY")
if [ "$HTTP_CODE" = "200" ] && grep -q '<div id="root"' "$FRONTEND_BODY" 2>/dev/null; then
    result "PASS" "Frontend HTML contains root element"
else
    result "FAIL" "Frontend HTML structure" "Missing <div id=\"root\"> (HTTP $HTTP_CODE)"
fi
rm -f "$FRONTEND_BODY"
echo ""

# ─── 阶段 3: 后端 API 连通性 ────────────────────────────────
echo "阶段 3: 后端 API 连通性"

HEALTH_BODY="$(smoke_temp_file deploy-health-body)"
HTTP_CODE=$(request_with_status GET "$BASE_URL/api/health/" "$HEALTH_BODY")
if [ "$HTTP_CODE" = "200" ]; then
    STATUS_OK=$(python3 -c "import sys,json; print(json.load(open('$HEALTH_BODY')).get('status',''))" 2>/dev/null || echo "")
    DB_OK=$(python3 -c "import sys,json; print(json.load(open('$HEALTH_BODY')).get('database',''))" 2>/dev/null || echo "")
    REDIS_OK=$(python3 -c "import sys,json; print(json.load(open('$HEALTH_BODY')).get('redis',''))" 2>/dev/null || echo "")
    if [ "$STATUS_OK" = "ok" ] && [ "$DB_OK" = "ok" ] && [ "$REDIS_OK" = "ok" ]; then
        result "PASS" "Backend /api/health/ status=database=redis=ok"
    else
        result "FAIL" "Backend /api/health/ body" "status=$STATUS_OK database=$DB_OK redis=$REDIS_OK"
    fi
else
    classify_http_status "$HTTP_CODE" "Backend /api/health/"
fi
rm -f "$HEALTH_BODY"

VERSION_BODY="$(smoke_temp_file deploy-version-body)"
VERSION_TOKEN_FILE="$(smoke_auth_token_file)"
VERSION_HEADER_FILE=""
if obtain_auth_token >/dev/null 2>&1; then
    record_smoke_resource auth-token "auth-token-$$" "$VERSION_TOKEN_FILE" || true
    VERSION_HEADER_FILE="$(smoke_auth_header_file "$VERSION_TOKEN_FILE" || true)"
fi
if [ -n "$VERSION_HEADER_FILE" ]; then
    HTTP_CODE=$(request_with_status GET "$BASE_URL/api/system/version/" "$VERSION_BODY" \
        -H "@$VERSION_HEADER_FILE")
else
    HTTP_CODE="000"
fi
if [ "$HTTP_CODE" = "200" ]; then
    if python3 -c "import sys,json; d=json.load(open('$VERSION_BODY')); assert 'version' in d" 2>/dev/null; then
        VERSION=$(python3 -c "import sys,json; print(json.load(open('$VERSION_BODY'))['version'])" 2>/dev/null || echo unknown)
        result "PASS" "Backend version: $VERSION"
    else
        result "FAIL" "Backend /api/system/version/ missing version field"
    fi
else
    if [ -z "$VERSION_HEADER_FILE" ]; then
        result "FAIL" "Backend /api/system/version/" "无法取得有效 JWT,受保护端点未执行"
    else
        classify_http_status "$HTTP_CODE" "Backend /api/system/version/"
    fi
fi
rm -f "$VERSION_BODY"

PROXY_BODY="$(smoke_temp_file deploy-proxy-body)"
HTTP_CODE=$(request_with_status POST "$BASE_URL/api/auth/guest-login/" "$PROXY_BODY" \
    -H "Content-Type: application/json" -d '{}')
case "$HTTP_CODE" in
    2??|400|401|403|405)
        result "PASS" "Nginx reverse proxy to backend (HTTP $HTTP_CODE)"
        ;;
    *)
        result "FAIL" "Nginx reverse proxy" "Got HTTP $HTTP_CODE"
        ;;
esac
rm -f "$PROXY_BODY"
echo ""

# ─── 阶段 4: 数据库连接验证 ─────────────────────────────────
echo "阶段 4: 数据库连接验证"

if compose ps -q db >/dev/null 2>&1; then
    DB_QUERY=$(compose exec -T backend python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'omni_desk_backend.settings.production')
django.setup()
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('SELECT 1')
    print('OK')
" 2>/dev/null || echo "FAIL")

    if [ "$DB_QUERY" = "OK" ]; then
        result "PASS" "Database query successful from backend"
    else
        result "FAIL" "Database query failed"
    fi
else
    result "SKIP" "Database container not found"
fi
echo ""

# ─── 阶段 5: Redis 连通性 ───────────────────────────────────
echo "阶段 5: Redis 连通性"

if [ -n "${ENV_FILE_PATH:-}" ] && [ -f "$ENV_FILE_PATH" ]; then
    REDIS_PASSWORD=$(grep "^REDIS_PASSWORD=" "$ENV_FILE_PATH" 2>/dev/null | cut -d= -f2- || echo "")
    # SECURITY FIX: Use REDISCLI_AUTH env var instead of -a flag to avoid password exposure in process list
    REDIS_PING=$(compose exec -T -e REDISCLI_AUTH="$REDIS_PASSWORD" redis redis-cli ping 2>/dev/null || echo "FAIL")
    if echo "$REDIS_PING" | grep -q "PONG"; then
        result "PASS" "Redis responds to PING"
    else
        result "FAIL" "Redis ping" "Response: $REDIS_PING"
    fi
else
    result "SKIP" "Redis" "resolved env file not found: ${ENV_FILE_PATH:-unset}"
fi
echo ""

# ─── 阶段 6: Celery Worker 状态 ─────────────────────────────
echo "阶段 6: Celery Worker 状态"

WORKER_STATUS=$(compose ps worker 2>/dev/null || echo "")
if echo "$WORKER_STATUS" | grep -q "Up"; then
    result "PASS" "Celery worker process running"
else
    result "FAIL" "Celery worker" "Status: $WORKER_STATUS"
fi
echo ""

# ─── 阶段 7: 关键业务流程验证 ──────────────────────────────
echo "阶段 7: 关键业务流程"

GUEST_BODY="$(smoke_temp_file deploy-guest-body)"
GUEST_TOKEN_FILE="$(smoke_temp_file deploy-guest-token)"
GUEST_HEADER_FILE=""
(umask 077; : > "$GUEST_BODY"; : > "$GUEST_TOKEN_FILE") || exit 1
chmod 600 "$GUEST_BODY" "$GUEST_TOKEN_FILE" || exit 1
record_smoke_resource guest-body "guest-body-$$" "$GUEST_BODY" || exit 1
record_smoke_resource guest-token "guest-token-$$" "$GUEST_TOKEN_FILE" || exit 1
GUEST_HTTP=$(curl -sS -X POST -o "$GUEST_BODY" -w '%{http_code}' --max-time 10 \
    -H "Content-Type: application/json" --data '{}' "$BASE_URL/api/auth/guest-login/" 2>/dev/null || printf '000')
if [ "$GUEST_HTTP" = "200" ]; then
    python3 - "$GUEST_BODY" "$GUEST_TOKEN_FILE" <<'PY'
import json, os, sys
with open(sys.argv[1]) as body_file:
    payload = json.load(body_file)
token = payload.get("access", "") if isinstance(payload, dict) else ""
if not isinstance(token, str) or not token:
    raise SystemExit(1)
with open(sys.argv[2], "w") as token_file:
    token_file.write(token)
os.chmod(sys.argv[2], 0o600)
PY
    if cat "$GUEST_TOKEN_FILE" | smoke_auth_token_is_valid; then
        GUEST_HEADER_FILE="$(smoke_auth_header_file "$GUEST_TOKEN_FILE" || true)"
    fi
fi
if [ -n "$GUEST_HEADER_FILE" ]; then
    result "PASS" "Guest login returns valid access token"
    PROTECTED_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL/api/users/me/" \
        -H "@$GUEST_HEADER_FILE" 2>/dev/null || echo "000")
    if [ "$PROTECTED_CODE" = "200" ]; then
        result "PASS" "Authenticated API request successful (HTTP $PROTECTED_CODE)"
    else
        result "FAIL" "Authenticated API request" "Got HTTP $PROTECTED_CODE"
    fi
else
    case "$GUEST_HTTP" in
        429) result "WARN" "Guest login rate-limited" "HTTP 429" ;;
        *) result "FAIL" "Guest login" "HTTP $GUEST_HTTP or invalid access token" ;;
    esac
fi
echo ""

# ─── 阶段 8: 反向代理配置验证 ──────────────────────────────
echo "阶段 8: 反向代理配置"

API_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL/api/health/" 2>/dev/null || echo "000")
if [ "$API_CODE" = "200" ]; then
    result "PASS" "/api/ routes to backend"
else
    result "FAIL" "/api/ routing" "Got HTTP $API_CODE"
fi

ADMIN_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL/admin/login/" 2>/dev/null || echo "000")
if [ "$ADMIN_CODE" = "200" ]; then
    result "PASS" "/admin/ routes to backend"
else
    result "FAIL" "/admin/ routing" "Got HTTP $ADMIN_CODE"
fi

ROOT_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL/" 2>/dev/null || echo "000")
if [ "$ROOT_CODE" = "200" ]; then
    result "PASS" "/ routes to frontend"
else
    result "FAIL" "/ routing" "Got HTTP $ROOT_CODE"
fi
echo ""

# ─── 阶段 9: 后端环境变量注入验证 ───────────────────────────
echo "阶段 9: 后端环境变量注入"

for var in DJANGO_SETTINGS_MODULE POSTGRES_DB; do
    VALUE=$(compose exec -T backend env 2>/dev/null | grep "^${var}=" | cut -d= -f2- || echo "")
    if [ -n "$VALUE" ]; then
        result "PASS" "Backend env: $var is set"
    else
        result "FAIL" "Backend env: $var" "Not found"
    fi
done
echo ""

# ─── 阶段 10: 静态文件路径验证 ─────────────────────────────
echo "阶段 10: 静态文件路径"

JS_CHECK=$(curl -s --max-time 10 "$BASE_URL/" 2>/dev/null | grep -oP 'src="[^"]*\.js"' | head -1 | sed 's/src="//;s/"//' || echo "")
if [ -n "$JS_CHECK" ]; then
    JS_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL$JS_CHECK" 2>/dev/null || echo "000")
    if [ "$JS_CODE" = "200" ]; then
        result "PASS" "Frontend JS bundle loads (HTTP $JS_CODE)"
    else
        result "FAIL" "Frontend JS bundle" "Got HTTP $JS_CODE for $JS_CHECK"
    fi
else
    result "SKIP" "Frontend JS bundle" "Could not find JS reference"
fi

CSS_CHECK=$(curl -s --max-time 10 "$BASE_URL/" 2>/dev/null | grep -oP 'href="[^"]*\.css"' | head -1 | sed 's/href="//;s/"//' || echo "")
if [ -n "$CSS_CHECK" ]; then
    CSS_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL$CSS_CHECK" 2>/dev/null || echo "000")
    if [ "$CSS_CODE" = "200" ]; then
        result "PASS" "Frontend CSS loads (HTTP $CSS_CODE)"
    else
        result "FAIL" "Frontend CSS" "Got HTTP $CSS_CODE for $CSS_CHECK"
    fi
else
    result "SKIP" "Frontend CSS" "Could not find CSS reference"
fi
echo ""

# ─── 总结 ────────────────────────────────────────────────────
echo "=========================================="
echo "  测试结果"
echo "=========================================="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
echo "  SKIP: $SKIP"
TOTAL=$((PASS + FAIL))
if [ "$TOTAL" -gt 0 ]; then
    PASS_RATE=$((PASS * 100 / TOTAL))
    echo "  通过率: ${PASS_RATE}%"
fi
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "STATUS: FAILED — $FAIL 个测试未通过"
    exit 1
else
    echo "STATUS: ALL PASSED"
    exit 0
fi
