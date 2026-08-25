#!/usr/bin/env bash
# smoke_common.sh — 部署测试共享上下文
# 提供:init_smoke_context / compose / smoke_temp_file / acquire_smoke_lock /
#       release_smoke_lock / resolve_artifact_dir / result / finalize_results
# 路径不依赖 cwd,通过 SMOKE_SCRIPT_DIR 显式定位。
# 不 source .env.production 内容(只解析特定 key),避免任意 env 被当 shell 执行。

# ─── Result 计数 ──────────────────────────────────────
: "${SMOKE_PASS:=0}"
: "${SMOKE_FAIL:=0}"
: "${SMOKE_WARN:=0}"
: "${SMOKE_SKIP:=0}"
PASS="$SMOKE_PASS"
FAIL="$SMOKE_FAIL"
WARN="$SMOKE_WARN"
SKIP="$SMOKE_SKIP"
WARN_DETAILS=()

result() {
    local status="$1"
    local msg="$2"
    local detail="${3:-}"
    case "$status" in
        PASS)
            echo "  PASS: $msg"
            PASS=$((PASS + 1))
            ;;
        FAIL)
            echo "  FAIL: $msg"
            [ -n "$detail" ] && echo "    -> $detail"
            FAIL=$((FAIL + 1))
            ;;
        WARN)
            echo "  WARN: $msg"
            [ -n "$detail" ] && echo "    -> $detail"
            WARN_DETAILS+=("$msg${detail:+ — $detail}")
            WARN=$((WARN + 1))
            ;;
        SKIP)
            if [ "${SMOKE_STRICT:-0}" = "1" ]; then
                echo "  FAIL(strict): $msg (was SKIP)"
                [ -n "$detail" ] && echo "    -> $detail"
                FAIL=$((FAIL + 1))
            else
                echo "  SKIP: $msg"
                SKIP=$((SKIP + 1))
            fi
            ;;
    esac
    export PASS FAIL WARN SKIP
}

# ─── 上下文解析 ──────────────────────────────────────
# init_smoke_context [base_url]
init_smoke_context() {
    BASE_URL="${1:-${SMOKE_BASE_URL:-http://localhost}}"
    # SMOKE_SCRIPT_DIR 优先(让测试可控),否则取当前 cwd(脚本必须 cd 到自身目录再 source)
    if [ -n "${SMOKE_SCRIPT_DIR:-}" ]; then
        SCRIPT_DIR="$SMOKE_SCRIPT_DIR"
    else
        SCRIPT_DIR="${SMOKE_SCRIPT_DIR_FALLBACK:-$PWD}"
    fi
    BUNDLE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    # 源码模式:compose 在 SCRIPT_DIR/docker-compose.offline.yml
    # bundle 模式:compose 在 SCRIPT_DIR/../compose/docker-compose.offline.yml
    if [ -f "$SCRIPT_DIR/docker-compose.offline.yml" ]; then
        COMPOSE_DIR="$SCRIPT_DIR"
    elif [ -f "$BUNDLE_DIR/compose/docker-compose.offline.yml" ]; then
        COMPOSE_DIR="$BUNDLE_DIR/compose"
    else
        echo "ERROR: compose file not found (looked in $SCRIPT_DIR and $BUNDLE_DIR/compose)" >&2
        return 1
    fi
    COMPOSE_FILE_PATH="${SMOKE_COMPOSE_FILE:-$COMPOSE_DIR/docker-compose.offline.yml}"
    ENV_FILE_PATH="${SMOKE_ENV_FILE:-$COMPOSE_DIR/.env.production}"

    if [ ! -f "$COMPOSE_FILE_PATH" ]; then
        echo "ERROR: compose file not found: $COMPOSE_FILE_PATH" >&2
        return 1
    fi
    if [ ! -f "$ENV_FILE_PATH" ]; then
        echo "ERROR: env file not found: $ENV_FILE_PATH" >&2
        return 1
    fi

    # 解析 COMPOSE_PROJECT_NAME(不 source env 文件)
    COMPOSE_PROJECT_NAME="${SMOKE_PROJECT_NAME:-}"
    if [ -z "$COMPOSE_PROJECT_NAME" ]; then
        COMPOSE_PROJECT_NAME="$(grep -E '^COMPOSE_PROJECT_NAME=' "$ENV_FILE_PATH" 2>/dev/null | head -1 | cut -d= -f2- || true)"
        COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME%%[$'\r\n ']*}"
    fi
    COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-omnidesk}"

    SMOKE_RUN_ID="${SMOKE_RUN_ID:-$(date -u +%s)-$$}"
    export BASE_URL SCRIPT_DIR BUNDLE_DIR COMPOSE_DIR COMPOSE_FILE_PATH ENV_FILE_PATH COMPOSE_PROJECT_NAME SMOKE_RUN_ID
}

# ─── Compose 调用包装 ─────────────────────────────────
compose() {
    docker compose -p "$COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE_PATH" --env-file "$ENV_FILE_PATH" "$@"
}

# ─── 临时文件 ──────────────────────────────────────────
smoke_temp_file() {
    printf '/tmp/omnidesk-smoke-%s-%s' "$SMOKE_RUN_ID" "$1"
}

# ─── 锁(同 project flock 互斥) ────────────────────────
SMOKE_LOCK_FD=""
SMOKE_LOCK_PATH=""

acquire_smoke_lock() {
    local lock_dir="${SMOKE_LOCK_DIR:-/tmp/omnidesk-smoke-locks}"
    mkdir -p "$lock_dir"
    SMOKE_LOCK_PATH="$lock_dir/${COMPOSE_PROJECT_NAME}.lock"
    exec 9>"$SMOKE_LOCK_PATH"
    if ! flock -n 9; then
        exec 9>&-
        echo "SKIP: smoke lock is held for $COMPOSE_PROJECT_NAME" >&2
        return 2
    fi
    SMOKE_LOCK_FD=9
    return 0
}

release_smoke_lock() {
    if [ -n "$SMOKE_LOCK_FD" ]; then
        flock -u "$SMOKE_LOCK_FD" 2>/dev/null || true
        eval "exec ${SMOKE_LOCK_FD}>&-" 2>/dev/null || true
    fi
    if [ -n "$SMOKE_LOCK_PATH" ] && [ "${SMOKE_LOCK_OWNED:-1}" = "1" ]; then
        rm -f "$SMOKE_LOCK_PATH" 2>/dev/null || true
    fi
    SMOKE_LOCK_FD=""
    SMOKE_LOCK_PATH=""
}

# ─── Artifact 目录解析 ────────────────────────────────
# resolve_artifact_dir [dir]: 显式 > bundle images/ > source exported_images/
resolve_artifact_dir() {
    local dir="${1:-}"
    if [ -n "$dir" ]; then
        if [ -d "$dir" ]; then
            printf '%s' "$dir"
            return 0
        fi
        echo "ERROR: artifact dir not found: $dir" >&2
        return 1
    fi
    local candidate
    for candidate in "$BUNDLE_DIR/images" "${SCRIPT_DIR:-$BUNDLE_DIR}/exported_images"; do
        if [ -d "$candidate" ]; then
            printf '%s' "$candidate"
            return 0
        fi
    done
    echo "ERROR: artifact dir not found (tried $BUNDLE_DIR/images and ${SCRIPT_DIR:-$BUNDLE_DIR}/exported_images)" >&2
    return 1
}

# ─── 服务健康检查(纯函数 + docker 包装) ──────────────────────
# 状态契约:
#   running + healthy       → PASS
#   running + unhealthy     → FAIL(required 与 optional 一视同仁)
#   starting                → FAIL
#   exited/created/restarting/absent → FAIL(可选服务 absent 才 SKIP)
# 不得出现 "running+unhealthy 视作 OK" 的分支。
#
# check_service_health_from_values <service> <state> <health> [required|optional]
check_service_health_from_values() {
    local service="$1" state="$2" health="$3" requirement="${4:-required}"
    if [ "$state" = "running" ] && [ "$health" = "healthy" ]; then
        result PASS "$service healthy"
        return 0
    fi
    # 可选服务只在 absent 时 SKIP;即便 optional,若 unhealthy 也必须 FAIL
    if [ "$requirement" = "optional" ] && [ "$state" = "absent" ]; then
        result SKIP "$service optional service disabled"
        return 0
    fi
    result FAIL "$service unhealthy" "state=$state health=$health requirement=$requirement"
    return 1
}

# check_service_health <service> [required|optional]
# 用 docker inspect 解析 STATE 与 health.Status,再委托给 from_values。
check_service_health() {
    local service="$1"
    local requirement="${2:-required}"
    local cid state health
    cid=$(compose ps -q "$service" 2>/dev/null || true)
    if [ -z "$cid" ]; then
        check_service_health_from_values "$service" absent absent "$requirement"
        return $?
    fi
    state=$(docker inspect --format='{{.State.Status}}' "$cid" 2>/dev/null || echo "unknown")
    health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || echo "unknown")
    # 没有 healthcheck 配置(none)=等同于 unhealthy,核心服务必须 FAIL
    if [ "$health" = "none" ] || [ "$health" = "" ]; then
        health="none"
    fi
    check_service_health_from_values "$service" "$state" "$health" "$requirement"
}

# ─── HTTP 请求辅助 ────────────────────────────────────
# request_with_status <method> <url> <body_file> [curl args...]
# 把响应体写入 body_file,stdout 输出数字 HTTP code。
# curl 网络错误 → 返回 "000";curl 进程失败码通过 $? 传递。
request_with_status() {
    local method="$1" url="$2" body_file="$3"
    shift 3
    local code
    code=$(curl -sS -X "$method" -o "$body_file" \
        --write-out '%{http_code}' \
        --max-time "${SMOKE_CURL_TIMEOUT:-15}" "$@" "$url" 2>/dev/null || echo "000")
    printf '%s' "$code"
}

# classify_http_status <code> <label>
# 判定并通过 result() 报告:
#   - 2xx                    → PASS
#   - 429 + ALLOW_RATE_LIMIT_SKIP=1 → WARN;否则 FAIL
#   - 000 + ALLOW_NETWORK_SKIP=1   → SKIP;否则 FAIL
#   - 其他 4xx/5xx/未知      → FAIL
# 在 SMOKE_STRICT=1 时,result() 内部已把 SKIP 升级为 FAIL。
classify_http_status() {
    local code="$1" label="$2"
    case "$code" in
        2??)
            result PASS "$label" "HTTP $code"
            return 0
            ;;
        429)
            if [ "${SMOKE_ALLOW_RATE_LIMIT_SKIP:-0}" = "1" ]; then
                result WARN "$label" "rate-limited HTTP $code (ALLOW_RATE_LIMIT_SKIP=1)"
                return 0
            fi
            result FAIL "$label" "rate-limited HTTP $code"
            return 1
            ;;
        000)
            if [ "${SMOKE_ALLOW_NETWORK_SKIP:-0}" = "1" ]; then
                result SKIP "$label" "network error (ALLOW_NETWORK_SKIP=1)"
                return 0
            fi
            result FAIL "$label" "network error / unreachable"
            return 1
            ;;
        *)
            result FAIL "$label" "HTTP $code"
            return 1
            ;;
    esac
}

# ─── finalize_results ────────────────────────────────
finalize_results() {
    if [ "${SMOKE_STRICT:-0}" = "1" ] && [ "$WARN" -gt 0 ]; then
        echo "ERROR: SMOKE_STRICT=1 模式有 $WARN 个 WARN,应改为 FAIL" >&2
        return 1
    fi
    echo ""
    echo "=========================================="
    echo "  Smoke Summary"
    echo "=========================================="
    echo "  PASS: $PASS"
    echo "  FAIL: $FAIL"
    echo "  SKIP: $SKIP"
    echo "  WARN: $WARN"
    [ "$FAIL" -gt 0 ] && return 1
    return 0
}
