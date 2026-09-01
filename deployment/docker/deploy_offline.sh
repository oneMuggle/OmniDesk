#!/bin/bash
set -e

# deploy_offline.sh — 离线部署管理脚本
# 使用方法: ./deploy_offline.sh {start|debug|stop|clean|restart|status|logs|exec|version|backup|upgrade|rollback|migrate|install-desktop}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 自动检测布局:源码树(扁平)vs 离线包(compose/ 子目录)
# brief 要求 bundle 内脚本通过 SCRIPT_DIR/../compose 定位 compose/env 文件
if [ -f "$SCRIPT_DIR/../compose/docker-compose.offline.yml" ]; then
    # 离线包布局
    cd "$SCRIPT_DIR/.."
    COMPOSE_FILE="-f compose/docker-compose.offline.yml"
    ENV_FILE="--env-file compose/.env.production"
else
    # 源码树布局
    cd "$SCRIPT_DIR"
    COMPOSE_FILE="-f docker-compose.offline.yml"
    ENV_FILE="--env-file .env.production"
fi

compose() {
    docker compose $COMPOSE_FILE $ENV_FILE "$@"
}

# ─── 升级状态机(Task 2 brief) ──────────────────────────────
# 升级状态模块(upgrade_state.sh)只在 upgrade/rollback 分支需要 —
# start/stop/status/logs/backup/migrate/install-desktop 等普通路径完全不引用,
# 若无条件 source 会浪费启动开销,且 bundle 中文件缺失时会让所有命令都 fail。
# 因此这里只设置默认 OMNIDESK_RUNTIME_ROOT;真正 source 推迟到 upgrade/rollback
# case(见下方)。
export OMNIDESK_RUNTIME_ROOT="${OMNIDESK_RUNTIME_ROOT:-/opt/omnidesk/runtime}"
SCRIPT_DIR_ENV="$(cd "$(dirname "$0")" && pwd)"

# ─── 路径辅助:定位 .env.production(源码树或离线包布局)────────
# 返回:相对于当前 cwd 的路径(空字符串表示不存在)
resolve_env_file() {
    if [ -f "compose/.env.production" ]; then
        echo "compose/.env.production"
    elif [ -f ".env.production" ]; then
        echo ".env.production"
    fi
}

# 检测失败时打印错误并退出
require_env_file() {
    local env_path
    env_path="$(resolve_env_file)"
    if [ -z "$env_path" ]; then
        echo "ERROR: .env.production not found (looked in compose/ and .)"
        exit 1
    fi
}

# ─── 加载镜像 ───────────────────────────────────────────────
load_images() {
    echo "Loading images from .tar files..."
    local errors=0

    # 源码树:images/ 在 exported_images/(build_and_export.sh 输出)
    # 离线包:images/ 直接在 bundle 根目录
    local img_dir=""
    if [ -d "images" ]; then
        img_dir="images"
    elif [ -d "exported_images" ]; then
        img_dir="exported_images"
    fi
    if [ -z "$img_dir" ]; then
        echo "WARN: images/ or exported_images/ directory not found, skipping image load"
        return 0
    fi

    for tar_file in "$img_dir/omni_desk_backend.tar" "$img_dir/omni_desk_frontend.tar" "$img_dir/postgres-14-alpine.tar" "$img_dir/redis-7-alpine.tar" "$img_dir/nginx-stable-alpine.tar"; do
        if [ -f "$tar_file" ]; then
            echo "  Loading: $(basename "$tar_file")"
            if docker load -i "$tar_file"; then
                echo "    OK"
            else
                echo "    FAIL"
                errors=$((errors + 1))
            fi
        else
            echo "  WARN: $tar_file not found"
            errors=$((errors + 1))
        fi
    done

    if [ "$errors" -gt 0 ]; then
        echo "ERROR: $errors image(s) failed to load."
        return 1
    fi

    # ─── 可选镜像:RAG 知识库栈(ragflow + 其元数据库 mysql)─────────
    # RAG 是可选能力:tar 缺失或加载失败仅 WARN,不阻塞主站启动。
    # (兼容未携带 RAG 镜像的旧版离线包;start 分支会据此决定是否启动 RAG 服务)
    for tar_file in "$img_dir/mysql-8.0.tar" "$img_dir/ragflow-v0.16.0.tar"; do
        if [ -f "$tar_file" ]; then
            echo "  Loading (optional): $(basename "$tar_file")"
            if docker load -i "$tar_file"; then
                echo "    OK"
            else
                echo "    WARN: failed to load (知识库功能不可用,主站不受影响)"
            fi
        else
            echo "  WARN: $tar_file not found (知识库功能不可用,主站不受影响)"
        fi
    done

    echo "All images loaded successfully."
}

# ─── 预部署检查 ──────────────────────────────────────────────
pre_deploy_check() {
    local errors=0

    echo "=========================================="
    echo "  预部署检查"
    echo "=========================================="
    echo ""

    # 检查 Docker 可用
    if ! command -v docker >/dev/null 2>&1; then
        echo "  FAIL: docker not found"
        errors=$((errors + 1))
    else
        echo "  PASS: Docker available ($(docker --version))"
    fi

    if ! docker compose version >/dev/null 2>&1; then
        echo "  FAIL: docker compose plugin not found"
        errors=$((errors + 1))
    else
        echo "  PASS: Docker Compose available"
    fi

    # 检查 .env.production(源码树:./.env.production;离线包:compose/.env.production)
    local env_file_path
    if [ -f "compose/.env.production" ]; then
        env_file_path="compose/.env.production"
    elif [ -f ".env.production" ]; then
        env_file_path=".env.production"
    else
        env_file_path=""
    fi
    if [ -z "$env_file_path" ]; then
        echo "  FAIL: .env.production not found (looked in compose/ and .)"
        errors=$((errors + 1))
    else
        echo "  PASS: $env_file_path exists"
        # 检查关键变量不为空
        for var in POSTGRES_PASSWORD SECRET_KEY REDIS_PASSWORD; do
            val=$(grep "^${var}=" "$env_file_path" | cut -d= -f2-)
            if [ -z "$val" ] || echo "$val" | grep -qi "<.*>"; then
                echo "  FAIL: $var is empty or placeholder"
                errors=$((errors + 1))
            else
                echo "  PASS: $var is set"
            fi
        done
    fi

    # 检查端口占用
    for port in 80 8000; do
        if command -v lsof >/dev/null 2>&1; then
            if lsof -i ":$port" >/dev/null 2>&1; then
                echo "  WARN: Port $port is in use"
            else
                echo "  PASS: Port $port is free"
            fi
        elif command -v ss >/dev/null 2>&1; then
            if ss -tlnp | grep -q ":$port "; then
                echo "  WARN: Port $port is in use"
            else
                echo "  PASS: Port $port is free"
            fi
        fi
    done

    echo ""
    if [ "$errors" -gt 0 ]; then
        echo "  $errors check(s) failed. Aborting."
        return 1
    fi
    echo "  All checks passed."
    echo ""
    return 0
}

# ─── 等待所有服务健康 ────────────────────────────────────────
wait_for_healthy() {
    local max_wait="${1:-120}"
    local interval=5
    local elapsed=0

    echo "Waiting for all services to be healthy (max ${max_wait}s)..."

    while [ "$elapsed" -lt "$max_wait" ]; do
        all_healthy=true
        for service in db redis backend frontend worker; do
            CONTAINER_ID=$(compose ps -q "$service" 2>/dev/null || true)
            if [ -n "$CONTAINER_ID" ]; then
                HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}starting{{end}}' "$CONTAINER_ID" 2>/dev/null || echo "unknown")
                if [ "$HEALTH" != "healthy" ]; then
                    all_healthy=false
                fi
            else
                all_healthy=false
            fi
        done

        if [ "$all_healthy" = true ]; then
            echo "All services are healthy (waited ${elapsed}s)."
            return 0
        fi

        sleep "$interval"
        elapsed=$((elapsed + interval))
    done

    echo "WARNING: Not all services are healthy after ${max_wait}s."
    echo "Unhealthy services:"
    for service in db redis backend frontend worker; do
        CONTAINER_ID=$(compose ps -q "$service" 2>/dev/null || true)
        if [ -n "$CONTAINER_ID" ]; then
            HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no healthcheck{{end}}' "$CONTAINER_ID" 2>/dev/null || echo "unknown")
            if [ "$HEALTH" != "healthy" ]; then
                echo "  - $service: $HEALTH"
            fi
        else
            echo "  - $service: not running"
        fi
    done
    return 1
}

# ─── 首次部署检查 ────────────────────────────────────────────
check_first_deploy() {
    if docker compose $COMPOSE_FILE $ENV_FILE exec -T backend python manage.py showmigrations 2>/dev/null | grep -q "\[ \]"; then
        echo ""
        echo "========================================"
        echo "  FIRST-TIME DEPLOYMENT DETECTED"
        echo "========================================"
        echo ""
        echo "Run these commands to initialize the database:"
        echo ""
        echo "  # 1. Run database migrations"
        echo "  ./deploy_offline.sh exec backend python manage.py migrate"
        echo ""
        echo "  # 2. Collect static files"
        echo "  ./deploy_offline.sh exec backend python manage.py collectstatic --noinput"
        echo ""
        echo "  # 3. Create admin user (non-interactive)"
        echo "  ./deploy_offline.sh exec backend python manage.py create_admin --password '<your-password>'"
        echo ""
        echo "========================================"
    fi
}

# ─── 主命令 ─────────────────────────────────────────────────
case "${1:-start}" in
    start)
        # 预部署检查
        if ! pre_deploy_check; then
            exit 1
        fi

        # 加载镜像
        if ! load_images; then
            exit 1
        fi

        echo "Starting production services..."
        # RAG 知识库为可选能力:若 bundle 未携带 ragflow/mysql 镜像(如旧版离线包),
        # 只启动核心服务,避免 compose up 因缺失镜像整体失败而拖垮主站。
        # backend 不 depends_on ragflow,运行时 RAG 调用失败会优雅降级。
        if docker image inspect infiniflow/ragflow:v0.16.0 >/dev/null 2>&1 \
           && docker image inspect mysql:8.0 >/dev/null 2>&1; then
            compose up -d
        else
            echo "WARN: ragflow/mysql 镜像缺失,仅启动核心服务(知识库功能不可用)"
            compose up -d db redis backend frontend worker
        fi

        # 等待服务健康(仅核心服务;ragflow 可选,不纳入健康门禁)
        wait_for_healthy 120 || true

        # 运行冒烟测试
        echo ""
        if [ -x "smoke_tests.sh" ]; then
            echo "Running smoke tests..."
            # P0:不再 `|| echo` 吞错 — set -e (脚本顶部) 让 smoke 失败终止部署。
            # smoke_tests.sh 自身只在 FAIL>0 时 exit 1,WARN/SKIP 仍 exit 0。
            ./smoke_tests.sh
        fi

        echo "Deployment complete."
        check_first_deploy
        echo ""
        echo "Run database migrations if first deploy:"
        echo "  ./deploy_offline.sh exec backend python manage.py migrate"
        echo "  ./deploy_offline.sh exec backend python manage.py collectstatic --noinput"
        ;;
    debug)
        require_env_file
        echo "Loading images from .tar files..."
        load_images || exit 1
        echo "Running in debug mode (foreground, press Ctrl+C to stop)..."
        compose up
        ;;
    stop)
        echo "Stopping production services..."
        compose down
        echo "Services stopped."
        ;;
    clean)
        # ─── 6 门禁保护(Task 7 brief)─────────────────────────────
        # 阻止误删生产数据卷:必须按顺序通过 6 道检查,任一失败立即非零退出,
        # 不下发 `compose down -v`(防 catastrophic data loss)。
        #
        #   a. 无 active upgrade(upgrade.sh 未运行或状态文件不在 RECOVERY/SAFE_STOPPED)
        #   b. --backup-id <id> 指定,且指定批次目录存在
        #   c. metadata.json 中 restore_verified=true
        #   d. DB checksum 校验通过
        #   e. media checksum 校验通过
        #   f. 备份位于外部 OMNIDESK_BACKUP_ROOT
        #   g. 确认参数等于 "DELETE OMNIDESK DATA <channel>"(精确大小写)
        require_env_file

        # 解析参数:--confirm-delete-data <phrase> 和 --backup-id <id>
        CONFIRM_PHRASE=""
        BACKUP_ID=""
        shift_next_phrase=0
        shift_next_id=0
        for arg in "${@:2}"; do
            case "$arg" in
                --confirm-delete-data=*) CONFIRM_PHRASE="${arg#*=}"; shift_next_phrase=0 ;;
                --confirm-delete-data)   shift_next_phrase=1 ;;
                --backup-id=*)           BACKUP_ID="${arg#*=}"; shift_next_id=0 ;;
                --backup-id)             shift_next_id=1 ;;
                --help|-h)
                    echo "Usage: $0 clean --confirm-delete-data \"DELETE OMNIDESK DATA <channel>\" --backup-id <batch-id>"
                    exit 0
                    ;;
                *)
                    # 处理两 token 形式(--confirm-delete-data <phrase> / --backup-id <id>)
                    if [ "$shift_next_phrase" -eq 1 ]; then
                        CONFIRM_PHRASE="$arg"
                        shift_next_phrase=0
                    elif [ "$shift_next_id" -eq 1 ]; then
                        BACKUP_ID="$arg"
                        shift_next_id=0
                    fi
                    ;;
            esac
        done

        # 从 .env.production 读取 channel + BACKUP_ROOT
        ENV_PATH="$(resolve_env_file)"
        CHANNEL_VAL="$(grep -E '^CHANNEL=' "$ENV_PATH" 2>/dev/null | cut -d= -f2- || true)"
        [ -z "$CHANNEL_VAL" ] && CHANNEL_VAL="stable"
        BACKUP_ROOT_VAL="${OMNIDESK_BACKUP_ROOT:-$(grep -E '^OMNIDESK_BACKUP_ROOT=' "$ENV_PATH" 2>/dev/null | cut -d= -f2- || true)}"
        [ -z "$BACKUP_ROOT_VAL" ] && BACKUP_ROOT_VAL="/opt/omnidesk/backups"

        # 审计日志路径(写到 BACKUP_ROOT/audit/clean.log)
        AUDIT_LOG_DIR="$BACKUP_ROOT_VAL/audit"
        AUDIT_LOG="$AUDIT_LOG_DIR/clean.log"
        mkdir -p "$AUDIT_LOG_DIR"

        write_audit() {
            local status="$1" reason="$2"
            local ts
            ts=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
            echo "[$ts] status=$status backup_id=${BACKUP_ID:-NONE} channel=$CHANNEL_VAL reason=$reason" >> "$AUDIT_LOG"
        }

        # ─── 门禁 a:无 active upgrade ────────────────────────────────
        # 注:用 mktemp 临时文件替代 find 输出重定向，保持 POSIX 兼容。
        # bash 在 case 解析阶段会扫描所有分支的语法(含未被选中的),
        # 若 clean 分支残留 bash-only 语法,即使只跑 start 也会在解析期
        # 撞 "syntax error near unexpected token '<'"。临时文件方案 POSIX 兼容,
        # 且 while 在当前 shell 跑,变量作用域不变(ACTIVE_BLOCKED 仍生效)。
        RUNTIME_ROOT_VAL="${OMNIDESK_RUNTIME_ROOT:-/opt/omnidesk/runtime}"
        ACTIVE_BLOCKED=0
        if [ -d "$RUNTIME_ROOT_VAL/upgrades" ]; then
            SF_LIST="$(mktemp)"
            find "$RUNTIME_ROOT_VAL/upgrades" -maxdepth 2 -name state.json 2>/dev/null > "$SF_LIST" || true
            while IFS= read -r sf; do
                local_st=$(jq -r '.state // "UNKNOWN"' "$sf" 2>/dev/null || echo "UNKNOWN")
                if [ "$local_st" != "UNKNOWN" ] && [ "$local_st" != "RECOVERY_STARTED" ] \
                   && [ "$local_st" != "RECOVERY_COMMITTED" ] && [ "$local_st" != "SAFE_STOPPED" ]; then
                    echo "ERROR: 门禁 a 失败:存在 active upgrade(状态=$local_st, file=$sf)" >&2
                    ACTIVE_BLOCKED=1
                fi
            done < "$SF_LIST"
            rm -f "$SF_LIST"
        fi
        if [ "$ACTIVE_BLOCKED" -ne 0 ]; then
            write_audit "REJECTED" "active upgrade in progress"
            echo "拒绝 clean:存在 active upgrade。请先完成/恢复/或 rm state.json。" >&2
            exit 1
        fi

        # ─── 门禁 b:--backup-id 必须指定且批次目录存在 ───────────
        if [ -z "$BACKUP_ID" ]; then
            write_audit "REJECTED" "missing --backup-id"
            echo "ERROR: 门禁 b 失败:--backup-id 必须指定" >&2
            exit 1
        fi
        BATCH_DIR_VAL="$BACKUP_ROOT_VAL/$CHANNEL_VAL/$BACKUP_ID"
        if [ ! -d "$BATCH_DIR_VAL" ]; then
            write_audit "REJECTED" "batch dir not found: $BATCH_DIR_VAL"
            echo "ERROR: 门禁 b 失败:批次目录不存在: $BATCH_DIR_VAL" >&2
            exit 1
        fi

        # ─── 门禁 f:备份目录在 BACKUP_ROOT 之内(防 path traversal) ─
        # realpath 解析软链 + 规范化,确保 BATCH_DIR_VAL 是 BACKUP_ROOT_VAL 的子目录
        REAL_BATCH="$(cd "$BATCH_DIR_VAL" 2>/dev/null && pwd -P)"
        REAL_BACKUP_ROOT="$(cd "$BACKUP_ROOT_VAL" 2>/dev/null && pwd -P)"
        case "$REAL_BATCH/" in
            "$REAL_BACKUP_ROOT/"*)
                : # OK
                ;;
            *)
                write_audit "REJECTED" "batch outside BACKUP_ROOT: $REAL_BATCH"
                echo "ERROR: 门禁 f 失败:批次目录不在 BACKUP_ROOT 内($REAL_BATCH not under $REAL_BACKUP_ROOT)" >&2
                exit 1
                ;;
        esac

        # ─── 门禁 g:确认短语必须精确匹配 "DELETE OMNIDESK DATA <channel>" ──
        EXPECTED_PHRASE="DELETE OMNIDESK DATA $CHANNEL_VAL"
        if [ "$CONFIRM_PHRASE" != "$EXPECTED_PHRASE" ]; then
            write_audit "REJECTED" "confirm phrase mismatch (got='$CONFIRM_PHRASE' expected='$EXPECTED_PHRASE')"
            echo "ERROR: 门禁 g 失败:确认短语不匹配" >&2
            echo "  期望: $EXPECTED_PHRASE" >&2
            echo "  收到: $CONFIRM_PHRASE" >&2
            exit 1
        fi

        # ─── 门禁 c/d/e:调用 verify_backup_batch.sh 校验批次完整性 ──
        # verify_backup_batch.sh 自身会:
        #   c. 校验 metadata.json 必填字段(含 restore_verified)
        #   d. 校验 database sha256
        #   e. 校验 media sha256
        # 如果 bundle 内有 verify_backup_batch.sh(生产),走外部脚本;
        # 否则(测试 bundle 仅打包 deploy_offline.sh)内联同款校验,确保门禁语义不变。
        if [ -f "$SCRIPT_DIR_ENV/verify_backup_batch.sh" ]; then
            # 生产路径:调用外部脚本
            if ! bash "$SCRIPT_DIR_ENV/verify_backup_batch.sh" "$BATCH_DIR_VAL"; then
                write_audit "REJECTED" "verify_backup_batch failed for $BATCH_DIR_VAL"
                echo "ERROR: 门禁 c/d/e 失败:批次校验未通过(见上方 verify_backup_batch 输出)" >&2
                exit 1
            fi
        else
            # 内联路径:执行与 verify_backup_batch.sh 同款的 6 项校验
            META="$BATCH_DIR_VAL/metadata.json"
            if [ ! -f "$META" ]; then
                write_audit "REJECTED" "metadata.json missing"
                echo "ERROR: 门禁 c 失败:metadata.json 缺失" >&2
                exit 1
            fi
            # c.1 必填字段(含 restore_verified)
            REQUIRED_KEYS='upgrade_id channel source_version database_file media_file database_sha256 media_sha256 database_size media_size restore_verified created_at'
            for key in $REQUIRED_KEYS; do
                VAL=$(jq -r ".$key // \"__MISSING__\"" "$META" 2>/dev/null || echo "__PARSE_ERROR__")
                if [ "$VAL" = "__MISSING__" ] || [ "$VAL" = "__PARSE_ERROR__" ] || [ -z "$VAL" ]; then
                    write_audit "REJECTED" "metadata missing field: $key"
                    echo "ERROR: 门禁 c 失败:metadata.json 缺字段 $key" >&2
                    exit 1
                fi
            done
            # c.2 restore_verified 必须 true
            RV=$(jq -r '.restore_verified' "$META")
            if [ "$RV" != "true" ]; then
                write_audit "REJECTED" "restore_verified != true"
                echo "ERROR: 门禁 c 失败:restore_verified 必须为 true(实际: $RV)" >&2
                exit 1
            fi
            DB_FILE_REL=$(jq -r '.database_file' "$META")
            MEDIA_FILE_REL=$(jq -r '.media_file' "$META")
            DB_SHA=$(jq -r '.database_sha256' "$META")
            MEDIA_SHA=$(jq -r '.media_sha256' "$META")
            DB_SIZE=$(jq -r '.database_size' "$META")
            MEDIA_SIZE=$(jq -r '.media_size' "$META")
            # 路径穿越防御
            case "$DB_FILE_REL" in ""|*".."*|/*)
                write_audit "REJECTED" "database_file invalid path"
                echo "ERROR: 门禁 c 失败:database_file 路径非法" >&2; exit 1 ;;
            esac
            case "$MEDIA_FILE_REL" in ""|*".."*|/*)
                write_audit "REJECTED" "media_file invalid path"
                echo "ERROR: 门禁 c 失败:media_file 路径非法" >&2; exit 1 ;;
            esac
            DB_PATH="$BATCH_DIR_VAL/$DB_FILE_REL"
            MEDIA_PATH="$BATCH_DIR_VAL/$MEDIA_FILE_REL"
            # d. database sha256 + size 校验
            ACTUAL_DB_SHA=$(sha256sum "$DB_PATH" 2>/dev/null | awk '{print $1}')
            if [ "$ACTUAL_DB_SHA" != "$DB_SHA" ]; then
                write_audit "REJECTED" "DB sha256 mismatch"
                echo "ERROR: 门禁 d 失败:database sha256 不匹配" >&2; exit 1
            fi
            ACTUAL_DB_SIZE=$(stat -c%s "$DB_PATH" 2>/dev/null || echo 0)
            if [ "$ACTUAL_DB_SIZE" != "$DB_SIZE" ]; then
                write_audit "REJECTED" "DB size mismatch"
                echo "ERROR: 门禁 d 失败:database size 不匹配" >&2; exit 1
            fi
            # d.1 sidecar .sha256 必须与 computed hash 一致(防篡改副文件)
            DB_SIDECAR="$BATCH_DIR_VAL/${DB_FILE_REL}.sha256"
            if [ -f "$DB_SIDECAR" ]; then
                SIDECAR_DB_SHA=$(awk '{print $1}' "$DB_SIDECAR")
                if [ "$SIDECAR_DB_SHA" != "$ACTUAL_DB_SHA" ]; then
                    write_audit "REJECTED" "DB sidecar sha256 mismatch"
                    echo "ERROR: 门禁 d 失败:database.sha256 副文件不匹配" >&2; exit 1
                fi
            fi
            # e. media sha256 + size 校验
            ACTUAL_MEDIA_SHA=$(sha256sum "$MEDIA_PATH" 2>/dev/null | awk '{print $1}')
            if [ "$ACTUAL_MEDIA_SHA" != "$MEDIA_SHA" ]; then
                write_audit "REJECTED" "media sha256 mismatch"
                echo "ERROR: 门禁 e 失败:media sha256 不匹配" >&2; exit 1
            fi
            ACTUAL_MEDIA_SIZE=$(stat -c%s "$MEDIA_PATH" 2>/dev/null || echo 0)
            if [ "$ACTUAL_MEDIA_SIZE" != "$MEDIA_SIZE" ]; then
                write_audit "REJECTED" "media size mismatch"
                echo "ERROR: 门禁 e 失败:media size 不匹配" >&2; exit 1
            fi
            # e.1 sidecar .sha256 必须与 computed hash 一致
            MEDIA_SIDECAR="$BATCH_DIR_VAL/${MEDIA_FILE_REL}.sha256"
            if [ -f "$MEDIA_SIDECAR" ]; then
                SIDECAR_MEDIA_SHA=$(awk '{print $1}' "$MEDIA_SIDECAR")
                if [ "$SIDECAR_MEDIA_SHA" != "$ACTUAL_MEDIA_SHA" ]; then
                    write_audit "REJECTED" "media sidecar sha256 mismatch"
                    echo "ERROR: 门禁 e 失败:media.sha256 副文件不匹配" >&2; exit 1
                fi
            fi
        fi

        # ─── 全部门禁通过:写审计 + 执行 compose down -v ───────────
        write_audit "APPROVED" "all gates passed, executing compose down -v"
        echo "=========================================="
        echo "  clean:全部 6 门禁通过,执行 compose down -v"
        echo "  backup_id=$BACKUP_ID"
        echo "  batch_dir=$BATCH_DIR_VAL"
        echo "  audit=$AUDIT_LOG"
        echo "=========================================="
        compose down -v
        echo "All containers and volumes removed."
        echo "WARNING: This deletes all database data."
        echo "审计已记录:$AUDIT_LOG"
        ;;
    restart)
        require_env_file
        echo "Restarting production services..."
        compose down
        compose up -d
        wait_for_healthy 120 || true
        echo "Services restarted."
        ;;
    status)
        compose ps
        ;;
    exec)
        require_env_file
        shift
        compose exec "$@"
        ;;
    logs)
        compose logs -f "${@:2}"
        ;;
    version)
        echo "Current version:"
        compose exec -T backend python manage.py list_versions 2>/dev/null || echo "Unable to connect to backend."
        ;;
    backup)
        require_env_file
        echo "Running backup..."
        ./backup.sh "${@:2}"
        ;;
    upgrade)
        require_env_file
        # upgrade.sh 自身 source upgrade_state.sh;这里显式 source 是为了
        # 在 dispatch 前就能 detect "升级状态模块缺失" 这种 bundle 完整性问题 —
        # 若 upgrade_state.sh 漏打包,在 dispatch 之前就 fail-fast,而不是
        # 让 ./upgrade.sh 在子 shell 里神秘崩。
        if [ ! -f "$SCRIPT_DIR_ENV/upgrade_state.sh" ]; then
            echo "ERROR: scripts/upgrade_state.sh 缺失 — bundle 不完整。" >&2
            echo "  请用 package_offline_bundle.sh 重新打包,确保 upgrade_state.sh 复制到 scripts/。" >&2
            exit 1
        fi
        SMOKE_STRICT=1 ./upgrade.sh "${2:-.}"
        ;;
    rollback)
        require_env_file
        if [ ! -f "$SCRIPT_DIR_ENV/upgrade_state.sh" ]; then
            echo "ERROR: scripts/upgrade_state.sh 缺失 — bundle 不完整。" >&2
            exit 1
        fi
        ./rollback.sh
        ;;
    migrate)
        require_env_file
        echo "Running pre-migration check..."
        compose exec -T backend python manage.py check_migrations 2>/dev/null || true
        echo ""
        read -p "Run migrations? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            echo "Creating backup first..."
            ./backup.sh --db-only
            compose exec -T backend python manage.py migrate
            echo "Migrations complete."
            # 播种智能助手默认 LLM 端点(幂等:LlmEndpoint 表非空时自动跳过)。
            # 修复离线部署根因:空库无 LLM 端点时所有对话返回"所有 LLM 端点均不可用"。
            echo "Seeding default LLM endpoint for smart assistant (idempotent)..."
            compose exec -T backend python manage.py seed_llm_endpoint
        else
            echo "Migrations skipped."
        fi
        ;;
    install-desktop)
        DEST_DIR="${2:-/opt/OmniDesk}"
        EXE_FILE="${3:-offline-packages/OmniDeskNotifier.exe}"
        if [ ! -f "$EXE_FILE" ]; then
            echo "ERROR: Desktop executable not found: $EXE_FILE"
            echo "Place the PyInstaller-built .exe file in offline-packages/"
            exit 1
        fi
        echo "Installing OmniDesk Desktop Notifier to $DEST_DIR ..."
        mkdir -p "$DEST_DIR"
        cp "$EXE_FILE" "$DEST_DIR/OmniDeskNotifier.exe"
        chmod +x "$DEST_DIR/OmniDeskNotifier.exe"

        # Create desktop shortcut
        DESKTOP="$HOME/Desktop"
        if [ -d "$DESKTOP" ]; then
            cat > "$DESKTOP/OmniDesk.desktop" << 'DESKTOP_EOF'
[Desktop Entry]
Name=OmniDesk 桌面助手
Exec=/opt/OmniDesk/OmniDeskNotifier.exe
Icon=application-x-executable
Type=Application
Comment=消息提醒和快速访问
DESKTOP_EOF
            chmod +x "$DESKTOP/OmniDesk.desktop"
            echo "Desktop shortcut created."
        fi

        # Create autostart entry
        AUTOSTART="$HOME/.config/autostart"
        mkdir -p "$AUTOSTART"
        cat > "$AUTOSTART/OmniDesk.desktop" << 'AUTOSTART_EOF'
[Desktop Entry]
Name=OmniDesk 桌面助手
Exec=/opt/OmniDesk/OmniDeskNotifier.exe
Icon=application-x-executable
Type=Application
Comment=消息提醒和快速访问
X-GNOME-Autostart-enabled=true
AUTOSTART_EOF
        echo "Autostart entry created."
        echo "Installation complete."
        ;;
    *)
        echo "Usage: $0 {start|debug|stop|clean|restart|status|logs|exec|version|backup|upgrade|rollback|migrate|install-desktop}"
        echo ""
        echo "Commands:"
        echo "  start             Load images and start services (with pre-check, smoke test)"
        echo "  debug             Load images and start services in foreground (Ctrl+C to stop)"
        echo "  stop              Stop and remove all containers"
        echo "  clean             Stop containers and DELETE all volumes (including database data)"
        echo "  restart           Stop and start services"
        echo "  status            Show running containers"
        echo "  logs              Show service logs"
        echo "  exec              Execute command in a service"
        echo "  version           Show current version and migration history"
        echo "  backup            Create database and media backup"
        echo "  upgrade           Safe version upgrade with backup"
        echo "  rollback          Rollback to a previous version (channel-scoped backups; --channel={alpha|beta|preview|stable|hotfix})"
        echo "  migrate           Pre-check and run database migrations"
        echo "  install-desktop   Install desktop notifier (usage: install-desktop [DEST_DIR] [EXE_FILE])"
        exit 1
        ;;
esac
