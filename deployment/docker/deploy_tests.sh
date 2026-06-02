#!/bin/bash

# deploy_tests.sh — 部署后完整测试（10 个检查阶段）
# 重构自 smoke_tests.sh，增加了关键业务流程、环境变量、静态文件等验证
# 使用方法: ./deploy_tests.sh [base_url]
# 默认测试 http://localhost

set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$COMPOSE_DIR"

BASE_URL="${1:-http://localhost}"

PASS=0
FAIL=0
SKIP=0

result() {
    local status="$1"
    local msg="$2"
    local detail="${3:-}"
    case "$status" in
        PASS) echo "  PASS: $msg"; PASS=$((PASS + 1)) ;;
        FAIL) echo "  FAIL: $msg"; FAIL=$((FAIL + 1)); [ -n "$detail" ] && echo "    -> $detail" ;;
        SKIP) echo "  SKIP: $msg"; SKIP=$((SKIP + 1)) ;;
    esac
}

COMPOSE_FILE="-f docker-compose.offline-standalone.yml"
ENV_FILE="--env-file .env.production"

compose() {
    docker compose $COMPOSE_FILE $ENV_FILE "$@"
}

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
    echo "FAIL: 无法访问 Docker Compose，退出测试"
    exit 1
fi

ALL_RUNNING=true
for service in db redis backend frontend worker nginx; do
    CONTAINER_ID=$(compose ps -q "$service" 2>/dev/null || true)
    if [ -n "$CONTAINER_ID" ]; then
        STATE=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_ID" 2>/dev/null || echo "unknown")
        if [ "$STATE" = "running" ]; then
            echo "  OK: $service (state=$STATE)"
        else
            echo "  FAIL: $service not running (state=$STATE)"
            ALL_RUNNING=false
        fi
    else
        echo "  SKIP: $service not found (optional service)"
    fi
done

if [ "$ALL_RUNNING" = true ]; then
    result "PASS" "All required services running"
else
    result "FAIL" "Some services not running"
fi
echo ""

# ─── 阶段 2: 前端可访问性 ───────────────────────────────────
echo "阶段 2: 前端可访问性"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL/" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    result "PASS" "Frontend serves HTTP 200 at $BASE_URL/"
else
    result "FAIL" "Frontend HTTP check" "Expected 200, got $HTTP_CODE"
fi

HTML_CONTENT=$(curl -s --max-time 10 "$BASE_URL/" 2>/dev/null || echo "")
if echo "$HTML_CONTENT" | grep -q '<div id="root"'; then
    result "PASS" "Frontend HTML contains root element"
else
    result "FAIL" "Frontend HTML structure" "Missing <div id=\"root\">"
fi
echo ""

# ─── 阶段 3: 后端 API 连通性 ────────────────────────────────
echo "阶段 3: 后端 API 连通性"

HEALTH_RESPONSE=$(curl -s --max-time 10 "$BASE_URL/api/health/" 2>/dev/null || echo "")
if echo "$HEALTH_RESPONSE" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
    result "PASS" "Backend /api/health/ returns JSON"
    DB_STATUS=$(echo "$HEALTH_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('database','unknown'))" 2>/dev/null)
    if [ "$DB_STATUS" = "ok" ]; then
        result "PASS" "Database connection healthy"
    else
        result "FAIL" "Database connection" "Status: $DB_STATUS"
    fi
else
    result "FAIL" "Backend /api/health/ not responding"
fi

VERSION_RESPONSE=$(curl -s --max-time 10 "$BASE_URL/api/system/version/" 2>/dev/null || echo "")
if echo "$VERSION_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'version' in d" 2>/dev/null; then
    VERSION=$(echo "$VERSION_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['version'])" 2>/dev/null)
    result "PASS" "Backend version: $VERSION"
else
    result "SKIP" "Backend version endpoint" "Not available"
fi

PROXY_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL/api/auth/guest-login/" -X POST -H "Content-Type: application/json" -d '{}' 2>/dev/null || echo "000")
if [ "$PROXY_CODE" != "000" ] && [ "$PROXY_CODE" != "502" ] && [ "$PROXY_CODE" != "503" ]; then
    result "PASS" "Nginx reverse proxy to backend (HTTP $PROXY_CODE)"
else
    result "FAIL" "Nginx reverse proxy" "Got HTTP $PROXY_CODE"
fi
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

if [ -f ".env.production" ]; then
    REDIS_PASSWORD=$(grep "^REDIS_PASSWORD=" .env.production 2>/dev/null | cut -d= -f2- || echo "")
    REDIS_PING=$(compose exec -T redis redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null || echo "FAIL")
    if echo "$REDIS_PING" | grep -q "PONG"; then
        result "PASS" "Redis responds to PING"
    else
        result "FAIL" "Redis ping" "Response: $REDIS_PING"
    fi
else
    result "SKIP" "Redis" ".env.production not found"
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

# ─── 阶段 9: 环境变量注入验证 ──────────────────────────────
echo "阶段 9: 环境变量注入"

for var in DJANGO_SETTINGS_MODULE POSTGRES_DB; do
    VALUE=$(compose exec -T backend env 2>/dev/null | grep "^${var}=" | cut -d= -f2- || echo "")
    if [ -n "$VALUE" ]; then
        result "PASS" "Backend env: $var is set"
    else
        result "FAIL" "Backend env: $var" "Not found"
    fi
done

REACT_API_URL=$(compose exec -T frontend env 2>/dev/null | grep "^REACT_APP_API_BASE_URL=" | cut -d= -f2- || echo "")
if [ -n "$REACT_API_URL" ]; then
    result "PASS" "Frontend env: REACT_APP_API_BASE_URL=$REACT_API_URL"
else
    result "SKIP" "Frontend env: REACT_APP_API_BASE_URL" "Not found (may be baked into build)"
fi
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
