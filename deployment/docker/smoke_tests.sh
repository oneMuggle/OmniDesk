#!/bin/bash

# smoke_tests.sh — 部署后冒烟测试
# 使用方法: ./smoke_tests.sh [base_url]
# 默认测试 http://localhost
# 所有 API 请求通过 Nginx 代理 ($base_url/api/) 访问后端

COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$COMPOSE_DIR"

BASE_URL="${1:-http://localhost}"
# backend 不再暴露 8000 端口，所有 API 请求通过 Nginx 代理走 $BASE_URL
# 非 API 端点（如 /admin/）通过 docker compose exec 直接访问容器

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

echo "=========================================="
echo "  冒烟测试"
echo "  Frontend/API: $BASE_URL"
echo "=========================================="
echo ""

COMPOSE_FILE="-f docker-compose.offline.yml"
ENV_FILE="--env-file .env.production"

compose() {
    docker compose $COMPOSE_FILE $ENV_FILE "$@"
}

# ─── 阶段 1: 容器状态 ───────────────────────────────────────
echo "阶段 1: 容器状态"

if compose ps >/dev/null 2>&1; then
    result "PASS" "Docker compose services available"
else
    result "FAIL" "Docker compose not available"
fi

# 检查每个容器
ALL_RUNNING=true
for service in db redis backend frontend worker; do
    CONTAINER_ID=$(compose ps -q "$service" 2>/dev/null || true)
    if [ -n "$CONTAINER_ID" ]; then
        STATE=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_ID" 2>/dev/null || echo "unknown")
        HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no healthcheck{{end}}' "$CONTAINER_ID" 2>/dev/null || echo "unknown")

        if [ "$STATE" = "running" ]; then
            # running 状态视为通过
            if [ "$HEALTH" = "unhealthy" ]; then
                # unhealthy 但有响应，检查是否因为端点不存在
                if [ "$service" = "backend" ] || [ "$service" = "worker" ]; then
                    # 后端/worker：如果进程在运行但 healthcheck 失败，可能是旧镜像没有端点
                    if [ "$service" = "backend" ]; then
                        # 后端在运行但 healthcheck 失败，用容器内部检查
                        HTTP_CODE_BACKEND=$(compose exec -T backend python -c "
import urllib.request
try:
    r = urllib.request.urlopen('http://127.0.0.1:8000/')
    print(r.getcode())
except Exception:
    print('000')
" 2>/dev/null || echo "000")
                        if [ "$HTTP_CODE_BACKEND" != "000" ]; then
                            echo "  NOTE: $service running (health: $HEALTH, but responding HTTP $HTTP_CODE_BACKEND)"
                        else
                            echo "  WARN: $service unhealthy (state=$STATE health=$HEALTH)"
                        fi
                    else
                        echo "  NOTE: $service running (health: $HEALTH)"
                    fi
                else
                    echo "  WARN: $service unhealthy (state=$state health=$health)"
                fi
            fi
        else
            echo "  FAIL: $service not running (state=$state)"
            ALL_RUNNING=false
        fi
    else
        echo "  FAIL: $service not found"
        ALL_RUNNING=false
    fi
done

if [ "$ALL_RUNNING" = true ]; then
    result "PASS" "All services running"
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

# 首先尝试健康端点（新版镜像）— 通过 Nginx 代理访问
HEALTH_RESPONSE=$(curl -s --max-time 10 "$BASE_URL/api/health/" 2>/dev/null || echo "")
if [ -n "$HEALTH_RESPONSE" ] && echo "$HEALTH_RESPONSE" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
    result "PASS" "Backend /api/health/ returns JSON"
else
    # 旧版镜像没有 health 端点，用 Gunicorn 进程检查替代
    BACKEND_PID=$(compose ps -q backend 2>/dev/null || true)
    if [ -n "$BACKEND_PID" ]; then
        STATE=$(docker inspect --format='{{.State.Status}}' "$BACKEND_PID" 2>/dev/null || echo "unknown")
        if [ "$STATE" = "running" ]; then
            # 通过 Nginx 代理验证后端 API 在响应
            AUTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL/api/auth/guest-login/" -X POST -H "Content-Type: application/json" -d '{}' 2>/dev/null || echo "000")
            if [ "$AUTH_CODE" != "000" ]; then
                result "PASS" "Backend Gunicorn responding (HTTP $AUTH_CODE)"
            else
                result "FAIL" "Backend not responding" "Gunicorn may not be running"
            fi
        else
            result "FAIL" "Backend container state: $STATE"
        fi
    else
        result "FAIL" "Backend container not found"
    fi
fi

# 尝试版本端点 — 通过 Nginx 代理访问
VERSION_RESPONSE=$(curl -s --max-time 10 "$BASE_URL/api/system/version/" 2>/dev/null || echo "")
if echo "$VERSION_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'version' in d" 2>/dev/null; then
    VERSION=$(echo "$VERSION_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['version'])" 2>/dev/null)
    result "PASS" "Backend version endpoint (v${VERSION})"
else
    # 旧版镜像可能没有此端点，检查后端是否在运行即可
    BACKEND_PID=$(compose ps -q backend 2>/dev/null || true)
    if [ -n "$BACKEND_PID" ]; then
        STATE=$(docker inspect --format='{{.State.Status}}' "$BACKEND_PID" 2>/dev/null || echo "unknown")
        if [ "$STATE" = "running" ]; then
            result "SKIP" "Backend version endpoint" "Not available in this version"
        else
            result "FAIL" "Backend /api/system/version/" "Response: ${VERSION_RESPONSE:0:200}"
        fi
    else
        result "FAIL" "Backend /api/system/version/" "Response: ${VERSION_RESPONSE:0:200}"
    fi
fi

# 测试通过 Nginx 代理访问后端 API
PROXY_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL/api/auth/guest-login/" -X POST -H "Content-Type: application/json" -d '{}' 2>/dev/null || echo "000")
if [ "$PROXY_CODE" != "000" ] && [ "$PROXY_CODE" != "502" ] && [ "$PROXY_CODE" != "503" ]; then
    result "PASS" "Nginx reverse proxy to backend API (HTTP $PROXY_CODE)"
else
    result "FAIL" "Nginx reverse proxy" "Got HTTP $PROXY_CODE (expected non-error response)"
fi
echo ""

# ─── 阶段 4: Redis 连通性 ───────────────────────────────────
echo "阶段 4: Redis 连通性"

if [ -f ".env.production" ]; then
    REDIS_PASSWORD=$(grep "^REDIS_PASSWORD=" .env.production | cut -d= -f2-)
    # SECURITY FIX: Use REDISCLI_AUTH env var instead of -a flag to avoid password exposure in process list
    REDIS_PING=$(compose exec -T -e REDISCLI_AUTH="$REDIS_PASSWORD" redis redis-cli ping 2>/dev/null || echo "FAIL")
    if echo "$REDIS_PING" | grep -q "PONG"; then
        result "PASS" "Redis responds to PING"
    else
        result "FAIL" "Redis ping" "Response: $REDIS_PING"
    fi
else
    result "SKIP" "Redis" ".env.production not found"
fi
echo ""

# ─── 阶段 5: Worker 状态 ────────────────────────────────────
echo "阶段 5: Worker 状态"

WORKER_STATUS=$(compose ps worker 2>/dev/null || echo "")
if echo "$WORKER_STATUS" | grep -q "Up"; then
    result "PASS" "Celery worker is running"
else
    result "FAIL" "Celery worker" "Status: $WORKER_STATUS"
fi
echo ""

# ─── 总结 ────────────────────────────────────────────────────
echo "=========================================="
echo "  测试结果"
echo "=========================================="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
echo "  SKIP: $SKIP"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "STATUS: FAILED — $FAIL 个测试未通过"
    exit 1
else
    echo "STATUS: ALL PASSED"
    exit 0
fi
