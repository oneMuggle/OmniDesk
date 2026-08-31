#!/bin/bash
set -uo pipefail

# validate_artifacts.sh — 验证构建产物(.tar 文件)的完整性
# 使用方法:
#   ./validate_artifacts.sh [images_dir]
#   ./validate_artifacts.sh --image-dir <dir> [--manifest <file>] [--checksums <file>]
# 默认检查顺序:显式参数 > bundle images/ > source exported_images/

# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/smoke_common.sh"

# 解析参数,支持位置参数与长选项
IMAGE_DIR=""
MANIFEST_FILE=""
CHECKSUMS_FILE=""
SKIP_CONTAINER_SMOKE=0
while [ $# -gt 0 ]; do
    case "$1" in
        --image-dir) IMAGE_DIR="${2:-}"; shift 2 ;;
        --manifest) MANIFEST_FILE="${2:-}"; shift 2 ;;
        --checksums) CHECKSUMS_FILE="${2:-}"; shift 2 ;;
        --skip-container-smoke) SKIP_CONTAINER_SMOKE=1; shift ;;
        --help|-h) sed -n '2,11p' "$0"; exit 0 ;;
        *)
            # 第一个非选项位置参数作为 IMAGE_DIR
            if [ -z "$IMAGE_DIR" ]; then IMAGE_DIR="$1"; fi; shift ;;
    esac
done

# resolve_artifact_dir 自动在 bundle images/ 与 source exported_images/ 之间选择
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
if [ -z "$IMAGE_DIR" ]; then
    IMAGE_DIR="$(resolve_artifact_dir "" || true)"
    if [ -z "$IMAGE_DIR" ]; then
        echo "ERROR: No image dir given and none found in $BUNDLE_DIR/images or $SCRIPT_DIR/exported_images" >&2
        exit 1
    fi
fi

if [ ! -d "$IMAGE_DIR" ]; then
    echo "ERROR: Directory '$IMAGE_DIR' not found."
    exit 1
fi

# result() 来自 smoke_common.sh(已 export),无需本地定义
export SMOKE_STRICT="${SMOKE_STRICT:-0}"

echo "=========================================="
echo "  构建产物验证"
echo "  目录: $IMAGE_DIR"
echo "=========================================="
echo ""

# ─── 1. 文件存在性检查 ─────────────────────────────────────
echo "1. 文件存在性检查"
REQUIRED_FILES=("omni_desk_backend.tar" "omni_desk_frontend.tar" "postgres-14-alpine.tar" "redis-7-alpine.tar" "nginx-stable-alpine.tar")

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
    "postgres-14-alpine.tar:1000"
    "redis-7-alpine.tar:1000"
    "nginx-stable-alpine.tar:1000"
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
# Step 4(Task 5):checksums.sha256 是 bundle 必备契约,缺失或失配必须 FAIL-closed。
# bundle 标准布局:images/ 下放 .tar,CHECKSUMS.sha256/BUILD-MANIFEST.json 在 bundle 根。
# 先查 IMAGE_DIR(直接参数模式),再查 BUNDLE_DIR(bundle 标准布局),兼容两种打包约定。
echo "3. Checksum 验证"
CHECKSUMS_PATH=""
if [ -n "${CHECKSUMS_FILE:-}" ] && [ -f "$CHECKSUMS_FILE" ]; then
    CHECKSUMS_PATH="$CHECKSUMS_FILE"
elif [ -f "$IMAGE_DIR/CHECKSUMS.sha256" ]; then
    CHECKSUMS_PATH="$IMAGE_DIR/CHECKSUMS.sha256"
elif [ -n "${BUNDLE_DIR:-}" ] && [ -f "$BUNDLE_DIR/CHECKSUMS.sha256" ]; then
    CHECKSUMS_PATH="$BUNDLE_DIR/CHECKSUMS.sha256"
fi
if [ -n "$CHECKSUMS_PATH" ]; then
    CHECKSUMS_DIR="$(dirname "$CHECKSUMS_PATH")"
    cd "$CHECKSUMS_DIR"
    if sha256sum -c CHECKSUMS.sha256 >/dev/null 2>&1; then
        result "PASS" "All checksums match"
    else
        result "FAIL" "Checksum mismatch — files may be corrupted"
    fi
    cd "$SCRIPT_DIR"
else
    result "FAIL" "CHECKSUMS.sha256 missing — bundle 必须包含 checksum 文件"
fi
echo ""

# ─── 4. 构建元数据检查 ─────────────────────────────────────
# Step 4(Task 5):BUILD-MANIFEST.json 是 bundle 必备契约,缺失或字段缺失必须 FAIL-closed。
# 同样支持 IMAGE_DIR 与 BUNDLE_DIR 两种来源。
echo "4. 构建元数据检查"
MANIFEST=""
if [ -n "${MANIFEST_FILE:-}" ] && [ -f "$MANIFEST_FILE" ]; then
    MANIFEST="$MANIFEST_FILE"
elif [ -f "$IMAGE_DIR/BUILD-MANIFEST.json" ]; then
    MANIFEST="$IMAGE_DIR/BUILD-MANIFEST.json"
elif [ -n "${BUNDLE_DIR:-}" ] && [ -f "$BUNDLE_DIR/BUILD-MANIFEST.json" ]; then
    MANIFEST="$BUNDLE_DIR/BUILD-MANIFEST.json"
fi
if [ -n "$MANIFEST" ] && [ -f "$MANIFEST" ]; then
    VERSION=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('version',''))" "$MANIFEST" 2>/dev/null || echo "")
    CHANNEL=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('channel',''))" "$MANIFEST" 2>/dev/null || echo "")
    GIT_SHA=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('git_sha',''))" "$MANIFEST" 2>/dev/null || echo "")
    BUILD_TIME=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('build_time',''))" "$MANIFEST" 2>/dev/null || echo "")
    BACKEND_NAME=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('images',{}).get('backend',{}).get('name',''))" "$MANIFEST" 2>/dev/null || echo "")
    BACKEND_DIGEST=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('images',{}).get('backend',{}).get('digest',''))" "$MANIFEST" 2>/dev/null || echo "")
    FRONTEND_NAME=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('images',{}).get('frontend',{}).get('name',''))" "$MANIFEST" 2>/dev/null || echo "")
    FRONTEND_DIGEST=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('images',{}).get('frontend',{}).get('digest',''))" "$MANIFEST" 2>/dev/null || echo "")
    MISSING=""
    [ -z "$VERSION" ] && MISSING="$MISSING version"
    [ -z "$CHANNEL" ] && MISSING="$MISSING channel"
    [ -z "$GIT_SHA" ] && MISSING="$MISSING git_sha"
    [ -z "$BUILD_TIME" ] && MISSING="$MISSING build_time"
    [ -z "$BACKEND_NAME" ] && MISSING="$MISSING images.backend.name"
    [ -z "$BACKEND_DIGEST" ] && MISSING="$MISSING images.backend.digest"
    [ -z "$FRONTEND_NAME" ] && MISSING="$MISSING images.frontend.name"
    [ -z "$FRONTEND_DIGEST" ] && MISSING="$MISSING images.frontend.digest"
    if [ -n "$MISSING" ]; then
        result "FAIL" "BUILD-MANIFEST.json missing fields:$MISSING"
    else
        result "PASS" "BUILD-MANIFEST.json fields complete"
        echo "  Version:    $VERSION"
        echo "  Channel:    $CHANNEL"
        echo "  Git SHA:    $GIT_SHA"
        echo "  Built:      $BUILD_TIME"
        echo "  Backend:    $BACKEND_NAME @ ${BACKEND_DIGEST:0:19}..."
        echo "  Frontend:   $FRONTEND_NAME @ ${FRONTEND_DIGEST:0:19}..."
    fi
else
    result "FAIL" "BUILD-MANIFEST.json missing — bundle 必须包含构建清单"
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
if [ "$SKIP_CONTAINER_SMOKE" -eq 1 ]; then
    echo "6. 容器内冒烟验证"
    echo "  SKIP: container smoke explicitly disabled (artifact-only fixture)"
else
    echo "6. 容器内冒烟验证"

    BACKEND_IMAGE=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "omni-desk-backend-prod" | head -1)
    FRONTEND_IMAGE=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "omni-desk-frontend-prod" | head -1)

    if [ -n "$BACKEND_IMAGE" ]; then
        # 使用 --entrypoint 绕过 entrypoint.sh 的数据库等待
        if docker run --rm --entrypoint bash \
            "$BACKEND_IMAGE" -c "
            test -f manage.py && \
            python -c 'import django; import psycopg2; import celery; import gunicorn; print(\"All dependencies OK\")'
            " >/dev/null 2>&1; then
            result "PASS" "Backend dependencies verified"
        else
            result "FAIL" "Backend dependency check failed"
        fi
    else
        result "FAIL" "Backend image not found in local Docker"
    fi

    if [ -n "$FRONTEND_IMAGE" ]; then
        # nginx -t 需要 upstream 解析，这里只验证配置文件存在
        if docker run --rm --entrypoint sh "$FRONTEND_IMAGE" -c "test -f /etc/nginx/conf.d/default.conf && test -d /usr/share/nginx/html" 2>/dev/null; then
            result "PASS" "Frontend Nginx config and static files present"
        else
            result "FAIL" "Frontend Nginx config test"
        fi
    else
        result "FAIL" "Frontend image not found in local Docker"
    fi
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
