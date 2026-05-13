#!/bin/bash
set -e

# validate_artifacts.sh — 验证构建产物（.tar 文件）的完整性
# 使用方法: ./validate_artifacts.sh [images_dir]
# 默认检查 exported_images/ 目录

COMPOSE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$COMPOSE_DIR"

IMAGE_DIR="${1:-exported_images}"

if [ ! -d "$IMAGE_DIR" ]; then
    echo "ERROR: Directory '$IMAGE_DIR' not found."
    exit 1
fi

PASS=0
FAIL=0
WARN=0

result() {
    local status="$1"
    local msg="$2"
    case "$status" in
        PASS) echo "  PASS: $msg"; PASS=$((PASS + 1)) ;;
        FAIL) echo "  FAIL: $msg"; FAIL=$((FAIL + 1)) ;;
        WARN) echo "  WARN: $msg"; WARN=$((WARN + 1)) ;;
    esac
}

echo "=========================================="
echo "  构建产物验证"
echo "  目录: $IMAGE_DIR"
echo "=========================================="
echo ""

# ─── 1. 文件存在性检查 ─────────────────────────────────────
echo "1. 文件存在性检查"
REQUIRED_FILES=("omni_desk_backend.tar" "omni_desk_frontend.tar" "postgres.tar" "redis.tar" "nginx.tar")

for f in "${REQUIRED_FILES[@]}"; do
    if [ -f "$IMAGE_DIR/$f" ]; then
        result "PASS" "$f exists"
    else
        result "FAIL" "$f missing"
    fi
done
echo ""

# ─── 2. 文件大小检查 ──────────────────────────────────────
echo "2. 文件大小检查"
MIN_SIZES=(
    "omni_desk_backend.tar:50000000"
    "omni_desk_frontend.tar:5000000"
    "postgres.tar:50000000"
    "redis.tar:5000000"
    "nginx.tar:5000000"
)

for entry in "${MIN_SIZES[@]}"; do
    fname="${entry%%:*}"
    min_size="${entry##*:}"
    if [ -f "$IMAGE_DIR/$fname" ]; then
        actual_size=$(stat -c%s "$IMAGE_DIR/$fname" 2>/dev/null || stat -f%z "$IMAGE_DIR/$fname" 2>/dev/null || echo "0")
        if [ "$actual_size" -ge "$min_size" ]; then
            size_mb=$((actual_size / 1024 / 1024))
            result "PASS" "$fname (${size_mb}MB)"
        else
            result "FAIL" "$fname too small (${actual_size} bytes < ${min_size} bytes)"
        fi
    fi
done
echo ""

# ─── 3. Checksum 验证 ─────────────────────────────────────
echo "3. Checksum 验证"
if [ -f "$IMAGE_DIR/checksums.sha256" ]; then
    cd "$IMAGE_DIR"
    if sha256sum -c checksums.sha256 >/dev/null 2>&1; then
        result "PASS" "All checksums match"
    else
        result "FAIL" "Checksum mismatch — files may be corrupted"
    fi
    cd "$COMPOSE_DIR"
else
    result "WARN" "checksums.sha256 not found, skipping"
fi
echo ""

# ─── 4. 构建元数据检查 ─────────────────────────────────────
echo "4. 构建元数据检查"
if [ -f "$IMAGE_DIR/build-manifest.json" ]; then
    result "PASS" "build-manifest.json exists"
    VERSION=$(python3 -c "import json; print(json.load(open('$IMAGE_DIR/build-manifest.json'))['version'])" 2>/dev/null || echo "unknown")
    GIT_SHA=$(python3 -c "import json; print(json.load(open('$IMAGE_DIR/build-manifest.json'))['git_sha'])" 2>/dev/null || echo "unknown")
    BUILD_TIME=$(python3 -c "import json; print(json.load(open('$IMAGE_DIR/build-manifest.json'))['build_time'])" 2>/dev/null || echo "unknown")
    echo "  Version: $VERSION"
    echo "  Git SHA: $GIT_SHA"
    echo "  Built:   $BUILD_TIME"
else
    result "WARN" "build-manifest.json not found"
fi
echo ""

# ─── 5. 镜像可加载性验证 ───────────────────────────────────
echo "5. 镜像可加载性验证"
for tar_file in "$IMAGE_DIR"/*.tar; do
    if [ -f "$tar_file" ]; then
        fname=$(basename "$tar_file")
        if docker load -i "$tar_file" >/dev/null 2>&1; then
            result "PASS" "$fname loads successfully"
        else
            result "FAIL" "$fname cannot be loaded"
        fi
    fi
done
echo ""

# ─── 6. 容器内冒烟验证 ─────────────────────────────────────
echo "6. 容器内冒烟验证"

BACKEND_IMAGE=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "omni-desk-backend-prod" | head -1)
FRONTEND_IMAGE=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "omni-desk-frontend-prod" | head -1)

if [ -n "$BACKEND_IMAGE" ]; then
    if docker run --rm "$BACKEND_IMAGE" python manage.py check --deploy >/dev/null 2>&1; then
        result "PASS" "Backend Django production check"
    else
        result "FAIL" "Backend Django production check"
    fi
else
    result "FAIL" "Backend image not found in local Docker"
fi

if [ -n "$FRONTEND_IMAGE" ]; then
    if docker run --rm "$FRONTEND_IMAGE" nginx -t 2>/dev/null; then
        result "PASS" "Frontend Nginx config test"
    else
        result "FAIL" "Frontend Nginx config test"
    fi
else
    result "FAIL" "Frontend image not found in local Docker"
fi
echo ""

# ─── 总结 ───────────────────────────────────────────────────
echo "=========================================="
echo "  验证结果"
echo "=========================================="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
echo "  WARN: $WARN"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "STATUS: FAILED — 发现 $FAIL 个问题"
    exit 1
elif [ "$WARN" -gt 0 ]; then
    echo "STATUS: PASSED WITH WARNINGS"
    exit 0
else
    echo "STATUS: ALL PASSED"
    exit 0
fi
