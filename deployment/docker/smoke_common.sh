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
    printf '/tmp/omnidesk-smoke-%s-%s' "${SMOKE_RUN_ID:-norunid}" "$1"
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
    # 保留共享锁文件 inode；删除会在解锁与 rm 之间制造并发绕过窗口。
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

# ─── 认证 Token(同 run 缓存一次) ────────────────────────────
smoke_auth_token_file() {
    printf '%s' "${SMOKE_AUTH_TOKEN_FILE:-/tmp/.smoke_auth_token-${SMOKE_RUN_ID:-$$}}"
}

# 从 stdin/受限文件读取 token，避免 token 出现在 argv 或环境变量。
smoke_auth_token_is_valid() {
    python3 -c '
import base64, binascii, json, math, sys, time

def decode_segment(segment):
    if not segment or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in segment):
        raise ValueError
    if "=" in segment or len(segment) % 4 == 1:
        raise ValueError
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))

try:
    parts = sys.stdin.read().split(".")
    if len(parts) != 3 or not all(parts):
        raise ValueError
    header = json.loads(decode_segment(parts[0]).decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise ValueError
    claims = json.loads(decode_segment(parts[1]).decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    if not isinstance(claims, dict):
        raise ValueError
    exp = claims.get("exp")
    if isinstance(exp, bool) or not isinstance(exp, (int, float)) or not math.isfinite(exp) or exp <= time.time():
        raise ValueError
except (binascii.Error, UnicodeError, json.JSONDecodeError, TypeError, ValueError, OverflowError):
    raise SystemExit(1)
'
}

# 为带认证的 curl 创建 0600 header 文件；调用方只传文件名给 curl。
smoke_auth_header_file() {
    local token_file="$1" header_file token
    header_file="$(mktemp "$(smoke_temp_file 'auth-header').XXXXXX")" || return 1
    token="$(cat "$token_file")" || { rm -f -- "$header_file"; return 1; }
    (umask 077; chmod 600 "$header_file" && {
        printf '%s' "$token" | smoke_auth_token_is_valid || return 1
        printf 'Authorization: Bearer %s\n' "$token" > "$header_file"
    }) || { rm -f -- "$header_file"; return 1; }
    record_smoke_resource auth-header "auth-header-$$-$RANDOM" "$header_file" || { rm -f -- "$header_file"; return 1; }
    printf '%s' "$header_file"
}

smoke_store_auth_token() {
    local token_file="$1" token="$2" token_dir tmp_file
    token_dir="$(dirname -- "$token_file")"
    [ -d "$token_dir" ] || return 1
    if [ -e "$token_file" ] || [ -L "$token_file" ]; then
        return 1
    fi
    tmp_file="$(mktemp "$token_dir/.smoke-token.XXXXXX")" || return 1
    if ! (umask 077; chmod 600 "$tmp_file" && printf '%s' "$token" > "$tmp_file"); then
        rm -f -- "$tmp_file"
        return 1
    fi
    if ! mv -- "$tmp_file" "$token_file"; then
        rm -f -- "$tmp_file"
        return 1
    fi
    chmod 600 "$token_file" || { rm -f -- "$token_file"; return 1; }
}

obtain_auth_token() {
    local token_file token_dir cached
    token_file="$(smoke_auth_token_file)"; token_dir="$(dirname -- "$token_file")"
    [ -d "$token_dir" ] || mkdir -p "$token_dir" || return 1
    if [ -e "$token_file" ] || [ -L "$token_file" ]; then
        local mode owner uid
        mode="$(stat -c '%a' -- "$token_file" 2>/dev/null || :)"; owner="$(stat -c '%u' -- "$token_file" 2>/dev/null || :)"; uid="$(id -u)"
        if [ -f "$token_file" ] && [ ! -L "$token_file" ] && [ "$owner" = "$uid" ] && [ "$mode" = 600 ]; then
            cached="$(cat -- "$token_file" 2>/dev/null || :)"
            if printf '%s' "$cached" | smoke_auth_token_is_valid; then printf '%s' "$cached"; return 0; fi
        fi
        rm -f -- "$token_file" || return 1
    fi
    (
        set -e
        local body_file="" request_file="" user_file="" password_file="" tmp_cache="" code login_url token
        trap 'rm -f -- "${body_file:-}" "${request_file:-}" "${user_file:-}" "${password_file:-}" "${tmp_cache:-}"' EXIT HUP INT TERM
        body_file="$(mktemp "$token_dir/.smoke-body.XXXXXX")"
        request_file="$(mktemp "$token_dir/.smoke-request.XXXXXX")"
        user_file="$(mktemp "$token_dir/.smoke-user.XXXXXX")"
        password_file="$(mktemp "$token_dir/.smoke-password.XXXXXX")"
        chmod 600 "$body_file" "$request_file" "$user_file" "$password_file"
        login_url="$BASE_URL/api/auth/guest-login/"
        if [ -n "${SMOKE_TEST_USER:-}" ] && [ -n "${SMOKE_TEST_PASSWORD:-}" ]; then
            login_url="$BASE_URL/api/auth/login/"
            printf '%s' "$SMOKE_TEST_USER" >"$user_file"
            printf '%s' "$SMOKE_TEST_PASSWORD" >"$password_file"
            python3 - "$user_file" "$password_file" "$request_file" <<'PYJSON'
import json, sys
with open(sys.argv[1]) as user_file, open(sys.argv[2]) as password_file, open(sys.argv[3], 'w') as request_file:
    json.dump({'username': user_file.read(), 'password': password_file.read()}, request_file)
PYJSON
        else
            printf '{}' >"$request_file"
        fi
        code="$(curl -sS -X POST -o "$body_file" --write-out '%{http_code}' --max-time "${SMOKE_CURL_TIMEOUT:-15}" -H 'Content-Type: application/json' --data-binary "@$request_file" "$login_url" 2>/dev/null || printf '000')"
        [ "$code" = 200 ] || exit 1
        token="$(python3 -c 'import json,sys;
try:
 d=json.load(open(sys.argv[1])); print(d.get("access","") if isinstance(d,dict) else "")
except (OSError,TypeError,ValueError,json.JSONDecodeError): pass' "$body_file")"
        printf '%s' "$token" | smoke_auth_token_is_valid
        smoke_store_auth_token "$token_file" "$token"
        printf '%s' "$token"
    )
}

# ─── Smoke 资源追踪(按 run-id 隔离) ─────────────────────────
# record_smoke_resource <kind> <id> <path>
#   向 $(smoke_temp_file resources) 追加一行:`<SMOKE_RUN_ID>\t<kind>\t<id>\t<path>`
#   后续 cleanup_smoke_artifacts 仅删 SMOKE_RUN_ID 匹配的行。
record_smoke_resource() {
    local kind="${1:-file}" id="${2:-$RANDOM}" path="${3:-}"
    [ -z "$path" ] && return 1
    local res_file
    res_file="$(smoke_temp_file resources)"
    printf '%s\t%s\t%s\t%s\n' "$SMOKE_RUN_ID" "$kind" "$id" "$path" >> "$res_file"
}

# cleanup_smoke_artifacts
#   读取 $(smoke_temp_file resources),仅删除 run-id == SMOKE_RUN_ID 的资源。
#   任何删除失败累计到返回值(成功=0,失败次数=exit code)。
#   无 resources 文件视为 0(幂等)。
cleanup_smoke_artifacts() {
    local res_file
    res_file="$(smoke_temp_file resources)"
    if [ ! -f "$res_file" ]; then
        return 0
    fi
    local failures=0 run_id kind id path
    while IFS=$'\t' read -r run_id kind id path; do
        [ -z "$run_id" ] && continue
        [ "$run_id" = "$SMOKE_RUN_ID" ] || continue
        if [ -e "$path" ]; then
            rm -f "$path" 2>/dev/null || failures=$((failures + 1))
        fi
    done < "$res_file"
    rm -f -- "$res_file" 2>/dev/null || failures=$((failures + 1))
    return "$failures"
}

# ─── finalize_results ────────────────────────────────
finalize_results() {
    if [ "${SMOKE_STRICT:-0}" = "1" ] && { [ "$WARN" -gt 0 ] || [ "$SKIP" -gt 0 ]; }; then
        echo "ERROR: SMOKE_STRICT=1 模式存在 WARN/SKIP (WARN=$WARN SKIP=$SKIP),拒绝通过" >&2
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

# ─── 协议层辅助函数(纯函数,从 inputs 推 contract) ─────────
# check_version_endpoint <http_code> <body_file> <expected_version> <expected_channel>
#   解析 body JSON,对 version+channel 严格匹配。
#   不一致 → FAIL;HTTP 非 200 → FAIL;body 字段缺失 → FAIL。
check_version_endpoint() {
    local code="$1" body_file="$2" expected_version="$3" expected_channel="$4"
    if [ "$code" != "200" ]; then
        result FAIL "version endpoint" "HTTP $code (expected 200)"
        return 1
    fi
    if [ ! -f "$body_file" ]; then
        result FAIL "version endpoint" "body file missing: $body_file"
        return 1
    fi
    local actual_version actual_channel
    actual_version="$(python3 -c "import sys,json; print(json.load(open(sys.argv[1])).get('version',''))" "$body_file" 2>/dev/null || echo "")"
    actual_channel="$(python3 -c "import sys,json; print(json.load(open(sys.argv[1])).get('channel',''))" "$body_file" 2>/dev/null || echo "")"
    if [ -z "$actual_version" ] || [ -z "$actual_channel" ]; then
        result FAIL "version endpoint" "missing version/channel field"
        return 1
    fi
    if [ "$actual_version" != "$expected_version" ]; then
        result FAIL "version mismatch" "expected=$expected_version actual=$actual_version"
        return 1
    fi
    if [ "$actual_channel" != "$expected_channel" ]; then
        result FAIL "channel mismatch" "expected=$expected_channel actual=$actual_channel"
        return 1
    fi
    result PASS "version+channel match" "v${actual_version}-${actual_channel}"
    return 0
}

# check_cors_preflight <http_code> <headers_file> <origin> <method> <request_headers_csv>
#   合法 origin(白名单来源 CORS_ALLOWED_ORIGINS,默认 "http://localhost:3000"):
#     必须 2xx + Access-Control-Allow-Origin + Allow-Methods + Allow-Headers,且 Allow-Headers
#     涵盖请求头(逗号分隔)。
#   非法 origin:不得被反射 Access-Control-Allow-Origin,2xx 但无 ACAO 即视为被拒;4xx 也视为被拒。
check_cors_preflight() {
    local code="$1" headers_file="$2" origin="$3" method="$4" request_headers="$5"
    local allowed_origins="${CORS_ALLOWED_ORIGINS:-http://localhost:3000}"
    local is_legal=false
    if [[ " ${allowed_origins} " == *" ${origin} "* ]]; then
        is_legal=true
    fi
    local allow_origin_line allow_methods_line allow_headers_line
    allow_origin_line="$(grep -i '^Access-Control-Allow-Origin:' "$headers_file" 2>/dev/null | head -1 | sed 's/^[A-Za-z-]*:[[:space:]]*//' | tr -d '\r' || echo "")"
    allow_methods_line="$(grep -i '^Access-Control-Allow-Methods:' "$headers_file" 2>/dev/null | head -1 | sed 's/^[A-Za-z-]*:[[:space:]]*//' | tr -d '\r' || echo "")"
    allow_headers_line="$(grep -i '^Access-Control-Allow-Headers:' "$headers_file" 2>/dev/null | head -1 | sed 's/^[A-Za-z-]*:[[:space:]]*//' | tr -d '\r' || echo "")"

    if [ "$is_legal" = false ]; then
        # 非法 origin:不得被反射 ACAO
        if [ -n "$allow_origin_line" ] && [ "$allow_origin_line" != "null" ]; then
            result FAIL "CORS reflection of illegal origin" "ACAO='$allow_origin_line' for $origin"
            return 1
        fi
        result PASS "CORS rejects illegal origin" "$origin"
        return 0
    fi

    # 合法 origin:必须 2xx
    case "$code" in
        2??) ;;
        *) result FAIL "CORS preflight" "HTTP $code (expected 2xx) for $origin"; return 1 ;;
    esac
    [ -n "$allow_origin_line" ] || { result FAIL "CORS preflight missing ACAO" "$origin"; return 1; }
    [ "$allow_origin_line" = "$origin" ] || { result FAIL "CORS Allow-Origin mismatch" "expected='$origin' actual='$allow_origin_line'"; return 1; }
    [ "$allow_origin_line" != "*" ] || { result FAIL "CORS wildcard origin forbidden" "$origin"; return 1; }
    [ -n "$allow_methods_line" ] || { result FAIL "CORS preflight missing Allow-Methods"; return 1; }
    [ -n "$allow_headers_line" ] || { result FAIL "CORS preflight missing Allow-Headers"; return 1; }
    # 校验请求头是否被允许(去除所有空格避免 ", Authorization" 与 ",Authorization," 失配)
    local missing=""
    local normalized_headers
    normalized_headers="$(echo "$allow_headers_line" | tr -d ' ')"
    IFS=',' read -ra REQ <<< "$request_headers"
    for h in "${REQ[@]}"; do
        h="$(echo "$h" | tr -d ' ')"
        [ -z "$h" ] && continue
        if ! echo ",$normalized_headers," | grep -qi ",$h,"; then
            missing="$missing $h"
        fi
    done
    if [ -n "$missing" ]; then
        result FAIL "CORS Allow-Headers missing" "$missing"
        return 1
    fi
    result PASS "CORS preflight" "origin=$origin method=$method"
    return 0
}

# check_optional_ragflow <enabled> <mysql_state,health> <ragflow_state,health>
#   enabled == "disabled" → SKIP(不得 PASS);
#   enabled == "enabled"  → 两服务(state=running & health=healthy) 必须 PASS;
#   任一服务未达要求 → FAIL。
check_optional_ragflow() {
    local enabled="$1" mysql_state_health="$2" ragflow_state_health="$3"
    if [ "$enabled" = "disabled" ]; then
        result SKIP "RAGFlow optional service disabled"
        return 0
    fi
    local mysql_state="${mysql_state_health%%,*}"
    local mysql_health="${mysql_state_health##*,}"
    local ragflow_state="${ragflow_state_health%%,*}"
    local ragflow_health="${ragflow_state_health##*,}"
    if [ "$mysql_state" != "running" ] || [ "$mysql_health" != "healthy" ]; then
        result FAIL "ragflow-mysql" "state=$mysql_state health=$mysql_health"
        return 1
    fi
    if [ "$ragflow_state" != "running" ] || [ "$ragflow_health" != "healthy" ]; then
        result FAIL "ragflow" "state=$ragflow_state health=$ragflow_health"
        return 1
    fi
    result PASS "RAGFlow services healthy"
    return 0
}

# check_lazy_routes <manifest_json_file>
#   manifest 形如 { "routes": [{"path":"/x","asset":"/static/x.js"}, ...] }
#   逐个请求 <BASE_URL><asset>,2xx 视为 PASS,否则 FAIL。
#   走 request_with_status 复用以尊重 SMOKE_ALLOW_NETWORK_SKIP 等策略。
check_lazy_routes() {
    local manifest="$1"
    if [ ! -f "$manifest" ]; then
        result FAIL "lazy routes manifest missing" "$manifest"
        return 1
    fi
    local base="${BASE_URL:-http://localhost}"
    local total=0 failures=0
    while IFS=$'\t' read -r route asset; do
        [ -z "$asset" ] && continue
        total=$((total + 1))
        local url="${base}${asset}"
        local body code
        body="$(smoke_temp_file lazy-route-body)"
        code=$(request_with_status GET "$url" "$body")
        if [ "$code" = "200" ]; then
            result PASS "lazy route asset" "$route -> $asset (HTTP 200)"
        else
            result FAIL "lazy route asset" "$route -> $asset (HTTP $code)"
            failures=$((failures + 1))
        fi
    done < <(python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as f:
        d = json.load(f)
    for r in d.get('routes', []):
        a = r.get('asset', '')
        if a:
            print(f\"{r.get('path','')}\t{a}\")
except Exception:
    pass
" "$manifest")
    return "$failures"
}
