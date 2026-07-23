#!/bin/bash

# build-metadata.sh — 构建元数据记录工具
# 使用方法:
#   ./build-metadata.sh record [version] [images_dir] — 记录构建元数据
#   ./build-metadata.sh show [images_dir]             — 显示构建元数据

COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$COMPOSE_DIR"

record_metadata() {
    local version="${1:-unknown}"
    local images_dir="${2:-exported_images}"
    mkdir -p "$images_dir"

    local manifest="$images_dir/build-manifest.json"
    local git_sha
    git_sha=$(git -C "$COMPOSE_DIR/../.." rev-parse --short HEAD 2>/dev/null || echo "unknown")
    local build_time
    build_time=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

    local backend_digest
    backend_digest=$(docker inspect --format='{{.Id}}' "omni-desk-backend-prod:latest" 2>/dev/null || echo "unknown")
    local frontend_digest
    frontend_digest=$(docker inspect --format='{{.Id}}' "omni-desk-frontend-prod:latest" 2>/dev/null || echo "unknown")
    local backend_size
    backend_size=$(docker inspect --format='{{.Size}}' "omni-desk-backend-prod:latest" 2>/dev/null || echo "0")
    local frontend_size
    frontend_size=$(docker inspect --format='{{.Size}}' "omni-desk-frontend-prod:latest" 2>/dev/null || echo "0")

    cat > "$manifest" << EOF
{
  "version": "$version",
  "build_time": "$build_time",
  "git_sha": "$git_sha",
  "images": {
    "backend": {
      "name": "omni-desk-backend-prod:v${version}",
      "digest": "$backend_digest",
      "size_bytes": $backend_size
    },
    "frontend": {
      "name": "omni-desk-frontend-prod:v${version}",
      "digest": "$frontend_digest",
      "size_bytes": $frontend_size
    }
  },
  "base_images": {
    "postgres": "postgres:14-alpine",
    "redis": "redis:7-alpine",
    "nginx": "nginx:stable-alpine"
  }
}
EOF

    echo "Metadata recorded to $manifest"
    python3 -c "
import json
with open('$manifest') as f:
    d = json.load(f)
print(f\"  Version:   {d['version']}\")
print(f\"  Built:     {d['build_time']}\")
print(f\"  Git SHA:   {d['git_sha']}\")
print(f\"  Backend:   {d['images']['backend']['name']}\")
print(f\"  Frontend:  {d['images']['frontend']['name']}\")
"
}

show_metadata() {
    local images_dir="${1:-exported_images}"
    local manifest="$images_dir/build-manifest.json"

    if [ ! -f "$manifest" ]; then
        echo "No build manifest found at $manifest"
        exit 1
    fi

    echo "Build Manifest: $manifest"
    echo "────────────────────────────────────"
    python3 -c "
import json
with open('$manifest') as f:
    d = json.load(f)
print(f\"Version:    {d.get('version', 'N/A')}\")
print(f\"Built:      {d.get('build_time', 'N/A')}\")
print(f\"Git SHA:    {d.get('git_sha', 'N/A')}\")
print()
print('Images:')
for name, info in d.get('images', {}).items():
    size_mb = info.get('size_bytes', 0) / 1024 / 1024
    print(f\"  {info.get('name', name)}: {size_mb:.0f}MB\")
print()
print('Base Images:')
for name, tag in d.get('base_images', {}).items():
    print(f\"  {name}: {tag}\")
"
}

case "${1:-show}" in
    record)
        record_metadata "${2:-unknown}" "${3:-exported_images}"
        ;;
    show)
        show_metadata "${2:-exported_images}"
        ;;
    *)
        echo "Usage: $0 {record [version] [dir]|show [dir]}"
        exit 1
        ;;
esac
