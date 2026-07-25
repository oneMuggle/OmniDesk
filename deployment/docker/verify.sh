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
    "scripts/upgrade.sh"
    "scripts/rollback.sh"
    "scripts/backup.sh"
    "scripts/verify.sh"
    "scripts/deploy_offline.sh"
    "scripts/smoke_tests.sh"
    "compose/docker-compose.offline.yml"
    "compose/.env.production.example"
    "config/.env.production.example"
    "VERSION"
    "BUILD-MANIFEST.json"
    "CHECKSUMS.sha256"
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

# 2.4 提示:compose/.env.production 是 deploy 时生成,缺它不代表"包损坏"
# 启动/升级的硬门禁由 deploy_offline.sh / upgrade.sh 自行 require_env_file 检查。
if [ -f "compose/.env.production" ]; then
    echo "  OK: compose/.env.production (已初始化)"
elif [ -f "compose/.env.production.example" ]; then
    echo "  INFO: compose/.env.production 缺失,但 compose/.env.production.example 存在 — 包尚未部署,验证通过"
else
    echo "  WARN: compose/.env.production 缺失且无 example 备份(异常)"
fi

# 2.5 校验固定身份字段(compose 文件 + 至少一个 env 文件必须含)
# 目的:防止打包脚本意外漏掉 ${COMPOSE_PROJECT_NAME} / ${OMNIDESK_*_VOLUME},
# 导致 alpha/beta/rc 多包目录升级时无法复用同一项目/卷 → 孤儿项目/数据遗弃。
# 行为:优先校验 compose/.env.production(已初始化);不存在则校验 compose/.env.production.example。
echo ""
echo "[2.5/3] 校验固定项目/卷身份字段..."

IDENTITY_PATTERNS=(
    "COMPOSE_PROJECT_NAME"
    "OMNIDESK_POSTGRES_VOLUME"
    "OMNIDESK_MEDIA_VOLUME"
)
COMPOSE_FILE="compose/docker-compose.offline.yml"
ENV_FILE="compose/.env.production"
ENV_EXAMPLE_FILE="compose/.env.production.example"
for pattern in "${IDENTITY_PATTERNS[@]}"; do
    compose_ok=0
    env_ok=0
    env_checked="$ENV_FILE"
    # 协调员 Important #2:跳过 YAML / .env 注释行(以 # 开头的行),只匹配"真实声明"。
    # 目的:避免注释里提到 COMPOSE_PROJECT_NAME 时被误判为已配置,
    #       防止打包者误把字段名搬进注释就掩盖了真实声明的缺失。
    if [ -f "$COMPOSE_FILE" ]; then
        compose_real=$(grep -vE '^[[:space:]]*#' "$COMPOSE_FILE" || true)
        if printf '%s\n' "$compose_real" | grep -qE "(^|[^A-Z_])${pattern}([^A-Z_]|$)"; then
            compose_ok=1
        fi
    fi
    if [ -f "$ENV_FILE" ]; then
        env_real=$(grep -vE '^[[:space:]]*#' "$ENV_FILE" || true)
        if printf '%s\n' "$env_real" | grep -qE "^${pattern}="; then
            env_ok=1
        fi
    elif [ -f "$ENV_EXAMPLE_FILE" ]; then
        env_real=$(grep -vE '^[[:space:]]*#' "$ENV_EXAMPLE_FILE" || true)
        if printf '%s\n' "$env_real" | grep -qE "^${pattern}="; then
            env_ok=1
            env_checked="$ENV_EXAMPLE_FILE (fallback,包未部署)"
        fi
    fi
    if [ "$compose_ok" = "1" ] && [ "$env_ok" = "1" ]; then
        echo "  OK: $pattern 在 compose 与 $env_checked 中都已声明(忽略注释行)"
    else
        echo "  MISSING: $pattern (compose_ok=$compose_ok env_ok=$env_ok)"
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
