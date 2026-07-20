#!/bin/bash

# smoke_tests.sh — 部署后冒烟测试
# 使用方法: ./smoke_tests.sh [base_url]
# 默认测试 http://localhost
# 所有 API 请求通过 Nginx 代理 ($base_url/api/) 访问后端
#
# ─── 前置条件 ──────────────────────────────────────────────────
#   - 必须在 deployment/docker/ 目录下运行(或其 cp/ln 副本)
#     否则本脚本的 compose project name ("docker") 与运行中的 compose 不匹配
#     (见 O4: 显式 COMPOSE_PROJECT_NAME)
#   - .env.production 必须存在且填充占位符 (POSTGRES_USER 不含 <...>)
#   - docker compose 插件可用; 当前用户能进 docker 组
#   - BASE_URL 应指向前端 (默认 http://localhost); 后端 API 走 Nginx 反代 /api/
#
# ─── 副作用 (Operator 必读) ───────────────────────────────────
#   - 阶段 8 会触发 backend / db 容器重启 — 生产窗口 30-90s 服务不可用
#   - 阶段 8 会创建 backend:/usr/src/app/media/_smoke_marker 文件 (trap 退出清理)
#   - 阶段 8 会在 postgres:_smoke_persist 表插一行 (trap 退出 DROP)
#   - /tmp/.smoke_guest_<pid>.json 含 JWT token (脚本结束清理,umask 077 仅 owner 可读)
#
# ─── 已知陷阱 ──────────────────────────────────────────────────
#   - HTTPS 部署: BASE_URL=https://... 时 curl 没 -k 会让所有 API 全 000 → 全 SKIP
#   - DRF throttle: 5/15m 限流 — 同机 15 分钟内第二次跑阶段 6 会拿 429 WARN
#   - 同一 box 多 compose 项目: 必须确保 pwd basename 与运行中项目一致
#     (推荐设置 COMPOSE_PROJECT_NAME 环境变量显式覆盖)

COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$COMPOSE_DIR" || exit 1

# O4: 显式锁定 compose project name — 默认 "docker" 与 deployment 目录 basename 一致
#     (deploy_offline.sh / upgrade.sh / rollback.sh 等共用此约定)
#     可以通过环境变量覆盖:  COMPOSE_PROJECT_NAME=mystack ./smoke_tests.sh
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-docker}"

BASE_URL="${1:-http://localhost}"
# backend 不再暴露 8000 端口，所有 API 请求通过 Nginx 代理走 $BASE_URL
# 非 API 端点（如 /admin/）通过 docker compose exec 直接访问容器

PASS=0
FAIL=0
SKIP=0
WARN=0
# O1: WARN 详情数组 — STATUS 框前 echo,让 operator 不用 grep 翻日志
WARN_DETAILS=()

# 不加 -e:result() 自控制流程,需要宽容失败
set -uo pipefail

# 退出兜底:阶段 8 marker 文件 / 测试表若中途崩溃,自动清理避免污染生产卷
# 注意:trap 内不要再调用 exit 防止 trap 重入
# B1: db exec 加 timeout 30 防止 db restarting 状态挂死
# B·E1: backend rm 也加 timeout 10 — 对称补漏,防 trap 期间 backend 处于 restart/starting 时 exec 挂死
# B·G: db cleanup 重试 3 次防 _smoke_persist 表永久残留
cleanup_smoke_artifacts() {
    [ -n "${MARKER_FILE:-}" ] && timeout 10 compose exec -T backend rm -f "$MARKER_FILE" 2>/dev/null || true
    if [ -n "${POSTGRES_USER:-}" ] && [ -n "${POSTGRES_DB:-}" ]; then
        for _attempt in 1 2 3; do
            timeout 20 compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
                "DROP TABLE IF EXISTS _smoke_persist;" >/dev/null 2>&1 && break
            sleep 2
        done
    fi
    # S5: GUEST_JSON 在阶段 6 末尾会 unset,这里用 ${VAR:-} 兼容已 unset 的情况
    #   (单 trap 不可叠加,合并到此函数避免覆盖原 trap)
    [ -n "${GUEST_JSON:-}" ] && rm -f "$GUEST_JSON" 2>/dev/null || true
}
trap cleanup_smoke_artifacts EXIT

result() {
    local status="$1"
    local msg="$2"
    local detail="${3:-}"
    case "$status" in
        PASS) echo "  PASS: $msg"; PASS=$((PASS + 1)) ;;
        FAIL) echo "  FAIL: $msg"; FAIL=$((FAIL + 1)); [ -n "$detail" ] && echo "    -> $detail" ;;
        SKIP) echo "  SKIP: $msg"; SKIP=$((SKIP + 1)) ;;
        # O1: WARN 详情也收集到 WARN_DETAILS,STATUS 框前 echo
        WARN) echo "  WARN: $msg"; WARN=$((WARN + 1))
              [ -n "$detail" ] && echo "    -> $detail"
              WARN_DETAILS+=("$msg${detail:+ — $detail}")
              ;;
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
    docker compose -p "$COMPOSE_PROJECT_NAME" $COMPOSE_FILE $ENV_FILE "$@"
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
                    echo "  WARN: $service unhealthy (state=$STATE health=$HEALTH)"
                fi
            fi
        else
            echo "  FAIL: $service not running (state=$STATE)"
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
if [ "$PROXY_CODE" != "000" ] && [ "$PROXY_CODE" != "502" ] && [ "$PROXY_CODE" != "503" ] && [ "$PROXY_CODE" != "504" ]; then
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

# ─── 阶段 6: 版本/迁移/CHANGELOG 端点 (需 JWT) ─────────────────
echo "阶段 6: 版本/迁移/CHANGELOG 端点"

# 阶段 6 头部抓 JWT — 区分 5/15m 限流 (H1)
# 阶段 6 头部抓 JWT — 区分 5/15m 限流 (H1) + 真业务错误不应 SKIP (C·新发现 1)
# C·新发现 2: 用 PID 后缀隔离并发 run 时的 json 文件
# S5: JWT 文件默认仅 owner 可读;清理合并到主 cleanup_smoke_artifacts trap
#   (因为 bash EXIT trap 是单值,不能与已有 trap 叠加,见 trap 函数实现)
GUEST_JSON="/tmp/.smoke_guest_$$.json"
(umask 077; : > "$GUEST_JSON")  # S5: 设 restrictive 权限
GUEST_HTTP=$(curl -s -o "$GUEST_JSON" -w "%{http_code}" --max-time 10 \
    -X POST -H "Content-Type: application/json" -d '{}' \
    "$BASE_URL/api/auth/guest-login/" 2>/dev/null || echo "000")

case "$GUEST_HTTP" in
    200)
        GUEST_TOKEN=$(python3 -c "import json; print(json.load(open('$GUEST_JSON')).get('access',''))" 2>/dev/null || echo "")
        ;;
    429)
        result "WARN" "Guest login rate-limited (HTTP 429)" "5/15m 已耗尽,跳过阶段 6;可 15 分钟后重试"
        GUEST_TOKEN=""
        ;;
    # 真业务错误(token 失效/被禁/IP 黑名单/后端崩溃):FAIL 让 CI gate 看见
    400|401|403|500)
        result "FAIL" "Guest login 真业务错误" "HTTP $GUEST_HTTP — 服务可能配置错/后端崩溃,不能 SKIP"
        GUEST_TOKEN=""
        ;;
    # B·D: 路由配置错误 / 服务器资源拒绝 — guest-login 是已知 POST 端点,
    #   405/451 = API 签名错或合规拒绝;506/507 = 服务器资源/版本错
    405|451)
        result "FAIL" "Guest login 路由配置错误" "HTTP $GUEST_HTTP — 端点签名错/合规拒绝,不能 SKIP"
        GUEST_TOKEN=""
        ;;
    506|507)
        result "FAIL" "Guest login 服务器资源异常" "HTTP $GUEST_HTTP — 服务器资源/版本不支持,不能 SKIP"
        GUEST_TOKEN=""
        ;;
    # 网络瞬态 / nginx 上游挂:保守 SKIP
    000|502|503|504)
        result "SKIP" "Migrations/Changelog endpoints" "Guest login HTTP $GUEST_HTTP (网络瞬态)"
        GUEST_TOKEN=""
        ;;
    *)
        # K2 设计意图:未知 HTTP 码保守 SKIP — 新版本后端可能新增业务错误码,
        #  在 CI 上不阻塞,但 STATUS 行通过 "skip count" 让值班能定位
        result "SKIP" "Migrations/Changelog endpoints" "Guest login HTTP $GUEST_HTTP (未知)"
        GUEST_TOKEN=""
        ;;
esac
# 清理临时 json (即便 set -u 下变量未用)
[ -f "$GUEST_JSON" ] && rm -f "$GUEST_JSON" 2>/dev/null || true
unset GUEST_JSON

if [ -z "$GUEST_TOKEN" ]; then
    # S4: 显式告知后续 6.1 / 6.2 也被跳过 — operator 看到 "FAIL + 2 SKIP" 而非 "FAIL" 单独一行
    #     才能区分"是 guest-login 单独坏"还是"全栈挂了"
    result "SKIP" "Migrations endpoint" "No JWT (guest-login HTTP ${GUEST_HTTP:-empty})"
    result "SKIP" "Changelog endpoint" "No JWT (guest-login HTTP ${GUEST_HTTP:-empty})"
else
    # 6.1 /api/system/migrations/
    MIG=$(curl -s --max-time 10 -H "Authorization: Bearer $GUEST_TOKEN" \
        "$BASE_URL/api/system/migrations/" 2>/dev/null || echo "")
    if echo "$MIG" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert 'has_destructive' in d
assert 'applied_count' in d
assert 'pending_count' in d
" 2>/dev/null; then
        APPLIED=$(echo "$MIG" | python3 -c "import sys,json; print(json.load(sys.stdin)['applied_count'])")
        PENDING=$(echo "$MIG" | python3 -c "import sys,json; print(json.load(sys.stdin)['pending_count'])")
        # destructive 比较 (M5) — case 大小写安全
        DESTRUCTIVE=$(echo "$MIG" | python3 -c "import sys,json; print(json.load(sys.stdin)['has_destructive'])")
        result "PASS" "Migrations endpoint (applied=$APPLIED pending=$PENDING destructive=$DESTRUCTIVE)"
        case "$DESTRUCTIVE" in
            [Tt]rue|1)
                # destructive op 列表 (L4) — 提示具体哪些类型
                DESTRUCTIVE_OPS=$(echo "$MIG" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ops = [o for p in d.get('pending', []) for o in (p.get('operations') or []) if o.get('destructive')]
print(','.join(o['type'] + '(' + o.get('model', o.get('field','?')) + ')' for o in ops[:5]) or 'unknown')
" 2>/dev/null || echo "extraction_failed")
                result "WARN" "Pending migrations include destructive operations" "$DESTRUCTIVE_OPS"
                ;;
        esac
    else
        result "FAIL" "Migrations endpoint" "Response: ${MIG:0:200}"
    fi

    # 6.2 /api/system/changelog/
    # 端点合法返回两种:
    #   (A) 真实 CHANGELOG.md 内容 — 含 "## " 二级标题与 [vX.Y.Z] 顶层 version
    #   (B) 占位符 fallback — "# 更新日志\n\n暂无更新日志。"
    #       (当 backend 容器无法读到 deployment/docker/CHANGELOG.md 时触发,
    #        这是生产部署配置问题而非 smoke 失败,故 PASS + WARN)
    CHL=$(curl -s --max-time 10 -H "Authorization: Bearer $GUEST_TOKEN" \
        "$BASE_URL/api/system/changelog/" 2>/dev/null || echo "")
    if echo "$CHL" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert isinstance(d.get('changelog',''), str) and len(d['changelog']) > 0
" 2>/dev/null; then
        VER=$(echo "$CHL" | python3 -c "
import sys,json,re
t=json.load(sys.stdin)['changelog']
m=re.search(r'\[(v[0-9.]+[a-z0-9.-]*)\]', t)
print(m.group(1) if m else 'fallback')
" 2>/dev/null)
        result "PASS" "Changelog endpoint (latest=$VER)"
        if [ "$VER" = "fallback" ]; then
            result "WARN" "Changelog endpoint fallback" "生产部署可能未挂载 deployment/docker/CHANGELOG.md;详见 core/api.py:54"
        fi
    else
        result "FAIL" "Changelog endpoint" "Response: ${CHL:0:200}"
    fi
fi
echo ""

# ─── 阶段 7: 离线包元数据/可加载性校验 (validate_artifacts.sh) ──
echo "阶段 7: 离线包元数据/可加载性校验"

if [ -x "./validate_artifacts.sh" ]; then
    VA_OUTPUT=$(./validate_artifacts.sh exported_images/ 2>&1)
    VA_RC=$?
    if [ "$VA_RC" -eq 0 ]; then
        VA_PASS=$(echo "$VA_OUTPUT" | grep -c "PASS:")
        VA_FAIL=$(echo "$VA_OUTPUT" | grep -c "FAIL:")
        VA_WARN=$(echo "$VA_OUTPUT" | grep -c "WARN:")
        result "PASS" "Offline bundle integrity (validate_artifacts: pass=$VA_PASS fail=$VA_FAIL warn=$VA_WARN)"
    else
        result "FAIL" "Offline bundle integrity" "validate_artifacts.sh exit=$VA_RC. tail: $(echo "$VA_OUTPUT" | tail -10)"
    fi
else
    result "SKIP" "Offline bundle integrity" "validate_artifacts.sh not found/executable"
fi
echo ""

# ─── 阶段 8: 卷持久化测试 (重启后数据仍在) ─────────────────────
echo "阶段 8: 卷持久化测试"
# R2: 卷持久化是部署正确性的关键 — 如果卷未正确挂载,容器重启即丢数据。
#     测试两个最具代表性的卷:
#       8.1 backend media (Django FileField 默认落点,容器重启数据应仍在)
#       8.2 postgres data (关系数据,容器重启数据应仍在)
#     策略: write → restart → 等 health green → read → cleanup。
#     注: 容器重启期间服务不可用,生产窗口期 ~30-90s。

# 8.1 Backend media volume (最稳的卷测试 — 文件就在 volume)
MEDIA_MARKER="smoke_media_$$_$(date +%s)"
MARKER_FILE="/usr/src/app/media/_smoke_marker"
if compose exec -T backend sh -c "echo '$MEDIA_MARKER' > $MARKER_FILE" 2>/dev/null; then
    compose restart backend >/dev/null 2>&1 || true
    # H2: 不再固定 sleep — 等 backend HEALTHCHECK green 才动手,最多 60s
    BACKEND_ID=$(compose ps -q backend 2>/dev/null || true)
    for _ in $(seq 1 12); do  # 12 * 5s ≈ 60s
        HC="unknown"
        if [ -n "$BACKEND_ID" ]; then
            HC=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' \
                "$BACKEND_ID" 2>/dev/null || echo "unknown")
        fi
        [ "$HC" = "healthy" ] && break
        sleep 5
    done
    MEDIA_AFTER=$(compose exec -T backend cat "$MARKER_FILE" 2>/dev/null || echo "MISSING")
    if [ "$MEDIA_AFTER" = "$MEDIA_MARKER" ]; then
        result "PASS" "Backend media volume persists across restart"
    else
        # 健康但值不对 → 真的丢卷; 健康但仍未 ready → SKIP(避免误报)
        if [ "$HC" != "healthy" ]; then
            result "SKIP" "Backend media persist" "Backend 60s 内未恢复 healthy (hc=$HC),暂无法判定"
        else
            result "FAIL" "Backend media persist" "Got '$MEDIA_AFTER' (expected $MEDIA_MARKER)"
        fi
    fi
    # 注意:trap EXIT 也会清理 marker_file,这里显式 rm 是双保险
    # B·F: 主流程 marker 清理也加 timeout 10,与 trap 内 backend rm 对称
    timeout 10 compose exec -T backend rm -f "$MARKER_FILE" 2>/dev/null || true
else
    result "SKIP" "Backend media persist" "Cannot write to /usr/src/app/media/"
fi

# 8.2 Postgres data volume (用 INSERT + restart db)
if [ -f ".env.production" ]; then
    POSTGRES_USER=$(grep "^POSTGRES_USER=" .env.production | cut -d= -f2-)
    POSTGRES_DB=$(grep "^POSTGRES_DB=" .env.production | cut -d= -f2-)
    if [ -n "$POSTGRES_USER" ] && [ -n "$POSTGRES_DB" ]; then
        # I 安全注释: PG_MARKER_VAL 仅含 PID + unix_ts + 下划线,无 SQL 注入风险。
        #   若改值规则(如追加 user input),须保证仅含 [A-Za-z0-9_],否则需 quote 转义
        PG_MARKER_VAL="smoke_pg_$$_$(date +%s)"
        # M3: 捕获 PSQL 输出,失败时区分建表失败 vs 重启后卷丢
        PSQL_OUT=$(compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c \
            "CREATE TABLE IF NOT EXISTS _smoke_persist (mark text); INSERT INTO _smoke_persist (mark) VALUES ('$PG_MARKER_VAL');" 2>&1) || true
        if ! echo "$PSQL_OUT" | grep -q "INSERT 0 1"; then
            result "FAIL" "Postgres persist" "CREATE+INSERT 失败: ${PSQL_OUT:0:200}"
        else
            compose restart db >/dev/null 2>&1 || true
            # H3: 18 * 5s = 90s,覆盖 db.start_period 60s + retries 5s/次
            for _ in $(seq 1 18); do
                if compose exec -T db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then break; fi
                sleep 5
            done
            if ! compose exec -T db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
                # 卷可能 OK,但 db 还在启动,SKIP 而非 FAIL (避免冷启动误报)
                result "SKIP" "Postgres persist" "pg_isready 90s 内未就绪;卷可能 OK 但 db 还在启动"
            else
                PG_AFTER=$(compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
                    "SELECT mark FROM _smoke_persist WHERE mark='$PG_MARKER_VAL';" 2>/dev/null | tr -d ' \r\n' || echo "")
                if [ "$PG_AFTER" = "$PG_MARKER_VAL" ]; then
                    result "PASS" "Postgres data persists across restart"
                else
                    result "FAIL" "Postgres persist" "重启后 SELECT 返回 '$PG_AFTER' (卷可能丢失)"
                fi
            fi
        fi
    else
        result "SKIP" "Postgres persist" "POSTGRES_USER/POSTGRES_DB not set in .env.production"
    fi
else
    result "SKIP" "Postgres persist" ".env.production not found"
fi
echo ""

# ─── 总结 ────────────────────────────────────────────────────
echo "=========================================="
echo "  测试结果"
echo "=========================================="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
echo "  SKIP: $SKIP"
echo "  WARN: $WARN"
echo ""
# O1: WARN 必读摘要 — 不用 grep 翻日志就能定位
if [ "$WARN" -gt 0 ]; then
    echo "  ⚠ WARN 详情(请逐条 review):"
    for wd in "${WARN_DETAILS[@]}"; do
        echo "    - $wd"
    done
fi
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "STATUS: FAILED — $FAIL fail, $WARN warn, $SKIP skip"
    exit 1
elif [ "$WARN" -gt 0 ] || [ "$SKIP" -gt 0 ]; then
    echo "STATUS: PASSED WITH WARNINGS — $WARN warn, $SKIP skip (review required)"
    exit 0
else
    echo "STATUS: ALL PASSED"
    exit 0
fi
