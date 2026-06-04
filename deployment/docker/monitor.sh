#!/bin/bash

# monitor.sh — 轻量级容器状态监控
# 使用方法:
#   ./monitor.sh status        — 显示所有容器状态和健康信息
#   ./monitor.sh watch [N]     — 持续监控（每 N 秒轮询，默认 30 秒）
#   ./monitor.sh logs [service] [N] — 显示最近 N 行日志（默认 100 行）
#   ./monitor.sh crash-detect  — 检测异常退出/重启

COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$COMPOSE_DIR"

COMPOSE_FILE="-f docker-compose.offline.yml"
ENV_FILE="--env-file .env.production"

compose() {
    docker compose $COMPOSE_FILE $ENV_FILE "$@"
}

show_status() {
    echo "=========================================="
    echo "  容器状态"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="
    echo ""

    compose ps

    echo ""
    echo "健康状态详情:"
    echo "────────────────────────────────────"

    for service in db redis backend frontend worker; do
        CONTAINER_ID=$(compose ps -q "$service" 2>/dev/null)
        if [ -n "$CONTAINER_ID" ]; then
            HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no healthcheck{{end}}' "$CONTAINER_ID" 2>/dev/null)
            RESTARTS=$(docker inspect --format='{{.RestartCount}}' "$CONTAINER_ID" 2>/dev/null)

            case "$HEALTH" in
                healthy)   ICON="[✓]" ;;
                unhealthy) ICON="[✗]" ;;
                starting)  ICON="[...]" ;;
                *)         ICON="[?]" ;;
            esac

            echo "  $ICON $service: health=$HEALTH restarts=$RESTARTS"
            if [ "$HEALTH" = "unhealthy" ]; then
                LAST_LOG=$(docker inspect --format='{{with $last := index .State.Health.Log (sub (len .State.Health.Log) 1)}}{{$last.Output}}{{end}}' "$CONTAINER_ID" 2>/dev/null | tail -c 200)
                echo "    Last: $LAST_LOG"
            fi
        else
            echo "  [ ] $service: not running"
        fi
    done

    echo ""
    echo "端口映射:"
    compose ps --format "table {{.Name}}\t{{.Ports}}" 2>/dev/null || true
}

watch_status() {
    local interval="${1:-30}"
    echo "Monitoring containers every ${interval}s (Ctrl+C to stop)..."

    while true; do
        clear
        echo "=========================================="
        echo "  OmniDesk 监控面板"
        echo "  $(date '+%Y-%m-%d %H:%M:%S')"
        echo "  轮询间隔: ${interval}s"
        echo "=========================================="
        echo ""

        compose ps 2>/dev/null
        echo ""

        UNHEALTHY=0
        for service in db redis backend frontend worker; do
            CONTAINER_ID=$(compose ps -q "$service" 2>/dev/null)
            if [ -n "$CONTAINER_ID" ]; then
                HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no healthcheck{{end}}' "$CONTAINER_ID" 2>/dev/null)
                case "$HEALTH" in
                    healthy)   ICON="[✓]" ;;
                    unhealthy) ICON="[✗]"; UNHEALTHY=$((UNHEALTHY + 1)) ;;
                    starting)  ICON="[.]" ;;
                    *)         ICON="[?]" ;;
                esac
                printf "  %-8s %-12s %s\n" "$ICON" "$service" "$HEALTH"
            else
                printf "  [ ]    %-12s not running\n" "$service"
            fi
        done

        if [ "$UNHEALTHY" -gt 0 ]; then
            echo ""
            echo "  WARNING: $UNHEALTHY container(s) unhealthy!"
        fi

        sleep "$interval"
    done
}

show_logs() {
    local service="${1:-}"
    local lines="${2:-100}"

    if [ -n "$service" ]; then
        echo "=== Logs for: $service (last $lines lines) ==="
        compose logs --tail="$lines" "$service"
    else
        echo "=== All service logs (last $lines lines each) ==="
        compose logs --tail="$lines"
    fi
}

detect_crashes() {
    echo "=========================================="
    echo "  异常检测"
    echo "=========================================="
    echo ""

    ALERTS=0

    for service in db redis backend frontend worker; do
        CONTAINER_ID=$(compose ps -q "$service" 2>/dev/null)
        if [ -n "$CONTAINER_ID" ]; then
            RESTARTS=$(docker inspect --format='{{.RestartCount}}' "$CONTAINER_ID" 2>/dev/null || echo "0")
            HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no healthcheck{{end}}' "$CONTAINER_ID" 2>/dev/null)
            OOM=$(docker inspect --format='{{.State.OOMKilled}}' "$CONTAINER_ID" 2>/dev/null || echo "false")

            if [ "$RESTARTS" -gt 0 ] 2>/dev/null; then
                echo "  ⚠  $service: restarted $RESTARTS times"
                ALERTS=$((ALERTS + 1))
            fi
            if [ "$HEALTH" = "unhealthy" ]; then
                echo "  ✗  $service: unhealthy"
                ALERTS=$((ALERTS + 1))
            fi
            if [ "$OOM" = "true" ]; then
                echo "  ✗  $service: OOM killed"
                ALERTS=$((ALERTS + 1))
            fi
        else
            echo "  ?  $service: not running"
            ALERTS=$((ALERTS + 1))
        fi
    done

    echo ""
    if [ "$ALERTS" -eq 0 ]; then
        echo "STATUS: All clear — no issues detected"
    else
        echo "STATUS: $ALERTS alert(s) — check service health"
    fi
}

case "${1:-status}" in
    status) show_status ;;
    watch) watch_status "${2:-30}" ;;
    logs) show_logs "${2:-}" "${3:-100}" ;;
    crash-detect|crash) detect_crashes ;;
    *)
        echo "Usage: $0 {status|watch [seconds]|logs [service] [lines]|crash-detect}"
        echo ""
        echo "Commands:"
        echo "  status              Show container status and health"
        echo "  watch [seconds]     Continuous monitoring (default: 30s interval)"
        echo "  logs [service] [N]  Show last N lines of logs (default: all, 100 lines)"
        echo "  crash-detect        Check for crashes, restarts, OOM kills"
        exit 1
        ;;
esac
