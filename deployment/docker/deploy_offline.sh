#!/bin/bash
set -e

# Use standalone compose file (no merge with docker-compose.yml)
COMPOSE_FILE="-f docker-compose.offline-standalone.yml"
ENV_FILE="--env-file .env.production"

compose() {
    docker compose $COMPOSE_FILE $ENV_FILE "$@"
}

# 检查是否需要首次部署初始化（数据库中没有迁移记录）
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
        echo "  # 3. Create admin user (interactive)"
        echo "  ./deploy_offline.sh exec backend python manage.py createsuperuser"
        echo ""
        echo "========================================"
    fi
}

case "${1:-start}" in
    start)
        echo "Loading images from .tar files..."
        docker load -i "exported_images/omni_desk_backend.tar"
        docker load -i "exported_images/omni_desk_frontend.tar"
        docker load -i "exported_images/postgres.tar"
        docker load -i "exported_images/redis.tar"
        docker load -i "exported_images/nginx.tar"
        echo "Images loaded successfully."

        if [ ! -f ".env.production" ]; then
            echo "ERROR: .env.production not found."
            echo "Copy .env.production from the build machine before deploying."
            exit 1
        fi

        echo "Starting production services..."
        compose up -d
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
        docker load -i "exported_images/omni_desk_backend.tar"
        docker load -i "exported_images/omni_desk_frontend.tar"
        docker load -i "exported_images/postgres.tar"
        docker load -i "exported_images/redis.tar"
        docker load -i "exported_images/nginx.tar"
        echo "Images loaded successfully."
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
        echo "  start             Load images and start services in background (default)"
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
        echo "  rollback          Rollback to a previous version"
        echo "  migrate           Pre-check and run database migrations"
        echo "  install-desktop   Install desktop notifier (usage: install-desktop [DEST_DIR] [EXE_FILE])"
        exit 1
        ;;
esac
