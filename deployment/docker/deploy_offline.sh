#!/bin/bash
set -e

# deploy_offline.sh — 离线部署管理脚本
# 使用方法: ./deploy_offline.sh {start|debug|stop|clean|restart|status|logs|exec|version|backup|upgrade|rollback|migrate|install-desktop}

COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$COMPOSE_DIR"

# Use standalone compose file (no merge with docker-compose.yml)
COMPOSE_FILE="-f docker-compose.offline.yml"
ENV_FILE="--env-file .env.production"

compose() {
    docker compose $COMPOSE_FILE $ENV_FILE "$@"
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

    # 检查 .env.production
    if [ ! -f ".env.production" ]; then
        echo "  FAIL: .env.production not found"
        errors=$((errors + 1))
    else
        echo "  PASS: .env.production exists"
        # 检查关键变量不为空
        for var in POSTGRES_PASSWORD SECRET_KEY REDIS_PASSWORD; do
            val=$(grep "^${var}=" .env.production | cut -d= -f2-)
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

# ─── 加载镜像 ───────────────────────────────────────────────
load_images() {
    echo "Loading images from .tar files..."
    local errors=0

    for tar_file in "exported_images/omni_desk_backend.tar" "exported_images/omni_desk_frontend.tar" "exported_images/postgres-14-alpine.tar" "exported_images/redis-7-alpine.tar" "exported_images/nginx-stable-alpine.tar"; do
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
    echo "All images loaded successfully."
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
        compose up -d

        # 等待服务健康
        wait_for_healthy 120 || true

        # 运行冒烟测试
        echo ""
        if [ -x "smoke_tests.sh" ]; then
            echo "Running smoke tests..."
            ./smoke_tests.sh || echo "Smoke tests had failures. Check output above."
        fi

        echo "Deployment complete."
        check_first_deploy
        echo ""
        echo "Run database migrations if first deploy:"
        echo "  ./deploy_offline.sh exec backend python manage.py migrate"
        echo "  ./deploy_offline.sh exec backend python manage.py collectstatic --noinput"
        ;;
    debug)
        if [ ! -f ".env.production" ]; then
            echo "ERROR: .env.production not found."
            exit 1
        fi
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
        echo "Stopping services and removing volumes..."
        compose down -v
        echo "All containers and volumes removed."
        echo "WARNING: This deletes all database data."
        ;;
    restart)
        if [ ! -f ".env.production" ]; then
            echo "ERROR: .env.production not found."
            exit 1
        fi
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
        if [ ! -f ".env.production" ]; then
            echo "ERROR: .env.production not found."
            exit 1
        fi
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
        if [ ! -f ".env.production" ]; then
            echo "ERROR: .env.production not found."
            exit 1
        fi
        echo "Running backup..."
        ./backup.sh "${@:2}"
        ;;
    upgrade)
        if [ ! -f ".env.production" ]; then
            echo "ERROR: .env.production not found."
            exit 1
        fi
        ./upgrade.sh "${2:-.}"
        ;;
    rollback)
        if [ ! -f ".env.production" ]; then
            echo "ERROR: .env.production not found."
            exit 1
        fi
        ./rollback.sh
        ;;
    migrate)
        if [ ! -f ".env.production" ]; then
            echo "ERROR: .env.production not found."
            exit 1
        fi
        echo "Running pre-migration check..."
        compose exec -T backend python manage.py check_migrations 2>/dev/null || true
        echo ""
        read -p "Run migrations? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            echo "Creating backup first..."
            ./backup.sh --db-only
            compose exec -T backend python manage.py migrate
            echo "Migrations complete."
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
