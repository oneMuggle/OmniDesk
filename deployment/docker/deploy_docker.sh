#!/bin/bash

# deploy_docker.sh
# A script to manage the Docker deployment of the Omni Desk application.

# Stop on first error
set -e

# Function to display help message
usage() {
    echo "Usage: $0 [up|down|build|logs|migrate|collectstatic]"
    echo "Commands:"
    echo "  up:             Builds and starts the services in detached mode."
    echo "  down:           Stops and removes the services."
    echo "  build:          Builds or rebuilds the services."
    echo "  logs [service]: Follows the logs of a service (e.g., backend, frontend)."
    echo "  migrate:        Runs Django database migrations."
    echo "  collectstatic:  Collects Django static files."
}

# Main command logic
case "$1" in
    up)
        echo "Starting all services..."
        docker-compose up -d --build
        echo "Services are up and running."
        ;;
    down)
        echo "Stopping all services..."
        docker-compose down
        echo "Services have been stopped."
        ;;
    build)
        echo "Building services..."
        docker-compose build
        echo "Build complete."
        ;;
    logs)
        if [ -z "$2" ]; then
            docker-compose logs -f
        else
            docker-compose logs -f "$2"
        fi
        ;;
    migrate)
        echo "Running database migrations..."
        docker-compose exec backend python manage.py migrate
        echo "Migrations complete."
        ;;
    collectstatic)
        echo "Collecting static files..."
        docker-compose exec backend python manage.py collectstatic --no-input
        echo "Static files collected."
        ;;
    *)
        usage
        exit 1
        ;;
esac

exit 0