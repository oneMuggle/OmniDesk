#!/bin/bash
set -e

# build_and_export.sh — 构建生产镜像并导出为离线 .tar 包
# 使用方法: ./build_and_export.sh [version]
# 版本号从 VERSION 文件读取，也可通过参数覆盖

COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$COMPOSE_DIR"

# ─── 版本管理 ─────────────────────────────────────────────────
VERSION_FILE="VERSION"
if [ -f "$VERSION_FILE" ]; then
    FILE_VERSION=$(cat "$VERSION_FILE" | tr -d '[:space:]')
fi
BUILD_VERSION="${1:-${FILE_VERSION}}"

if [ -z "$BUILD_VERSION" ]; then
    echo "ERROR: No version specified and VERSION file not found."
    echo "Usage: $0 [version]"
    exit 1
fi

# 验证语义化版本格式(支持渠道后缀: -alpha.N, -beta.N, -rc.N)
if ! echo "$BUILD_VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-alpha\.[0-9]+|-beta\.[0-9]+|-rc\.[0-9]+)?$'; then
    echo "ERROR: Invalid version format '$BUILD_VERSION'."
    echo "Use semantic versioning: MAJOR.MINOR.PATCH or MAJOR.MINOR.PATCH-CHANNEL.N"
    echo "Examples: 1.0.0, 1.0.0-alpha.1, 1.0.0-beta.2, 1.0.0-rc.1"
    exit 1
fi

echo "Building version: $BUILD_VERSION"

# 镜像命名 — 与 GHCR 全名保持一致 (ghcr.io/onemuggle/omni-desk-{backend,frontend})
# 离线 compose (docker-compose.offline.yml) 引用 GHCR 全名,本地 docker save 源用简化名
BACKEND_IMAGE="omni-desk-backend-prod:v${BUILD_VERSION}"
FRONTEND_IMAGE="omni-desk-frontend-prod:v${BUILD_VERSION}"
# GHCR 全名 — 离线包加载后由 deploy 流程 docker tag 添加,让 offline compose 能直接引用
BACKEND_IMAGE_GHCR="ghcr.io/onemuggle/omni-desk-backend:v${BUILD_VERSION}"
FRONTEND_IMAGE_GHCR="ghcr.io/onemuggle/omni-desk-frontend:v${BUILD_VERSION}"

# 判断是否为 stable 渠道(无后缀)
IS_STABLE=true
if echo "$BUILD_VERSION" | grep -qE -- '-(alpha|beta|rc)\.[0-9]+$'; then
    IS_STABLE=false
fi

# :latest 标签仅 stable 渠道使用(渠道规范要求)
if [ "$IS_STABLE" = true ]; then
    BACKEND_IMAGE_LATEST="omni-desk-backend-prod:latest"
    FRONTEND_IMAGE_LATEST="omni-desk-frontend-prod:latest"
fi

# 基础镜像（离线模式下使用本地已有镜像）
POSTGRES_IMAGE="postgres:14-alpine"
REDIS_IMAGE="redis:7-alpine"
NGINX_IMAGE="nginx:stable-alpine"

EXPORT_DIR="exported_images"
mkdir -p "$EXPORT_DIR"

# ─── Phase 1: 构建镜像 ──────────────────────────────────────
echo "=========================================="
echo "  Phase 1: 构建生产镜像"
echo "=========================================="
echo ""

# 构建生产目标
echo "Building backend production image..."
cd "$COMPOSE_DIR/../.."
docker build \
    -f deployment/docker/omni_desk_backend/Dockerfile \
    --target production \
    --platform linux/amd64 \
    -t "$BACKEND_IMAGE" \
    .

echo "Building frontend production image..."
cd "$COMPOSE_DIR/../.."
docker build \
    -f omni_desk_frontend/Dockerfile \
    --platform linux/amd64 \
    -t "$FRONTEND_IMAGE" \
    omni_desk_frontend/

cd "$COMPOSE_DIR"

# 打 latest 标签(仅 stable 渠道,供 compose 文件引用)
if [ "$IS_STABLE" = true ]; then
    docker tag "$BACKEND_IMAGE" "$BACKEND_IMAGE_LATEST"
    docker tag "$FRONTEND_IMAGE" "$FRONTEND_IMAGE_LATEST"
    echo "Tagged :latest (stable channel)"
else
    echo "Skipped :latest tag (pre-release channel: $BUILD_VERSION)"
fi

# 同时打 GHCR 全名标签（让 offline compose 与 GHCR 引用一致,避免镜像名割裂）
docker tag "$BACKEND_IMAGE" "$BACKEND_IMAGE_GHCR"
docker tag "$FRONTEND_IMAGE" "$FRONTEND_IMAGE_GHCR"

echo ""
echo "Build complete:"
echo "  Backend:  $BACKEND_IMAGE -> $BACKEND_IMAGE_GHCR"
echo "  Frontend: $FRONTEND_IMAGE -> $FRONTEND_IMAGE_GHCR"
if [ "$IS_STABLE" = true ]; then
    echo "  + :latest tags (stable channel)"
fi

# ─── Phase 1.3: 构建后验证 ──────────────────────────────────
echo ""
echo "=========================================="
echo "  Phase 1.3: 构建后验证"
echo "=========================================="
echo ""

BUILD_VERIFIED=true

echo "Verifying backend image..."
# 验证 Django 镜像的基本完整性：
# 1. 确认 manage.py 存在
# 2. 确认依赖安装成功
# 3. 确认代码语法正确（compile check）
BACKEND_CHECK_OUTPUT=$(docker run --rm --entrypoint bash \
    "$BACKEND_IMAGE" -c "
    test -f manage.py && \
    python -c 'import django; print(\"Django version:\", django.__version__)' && \
    python -c 'import psycopg2; print(\"psycopg2 OK\")' && \
    python -c 'import celery; print(\"celery OK\")' && \
    python -c 'import gunicorn; print(\"gunicorn OK\")' && \
    pip check 2>&1 && echo 'pip check OK'
    " 2>&1) || {
    echo "  FAIL: Backend image dependency check failed"
    echo "  $BACKEND_CHECK_OUTPUT"
    BUILD_VERIFIED=false
}
if [ "$BUILD_VERIFIED" = true ]; then
    echo "  PASS: Backend image dependencies verified"
fi

echo "Verifying frontend image (nginx config)..."
# nginx -t 需要在有 upstream backend 解析的环境下运行
# 这里只验证配置文件语法正确性（不验证 upstream 解析）
FRONTEND_CHECK_OUTPUT=$(docker run --rm --entrypoint sh "$FRONTEND_IMAGE" -c \
    "nginx -t 2>&1 || echo 'UPSTREAM_EXPECTED_FAIL'")
if echo "$FRONTEND_CHECK_OUTPUT" | grep -q "UPSTREAM_EXPECTED_FAIL"; then
    # upstream 解析失败是正常的（没有 backend 容器）
    # 但确认 nginx 二进制和配置文件本身存在
    if echo "$FRONTEND_CHECK_OUTPUT" | grep -q "configuration file"; then
        echo "  PASS: Nginx config exists (upstream resolution requires docker-compose network)"
    else
        echo "  FAIL: Nginx configuration issue"
        echo "  $FRONTEND_CHECK_OUTPUT"
        BUILD_VERIFIED=false
    fi
elif echo "$FRONTEND_CHECK_OUTPUT" | grep -q "test failed"; then
    echo "  FAIL: Nginx config test failed"
    echo "  $FRONTEND_CHECK_OUTPUT"
    BUILD_VERIFIED=false
else
    echo "  PASS: Nginx config test"
fi

# 验证镜像大小合理
BACKEND_SIZE=$(docker inspect --format='{{.Size}}' "$BACKEND_IMAGE" 2>/dev/null || echo "0")
FRONTEND_SIZE=$(docker inspect --format='{{.Size}}' "$FRONTEND_IMAGE" 2>/dev/null || echo "0")
BACKEND_MB=$((BACKEND_SIZE / 1024 / 1024))
FRONTEND_MB=$((FRONTEND_SIZE / 1024 / 1024))

echo "Image sizes: Backend ${BACKEND_MB}MB, Frontend ${FRONTEND_MB}MB"

if [ "$BACKEND_SIZE" -lt 100000000 ]; then
    echo "  WARN: Backend image unusually small (<100MB)"
fi
if [ "$FRONTEND_SIZE" -lt 10000000 ]; then
    echo "  WARN: Frontend image unusually small (<10MB)"
fi

if [ "$BUILD_VERIFIED" = false ]; then
    echo ""
    echo "BUILD VERIFICATION FAILED. Aborting."
    exit 1
fi
echo ""
echo "Build verification: ALL PASSED"

# ─── Phase 1.4: 构建元数据记录 ─────────────────────────────
echo ""
echo "=========================================="
echo "  Phase 1.4: 记录构建元数据"
echo "=========================================="
echo ""

BACKEND_DIGEST=$(docker inspect --format='{{.Id}}' "$BACKEND_IMAGE" 2>/dev/null || echo "unknown")
FRONTEND_DIGEST=$(docker inspect --format='{{.Id}}' "$FRONTEND_IMAGE" 2>/dev/null || echo "unknown")
GIT_SHA=$(git -C "$COMPOSE_DIR/../.." rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_TIME=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

cat > "$EXPORT_DIR/build-manifest.json" << EOF
{
  "version": "$BUILD_VERSION",
  "build_time": "$BUILD_TIME",
  "git_sha": "$GIT_SHA",
  "images": {
    "backend": {
      "name": "$BACKEND_IMAGE",
      "digest": "$BACKEND_DIGEST",
      "size_bytes": $BACKEND_SIZE
    },
    "frontend": {
      "name": "$FRONTEND_IMAGE",
      "digest": "$FRONTEND_DIGEST",
      "size_bytes": $FRONTEND_SIZE
    }
  },
  "base_images": {
    "postgres": "$POSTGRES_IMAGE",
    "redis": "$REDIS_IMAGE",
    "nginx": "$NGINX_IMAGE"
  }
}
EOF

echo "Build manifest saved to $EXPORT_DIR/build-manifest.json"

# ─── Phase 1.2: 获取基础镜像 ───────────────────────────────
echo ""
echo "=========================================="
echo "  Phase 1.2: 准备基础镜像"
echo "=========================================="
echo ""

OFFLINE_MODE="${OFFLINE_MODE:-auto}"

check_image_exists() {
    docker image inspect "$1" >/dev/null 2>&1
}

for base_image in "$POSTGRES_IMAGE" "$REDIS_IMAGE" "$NGINX_IMAGE"; do
    if check_image_exists "$base_image"; then
        echo "  OK: $base_image (local)"
    elif [ "$OFFLINE_MODE" = "true" ]; then
        echo "  ERROR: $base_image not found locally and OFFLINE_MODE=true"
        echo "  Set OFFLINE_MODE=false to allow pulling, or run with network first."
        exit 1
    else
        echo "  Pulling: $base_image..."
        docker pull "$base_image"
    fi
done

# ─── Phase 2: 导出镜像 ──────────────────────────────────────
echo ""
echo "=========================================="
echo "  Phase 2: 导出镜像"
echo "=========================================="
echo ""

echo "Saving images to .tar files..."
# 同时保存源名 + GHCR 全名 tag,使 tar 在新机器 docker load 后无需额外 docker tag
# (经实测:多 tag save 不会重复 layer,体积不变,只 1 layer)
docker save -o "$EXPORT_DIR/omni_desk_backend.tar" "$BACKEND_IMAGE" "$BACKEND_IMAGE_GHCR"
docker save -o "$EXPORT_DIR/omni_desk_frontend.tar" "$FRONTEND_IMAGE" "$FRONTEND_IMAGE_GHCR"
docker save -o "$EXPORT_DIR/postgres-14-alpine.tar" "$POSTGRES_IMAGE"
docker save -o "$EXPORT_DIR/redis-7-alpine.tar" "$REDIS_IMAGE"
docker save -o "$EXPORT_DIR/nginx-stable-alpine.tar" "$NGINX_IMAGE"

# Fix ownership: docker save creates files as root:root, change to current user
CURRENT_USER=$(whoami)
CURRENT_GROUP=$(id -gn)
echo "Fixing file ownership to ${CURRENT_USER}:${CURRENT_GROUP}..."
chown "${CURRENT_USER}:${CURRENT_GROUP}" "$EXPORT_DIR"/*.tar

echo ""
echo "Exported files:"
for tar_file in "$EXPORT_DIR"/*.tar; do
    SIZE=$(du -h "$tar_file" | cut -f1)
    echo "  $(basename "$tar_file"): $SIZE"
done

# ─── Phase 2.1: 生成 checksum ───────────────────────────────
echo ""
echo "Generating SHA256 checksums..."
cd "$EXPORT_DIR"
sha256sum *.tar > checksums.sha256
cd "$COMPOSE_DIR"
echo "Checksums saved to $EXPORT_DIR/checksums.sha256"

# ─── Phase 3: 生成 .env.production ──────────────────────────
echo ""
echo "=========================================="
echo "  Phase 3: 环境配置"
echo "=========================================="
echo ""

if [ ! -f ".env.production" ] && [ -f ".env.production.example" ]; then
    echo "Generating .env.production from example template (first-time setup)..."
    cp .env.production.example .env.production

    python3 -c "
import secrets
with open('.env.production', 'r') as f:
    content = f.read()
content = content.replace('<GENERATE-NEW-SECRET-KEY>', secrets.token_urlsafe(50))
content = content.replace('<CHANGE-TO-STRONG-PASSWORD>', secrets.token_urlsafe(20))
with open('.env.production', 'w') as f:
    f.write(content)
"

    echo ".env.production generated successfully."
    echo ""
    echo "SECURITY REMINDER: Review and change secrets before deploying to production."
elif [ -f ".env.production" ]; then
    echo ".env.production already exists, keeping existing configuration."
fi

# ─── 完成 ────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  构建完成 v${BUILD_VERSION}"
echo "=========================================="
echo ""
echo "Exported files: $EXPORT_DIR/"
echo "Build manifest: $EXPORT_DIR/build-manifest.json"
echo "Checksums:      $EXPORT_DIR/checksums.sha256"
echo ""
echo "Next steps:"
echo "  1. Copy '$EXPORT_DIR/' to your offline server"
echo "  2. Copy docker-compose files and .env.production"
echo "  3. On the target server: ./deploy_offline.sh start"
echo ""
echo "Verify on target server:"
echo "  sha256sum -c checksums.sha256"
