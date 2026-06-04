#!/bin/bash
set -e

# verify.sh — 离线部署介质完整性校验
# 使用方法: 将本脚本放入离线包根目录后执行 ./verify.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# 脚本位于 scripts/ 子目录，需 cd 到离线包根目录
cd "$SCRIPT_DIR/.."

echo "=========================================="
echo "  离线部署介质完整性校验"
echo "=========================================="
echo ""

ERRORS=0

# 1. 校验 SHA256 checksums
if [ -f "CHECKSUMS.sha256" ]; then
    echo "[1/3] 校验 SHA256 checksums..."
    if sha256sum -c CHECKSUMS.sha256 2>/dev/null; then
        echo "  PASS: 所有文件 checksum 校验通过"
    else
        echo "  FAIL: checksum 校验失败，文件可能已损坏"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "  WARN: CHECKSUMS.sha256 不存在，跳过 checksum 校验"
fi

# 2. 校验必需文件存在
echo ""
echo "[2/3] 校验必需文件..."
REQUIRED_FILES=(
    "images/omni_desk_backend.tar"
    "images/omni_desk_frontend.tar"
    "images/postgres-14-alpine.tar"
    "images/redis-7-alpine.tar"
    "images/nginx-stable-alpine.tar"
    "scripts/deploy.sh"
    "compose/docker-compose.offline.yml"
    "config/.env.production.example"
    "VERSION"
    "BUILD-MANIFEST.json"
)

for f in "${REQUIRED_FILES[@]}"; do
    if [ -f "$f" ]; then
        SIZE=$(du -h "$f" | cut -f1)
        echo "  OK: $f ($SIZE)"
    else
        echo "  MISSING: $f"
        ERRORS=$((ERRORS + 1))
    fi
done

# 3. 校验镜像文件大小（合理性检查）
echo ""
echo "[3/3] 校验镜像大小合理性..."

BACKEND_TAR="images/omni_desk_backend.tar"
FRONTEND_TAR="images/omni_desk_frontend.tar"

if [ -f "$BACKEND_TAR" ]; then
    BACKEND_SIZE=$(stat -c%s "$BACKEND_TAR" 2>/dev/null || stat -f%z "$BACKEND_TAR" 2>/dev/null || echo "0")
    BACKEND_MB=$((BACKEND_SIZE / 1024 / 1024))
    if [ "$BACKEND_MB" -lt 50 ]; then
        echo "  WARN: 后端镜像过小 (${BACKEND_MB}MB)，可能不完整"
        ERRORS=$((ERRORS + 1))
    else
        echo "  OK: 后端镜像 ${BACKEND_MB}MB"
    fi
fi

if [ -f "$FRONTEND_TAR" ]; then
    FRONTEND_SIZE=$(stat -c%s "$FRONTEND_TAR" 2>/dev/null || stat -f%z "$FRONTEND_TAR" 2>/dev/null || echo "0")
    FRONTEND_MB=$((FRONTEND_SIZE / 1024 / 1024))
    if [ "$FRONTEND_MB" -lt 10 ]; then
        echo "  WARN: 前端镜像过小 (${FRONTEND_MB}MB)，可能不完整"
        ERRORS=$((ERRORS + 1))
    else
        echo "  OK: 前端镜像 ${FRONTEND_MB}MB"
    fi
fi

# 总结
echo ""
echo "=========================================="
if [ "$ERRORS" -eq 0 ]; then
    echo "  校验通过：所有检查项均通过"
    echo "  可安全执行部署：./scripts/deploy.sh start"
else
    echo "  校验失败：$ERRORS 项检查未通过"
    echo "  请勿部署，重新获取完整的离线包"
fi
echo "=========================================="

exit $ERRORS
