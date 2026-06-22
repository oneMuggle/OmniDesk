#!/bin/bash
set -e

# package_offline_bundle.sh — 将构建产物打包为标准离线部署介质
# 使用方法: ./package_offline_bundle.sh [version]
# version 从 VERSION 文件读取，也可通过参数覆盖

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ─── 版本 ────────────────────────────────────────────────────
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

if ! echo "$BUILD_VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "ERROR: Invalid version format '$BUILD_VERSION'. Use semantic versioning (MAJOR.MINOR.PATCH)."
    exit 1
fi

BUNDLE_DIR="omnidesk-offline-v${BUILD_VERSION}"
EXPORT_DIR="exported_images"

echo "=========================================="
echo "  打包离线部署介质 v${BUILD_VERSION}"
echo "=========================================="
echo ""

# ─── 清理旧包 ───────────────────────────────────────────────
if [ -d "$BUNDLE_DIR" ]; then
    echo "清理旧的打包目录: $BUNDLE_DIR"
    rm -rf "$BUNDLE_DIR"
fi

# ─── 创建目录结构 ───────────────────────────────────────────
echo "创建目录结构..."
mkdir -p "$BUNDLE_DIR/images"
mkdir -p "$BUNDLE_DIR/scripts"
mkdir -p "$BUNDLE_DIR/compose"
mkdir -p "$BUNDLE_DIR/config"

# ─── 复制镜像 ───────────────────────────────────────────────
echo "复制 Docker 镜像..."

# 应用镜像（从 exported_images 复制）
for tar in omni_desk_backend.tar omni_desk_frontend.tar; do
    if [ -f "$EXPORT_DIR/$tar" ]; then
        cp "$EXPORT_DIR/$tar" "$BUNDLE_DIR/images/"
        echo "  OK: $tar"
    else
        echo "  WARN: $EXPORT_DIR/$tar not found"
    fi
done

# 基础镜像（优先从 exported_images 取，不存在则从本地导出）
# 使用并行数组兼容 sh/bash
BASE_IMAGE_NAMES="postgres-14-alpine.tar redis-7-alpine.tar nginx-stable-alpine.tar"
BASE_IMAGE_TAGS="postgres:14-alpine redis:7-alpine nginx:stable-alpine"

base_image_idx=0
for name in $BASE_IMAGE_NAMES; do
    # 获取对应的 tag
    IMAGE=""
    current_idx=0
    for tag in $BASE_IMAGE_TAGS; do
        if [ "$current_idx" -eq "$base_image_idx" ]; then
            IMAGE="$tag"
            break
        fi
        current_idx=$((current_idx + 1))
    done

    if [ -f "$EXPORT_DIR/$name" ]; then
        cp "$EXPORT_DIR/$name" "$BUNDLE_DIR/images/"
        echo "  OK: $name (from exported_images)"
    else
        if docker image inspect "$IMAGE" >/dev/null 2>&1; then
            echo "  Exporting: $IMAGE -> $name"
            docker save -o "$BUNDLE_DIR/images/$name" "$IMAGE"
        else
            echo "  MISSING: $IMAGE not found locally"
        fi
    fi
    base_image_idx=$((base_image_idx + 1))
done

# Fix ownership on all exported .tar files
CURRENT_USER=$(whoami)
CURRENT_GROUP=$(id -gn)
echo "Fixing file ownership to ${CURRENT_USER}:${CURRENT_GROUP}..."
chown "${CURRENT_USER}:${CURRENT_GROUP}" "$BUNDLE_DIR/images/"*.tar 2>/dev/null || true

# ─── 复制脚本 ───────────────────────────────────────────────
echo "复制部署脚本..."

# 创建离线包入口 deploy.sh
cat > "$BUNDLE_DIR/scripts/deploy.sh" << 'DEPLOY_EOF'
#!/bin/bash
set -e

# deploy.sh — 离线包一键部署入口
# 使用方法: ./deploy.sh {start|stop|status|logs|exec|migrate}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$BUNDLE_DIR"

# ─── 加载镜像 ───────────────────────────────────────────────
load_images() {
    echo "加载 Docker 镜像..."
    for tar_file in images/*.tar; do
        if [ -f "$tar_file" ]; then
            echo "  加载: $(basename "$tar_file")"
            docker load -i "$tar_file" || echo "    WARN: failed to load $tar_file"
        fi
    done
    echo "镜像加载完成。"

    # 同步 GHCR 命名,使 compose 文件中的 ghcr.io/onemuggle/* 镜像引用能找到本地 tag
    # (docker load 后镜像以源名 omni-desk-*-prod:vX.Y.Z 存在,需 alias 到 ghcr.io 全名)
    local version
    version=$(cat VERSION 2>/dev/null | tr -d '[:space:]' || echo "")
    if [ -n "$version" ]; then
        echo "同步 GHCR 镜像命名 (v${version})..."
        docker tag "omni-desk-backend-prod:v${version}"  "ghcr.io/onemuggle/omni-desk-backend:v${version}"  2>/dev/null \
            && echo "  tagged: ghcr.io/onemuggle/omni-desk-backend:v${version}" \
            || echo "  WARN: backend retag 失败 (源镜像可能不存在)"
        docker tag "omni-desk-frontend-prod:v${version}" "ghcr.io/onemuggle/omni-desk-frontend:v${version}" 2>/dev/null \
            && echo "  tagged: ghcr.io/onemuggle/omni-desk-frontend:v${version}" \
            || echo "  WARN: frontend retag 失败 (源镜像可能不存在)"
    else
        echo "WARN: VERSION 文件缺失或为空,跳过 GHCR 镜像重命名"
    fi
}

# ─── 生成 .env.production ──────────────────────────────────
generate_env() {
    if [ -f "config/.env.production" ]; then
        echo ".env.production 已存在，使用现有配置。"
        cp config/.env.production compose/.env.production
        return
    fi

    if [ ! -f "config/.env.production.example" ]; then
        echo "ERROR: config/.env.production.example 不存在"
        exit 1
    fi

    echo "从模板生成 .env.production..."
    cp config/.env.production.example compose/.env.production

    # 自动生成密钥
    if command -v python3 >/dev/null 2>&1; then
        python3 -c "
import secrets, re
with open('compose/.env.production', 'r') as f:
    content = f.read()
content = re.sub(r'<GENERATE-NEW-SECRET-KEY>', secrets.token_urlsafe(50), content)
content = re.sub(r'<CHANGE-TO-STRONG-PASSWORD>', secrets.token_urlsafe(20), content)
with open('compose/.env.production', 'w') as f:
    f.write(content)
"
        echo ".env.production 已生成（含随机密钥）。"
    else
        echo "WARNING: python3 not found. Using template with placeholders."
        echo "请手动编辑 compose/.env.production 替换所有 <...> 占位符。"
    fi
}

# ─── 等待服务健康 ───────────────────────────────────────────
wait_for_healthy() {
    local max_wait="${1:-120}"
    local interval=5
    local elapsed=0

    echo "等待服务就绪（最多 ${max_wait}s）..."
    while [ "$elapsed" -lt "$max_wait" ]; do
        all_healthy=true
        for service in db redis backend frontend worker; do
            CONTAINER_ID=$(docker compose -f compose/docker-compose.offline.yml --env-file compose/.env.production ps -q "$service" 2>/dev/null || true)
            if [ -n "$CONTAINER_ID" ]; then
                HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}starting{{end}}' "$CONTAINER_ID" 2>/dev/null || echo "unknown")
                if [ "$HEALTH" != "healthy" ]; then
                    all_healthy=false
                fi
            else
                all_healthy=false
            fi
        done
        if [ "$all_healthy" = true ]; then
            echo "所有服务已就绪（等待 ${elapsed}s）。"
            return 0
        fi
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done
    echo "WARNING: 部分服务未就绪（已等待 ${max_wait}s）。"
    echo "使用 ./deploy.sh logs 查看日志。"
    return 1
}

# ─── 冒烟测试 ───────────────────────────────────────────────
smoke_test() {
    echo "运行冒烟测试..."
    sleep 5

    if command -v curl >/dev/null 2>&1; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ]; then
            echo "  PASS: 前端 HTTP 200"
        else
            echo "  WARN: 前端 HTTP $HTTP_CODE（可能正在启动）"
        fi
    fi

    if command -v curl >/dev/null 2>&1; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/health/ 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ]; then
            echo "  PASS: 后端 API 健康"
        else
            echo "  WARN: 后端 API HTTP $HTTP_CODE"
        fi
    fi
}

# ─── 主命令 ─────────────────────────────────────────────────
case "${1:-start}" in
    start)
        echo "=========================================="
        echo "  OmniDesk 离线部署"
        echo "=========================================="
        echo ""

        # 第一步：校验
        if [ -f "scripts/verify.sh" ]; then
            bash scripts/verify.sh || exit 1
        fi

        # 第二步：加载镜像
        load_images

        # 第三步：生成环境配置
        generate_env

        # 第四步：启动服务
        echo ""
        echo "启动服务..."
        docker compose -f compose/docker-compose.offline.yml --env-file compose/.env.production up -d

        # 第五步：等待健康
        wait_for_healthy 120 || true

        # 第六步：冒烟测试
        smoke_test

        echo ""
        echo "=========================================="
        echo "  部署完成"
        echo "=========================================="
        echo ""
        echo "访问地址: http://localhost"
        echo ""
        echo "首次部署请执行："
        echo "  ./deploy.sh exec backend python manage.py migrate"
        echo "  ./deploy.sh exec backend python manage.py collectstatic --noinput"
        echo "  ./deploy.sh exec backend python manage.py createsuperuser"
        ;;
    stop)
        echo "停止服务..."
        docker compose -f compose/docker-compose.offline.yml --env-file compose/.env.production down
        echo "服务已停止。"
        ;;
    status)
        docker compose -f compose/docker-compose.offline.yml --env-file compose/.env.production ps
        ;;
    logs)
        docker compose -f compose/docker-compose.offline.yml --env-file compose/.env.production logs -f "${@:2}"
        ;;
    exec)
        shift
        docker compose -f compose/docker-compose.offline.yml --env-file compose/.env.production exec "$@"
        ;;
    migrate)
        echo "执行数据库迁移..."
        docker compose -f compose/docker-compose.offline.yml --env-file compose/.env.production exec -T backend python manage.py migrate
        echo "迁移完成。"
        ;;
    verify)
        if [ -f "scripts/verify.sh" ]; then
            bash scripts/verify.sh
        else
            echo "verify.sh 不存在"
        fi
        ;;
    *)
        echo "使用方法: ./deploy.sh {start|stop|status|logs|exec|migrate|verify}"
        ;;
esac
DEPLOY_EOF

chmod +x "$BUNDLE_DIR/scripts/deploy.sh"
echo "  OK: deploy.sh"

# 复制 verify.sh
cp "$SCRIPT_DIR/verify.sh" "$BUNDLE_DIR/scripts/"
echo "  OK: verify.sh"

# 复制 rollback.sh 和 backup.sh（如果存在）
for script in rollback.sh backup.sh; do
    if [ -f "$SCRIPT_DIR/$script" ]; then
        cp "$SCRIPT_DIR/$script" "$BUNDLE_DIR/scripts/"
        chmod +x "$BUNDLE_DIR/scripts/$script"
        echo "  OK: $script"
    fi
done

# ─── 复制 compose 配置 ─────────────────────────────────────
echo "复制 docker-compose 配置..."
cp "$SCRIPT_DIR/docker-compose.offline.yml" "$BUNDLE_DIR/compose/docker-compose.offline.yml"
# 用 sed 把 bundle 内 compose 文件的 IMAGE_TAG default fallback 替换为当前构建版本
# (源文件保持 v0.4.0 不动,只让 bundle 副本与本次构建版本对齐)
sed -i "s/BACKEND_IMAGE_TAG:-v[0-9]*\.[0-9]*\.[0-9]*/BACKEND_IMAGE_TAG:-v${BUILD_VERSION}/" "$BUNDLE_DIR/compose/docker-compose.offline.yml"
sed -i "s/FRONTEND_IMAGE_TAG:-v[0-9]*\.[0-9]*\.[0-9]*/FRONTEND_IMAGE_TAG:-v${BUILD_VERSION}/" "$BUNDLE_DIR/compose/docker-compose.offline.yml"
echo "  OK: docker-compose.offline.yml (IMAGE_TAG fallback → v${BUILD_VERSION})"

# ─── 复制配置模板 ──────────────────────────────────────────
echo "复制配置模板..."
if [ -f "$SCRIPT_DIR/.env.production.example" ]; then
    cp "$SCRIPT_DIR/.env.production.example" "$BUNDLE_DIR/config/"
    # 用 sed 把 bundle 内 example env 的 IMAGE_TAG 默认值替换为当前构建版本
    sed -i "s/^BACKEND_IMAGE_TAG=v[0-9]*\.[0-9]*\.[0-9]*/BACKEND_IMAGE_TAG=v${BUILD_VERSION}/" "$BUNDLE_DIR/config/.env.production.example"
    sed -i "s/^FRONTEND_IMAGE_TAG=v[0-9]*\.[0-9]*\.[0-9]*/FRONTEND_IMAGE_TAG=v${BUILD_VERSION}/" "$BUNDLE_DIR/config/.env.production.example"
    echo "  OK: .env.production.example (IMAGE_TAG → v${BUILD_VERSION})"
else
    echo "  WARN: .env.production.example 不存在,跳过配置模板复制"
fi

# 复制 nginx.conf
if [ -f "../../omni_desk_frontend/nginx.conf" ]; then
    cp "../../omni_desk_frontend/nginx.conf" "$BUNDLE_DIR/config/"
    echo "  OK: nginx.conf"
fi

# ─── 复制版本和元数据 ──────────────────────────────────────
echo "复制版本和元数据..."
echo "$BUILD_VERSION" > "$BUNDLE_DIR/VERSION"
echo "  OK: VERSION"

if [ -f "$EXPORT_DIR/build-manifest.json" ]; then
    cp "$EXPORT_DIR/build-manifest.json" "$BUNDLE_DIR/BUILD-MANIFEST.json"
    echo "  OK: BUILD-MANIFEST.json"
else
    GIT_SHA=$(git -C "$SCRIPT_DIR/../.." rev-parse --short HEAD 2>/dev/null || echo "unknown")
    BUILD_TIME=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    cat > "$BUNDLE_DIR/BUILD-MANIFEST.json" << EOF
{
  "version": "$BUILD_VERSION",
  "build_time": "$BUILD_TIME",
  "git_sha": "$GIT_SHA"
}
EOF
    echo "  OK: BUILD-MANIFEST.json (generated)"
fi

# ─── 生成 README ────────────────────────────────────────────
echo "生成部署说明..."
cat > "$BUNDLE_DIR/README.md" << EOF
# OmniDesk 离线部署包

## 快速开始

1. **校验完整性**
   \`\`\`bash
   ./scripts/verify.sh
   \`\`\`

2. **一键部署**
   \`\`\`bash
   ./scripts/deploy.sh start
   \`\`\`

3. **首次部署初始化**
   \`\`\`bash
   ./scripts/deploy.sh exec backend python manage.py migrate
   ./scripts/deploy.sh exec backend python manage.py collectstatic --noinput
   ./scripts/deploy.sh exec backend python manage.py createsuperuser
   \`\`\`

4. **访问系统**
   浏览器打开 http://localhost

## 常用命令

| 命令 | 说明 |
|------|------|
| \`./scripts/deploy.sh start\` | 启动服务 |
| \`./scripts/deploy.sh stop\` | 停止服务 |
| \`./scripts/deploy.sh status\` | 查看服务状态 |
| \`./scripts/deploy.sh logs\` | 查看日志 |
| \`./scripts/deploy.sh migrate\` | 数据库迁移 |
| \`./scripts/deploy.sh verify\` | 校验文件完整性 |

## 系统要求

- Docker 20.10+
- Docker Compose v2
- Linux amd64 (x86_64)
- 至少 4GB 内存
- 至少 10GB 磁盘空间

## 客户端兼容性

- Windows 7: Chrome 109 / Edge 109
- Windows 10/11: Chrome / Edge / Firefox
- Linux: Chrome / Firefox
- **不支持 IE11**
EOF

echo "  OK: README.md"

# ─── 生成 checksum ─────────────────────────────────────────
echo "生成 SHA256 checksums..."
cd "$BUNDLE_DIR"
find . -type f ! -name 'CHECKSUMS.sha256' -exec sha256sum {} + > CHECKSUMS.sha256
cd "$SCRIPT_DIR"
echo "  OK: CHECKSUMS.sha256"

# ─── 计算总大小 ─────────────────────────────────────────────
TOTAL_SIZE=$(du -sh "$BUNDLE_DIR" | cut -f1)

# ─── 完成 ───────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  打包完成 v${BUILD_VERSION}"
echo "=========================================="
echo ""
echo "离线包位置: $BUNDLE_DIR/"
echo "总大小: $TOTAL_SIZE"
echo ""
echo "传输到目标服务器后执行："
echo "  cd $BUNDLE_DIR && ./scripts/deploy.sh start"
