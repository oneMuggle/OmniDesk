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
VERSION_TOKEN="$(obtain_auth_token || true)"
if [ -n "$VERSION_TOKEN" ]; then
    HTTP_CODE=$(request_with_status GET "$BASE_URL/api/system/version/" "$VERSION_BODY" \
        -H "Authorization: Bearer $VERSION_TOKEN")
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
    if [ -z "$VERSION_TOKEN" ]; then
        result "FAIL" "Backend /api/system/version/" "无法取得 JWT,受保护端点未执行"
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

GUEST_TOKEN=$(curl -s --max-time 10 "$BASE_URL/api/auth/guest-login/" \
    -X POST -H "Content-Type: application/json" -d '{}' \
    2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('access',''))" 2>/dev/null || echo "")

if [ -n "$GUEST_TOKEN" ]; then
    result "PASS" "Guest login returns access token"
    PROTECTED_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL/api/users/me/" \
        -H "Authorization: Bearer $GUEST_TOKEN" 2>/dev/null || echo "000")
    if [ "$PROTECTED_CODE" = "200" ]; then
        result "PASS" "Authenticated API request successful (HTTP $PROTECTED_CODE)"
    else
        result "FAIL" "Authenticated API request" "Got HTTP $PROTECTED_CODE"
    fi
else
    result "FAIL" "Guest login" "No access token returned"
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
