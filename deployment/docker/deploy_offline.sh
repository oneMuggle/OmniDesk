#!/bin/bash
set -e

# Use standalone compose file to avoid merge with docker-compose.override.yml
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
    *)
        echo "Usage: $0 {start|debug|stop|clean|restart|status|logs|exec}"
        echo ""
        echo "Commands:"
        echo "  start   Load images and start services in background (default)"
        echo "  debug   Load images and start services in foreground (Ctrl+C to stop)"
        echo "  stop    Stop and remove all containers"
        echo "  clean   Stop containers and DELETE all volumes (including database data)"
        echo "  restart Stop and start services"
        echo "  status  Show running containers"
        echo "  logs    Show service logs (e.g., ./deploy_offline.sh logs backend)"
        echo "  exec    Execute command in a service (e.g., ./deploy_offline.sh exec backend bash)"
        exit 1
        ;;
esac
