#!/usr/bin/env bash
# test_offline_bundle_layout.sh — 单元测试: 离线包脚本布局 + 固定身份变量
#
# 覆盖目标(Task 1 brief):
#   - package_offline_bundle.sh 同时复制 upgrade.sh(以及 rollback/backup/verify)
#   - bundle 的 compose/docker-compose.offline.yml 含固定项目/卷身份:
#     COMPOSE_PROJECT_NAME / OMNIDESK_POSTGRES_VOLUME / OMNIDESK_MEDIA_VOLUME
#   - verify.sh 在 bundle 根目录下能成功校验这些脚本存在
#
# 使用方法:
#   bash deployment/docker/tests/test_offline_bundle_layout.sh
#
# 注意:
#   - 测试构造一个最小 bundle(只复制脚本和 compose),不复制镜像,
#     所以跳过 verify.sh 里的镜像大小合理性检查(脚本自带容错,缺失就跳过该 case)。
#   - assertion helpers 在文件内 inline 定义,不依赖外部 test_helpers.sh,
#     以严格遵守 task brief 的"Files"清单(只动 6 个文件)。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACK_SH="$ROOT/package_offline_bundle.sh"
VERIFY_SH="$ROOT/verify.sh"
COMPOSE_FILE_SRC="$ROOT/docker-compose.offline.yml"
ENV_EXAMPLE_SRC="$ROOT/.env.production.example"

# ─── 内联 assertion helpers(避免引用不存在的 test_helpers.sh)─────
PASS_COUNT=0
FAIL_COUNT=0
FAILED_CASES=()

pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS: $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); FAILED_CASES+=("$1"); echo "  FAIL: $1"; }

assert_file_exists() {
    local f="$1"
    if [ -f "$f" ]; then
        pass "file exists: $f"
    else
        fail "file exists: $f (MISSING)"
    fi
}

assert_contains() {
    local f="$1" pattern="$2"
    if [ ! -f "$f" ]; then
        fail "assert_contains: file missing: $f"
        return
    fi
    if grep -qE "$pattern" "$f"; then
        pass "contains '$pattern' in $f"
    else
        fail "contains '$pattern' in $f (NOT FOUND)"
    fi
}

# ─── 主测试 ──────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  离线包布局 + 固定身份变量测试"
echo "=========================================="

# 1. 源码文件本身存在
assert_file_exists "$PACK_SH"
assert_file_exists "$VERIFY_SH"
assert_file_exists "$COMPOSE_FILE_SRC"
assert_file_exists "$ENV_EXAMPLE_SRC"

# 2. 构造最小 bundle(模拟 package_offline_bundle.sh 的关键复制动作)
#    真实脚本会执行 mkdir -p "$BUNDLE_DIR/scripts" 和 "$BUNDLE_DIR/compose" 并 cp 各脚本,
#    这里手动模拟一遍,验证:
#      - scripts/upgrade.sh、rollback.sh、backup.sh、verify.sh 都存在
#      - compose/docker-compose.offline.yml 含 3 个固定身份字段
#      - verify.sh 接收 bundle 根目录并能解析出 scripts/verify.sh 等关键路径
TEST_TMPDIR="$(mktemp -d)"
bundle="$TEST_TMPDIR/bundle"
mkdir -p "$bundle/scripts" "$bundle/compose" "$bundle/images" "$bundle/config"

# 模拟 package_offline_bundle.sh 复制 upgrade.sh(关键缺失项)
# (rollback/backup/verify 已在原脚本里复制)
cp "$ROOT/upgrade.sh"     "$bundle/scripts/upgrade.sh"
cp "$ROOT/rollback.sh"    "$bundle/scripts/rollback.sh"
cp "$ROOT/backup.sh"      "$bundle/scripts/backup.sh"
cp "$ROOT/verify.sh"      "$bundle/scripts/verify.sh"
# Step 3(Task 5):补齐 smoke_common.sh / deploy_tests.sh / validate_artifacts.sh(verify.sh 强制要求)
[ -f "$ROOT/smoke_common.sh" ]    && cp "$ROOT/smoke_common.sh"    "$bundle/scripts/smoke_common.sh"
[ -f "$ROOT/deploy_tests.sh" ]    && cp "$ROOT/deploy_tests.sh"    "$bundle/scripts/deploy_tests.sh"
[ -f "$ROOT/validate_artifacts.sh" ] && cp "$ROOT/validate_artifacts.sh" "$bundle/scripts/validate_artifacts.sh"
[ -f "$ROOT/verify_backup_batch.sh" ] && cp "$ROOT/verify_backup_batch.sh" "$bundle/scripts/verify_backup_batch.sh"
cp "$COMPOSE_FILE_SRC"    "$bundle/compose/docker-compose.offline.yml"

# 写入 VERSION 与 BUILD-MANIFEST.json(verify.sh 要求)
echo "0.7.0-rc.1" > "$bundle/VERSION"
cat > "$bundle/BUILD-MANIFEST.json" <<EOF
{
  "version": "0.7.0-rc.1",
  "channel": "preview"
}
EOF

# 3. 校验 bundle 内 scripts/upgrade.sh 等脚本存在
assert_file_exists "$bundle/scripts/upgrade.sh"
assert_file_exists "$bundle/scripts/rollback.sh"
assert_file_exists "$bundle/scripts/backup.sh"
assert_file_exists "$bundle/scripts/verify.sh"
assert_file_exists "$bundle/compose/docker-compose.offline.yml"

# 4. 校验 compose 文件含固定身份字段
#    (这三个字段名是 Task 1 brief 强制要求,即使将来可能改名也要保留)
assert_contains "$bundle/compose/docker-compose.offline.yml" 'COMPOSE_PROJECT_NAME'
assert_contains "$bundle/compose/docker-compose.offline.yml" 'OMNIDESK_POSTGRES_VOLUME'
assert_contains "$bundle/compose/docker-compose.offline.yml" 'OMNIDESK_MEDIA_VOLUME'

# 5. 校验 .env.production.example 含同源变量(渠道模板)
assert_contains "$ENV_EXAMPLE_SRC" 'COMPOSE_PROJECT_NAME'
assert_contains "$ENV_EXAMPLE_SRC" 'OMNIDESK_POSTGRES_VOLUME'
assert_contains "$ENV_EXAMPLE_SRC" 'OMNIDESK_MEDIA_VOLUME'

# 6. 跨目录复用核心断言:
#    把同一 .env.production 拷到两个不同 bundle 目录,各自解析后项目名/卷名必须一致
bundle_a="$TEST_TMPDIR/bundleA/compose"
bundle_b="$TEST_TMPDIR/bundleB/compose"
mkdir -p "$bundle_a" "$bundle_b"

cat > "$bundle_a/.env.production" <<EOF
CHANNEL=rc
COMPOSE_PROJECT_NAME=omnidesk-rc
OMNIDESK_POSTGRES_VOLUME=omnidesk-rc-postgres-data
OMNIDESK_MEDIA_VOLUME=omnidesk-rc-media-data
BACKEND_IMAGE_TAG=v0.7.0-rc.1
FRONTEND_IMAGE_TAG=v0.7.0-rc.1
POSTGRES_DB=test
POSTGRES_USER=u
POSTGRES_PASSWORD=p
SECRET_KEY=k
REDIS_PASSWORD=r
EOF
cp "$bundle_a/.env.production" "$bundle_b/.env.production"

# 把 compose 文件同样放到两个目录里
cp "$bundle/compose/docker-compose.offline.yml" "$bundle_a/docker-compose.offline.yml"
cp "$bundle/compose/docker-compose.offline.yml" "$bundle_b/docker-compose.offline.yml"

# 用 docker compose config 解析两次,验证项目名/卷名跨目录一致
# 注:docker compose --name 不存在;项目名走 YAML 顶层的 `name:` 字段,
# 用 `config` 渲染后由 grep ^name: 提取。
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    # 解析两次,提取 project name(top-level `name: ...` 行)
    rendered_a=$(cd "$bundle_a" && docker compose -f docker-compose.offline.yml --env-file .env.production config 2>/dev/null || true)
    rendered_b=$(cd "$bundle_b" && docker compose -f docker-compose.offline.yml --env-file .env.production config 2>/dev/null || true)

    name_a=$(echo "$rendered_a" | awk '/^name: / {print $2; exit}')
    name_b=$(echo "$rendered_b" | awk '/^name: / {print $2; exit}')
    if [ -n "$name_a" ] && [ "$name_a" = "$name_b" ]; then
        pass "compose project name 跨目录一致: $name_a"
    else
        fail "compose project name 跨目录不一致: a=[$name_a] b=[$name_b]"
    fi

    # 解析两个 bundle 的 volumes,确认同名
    vols_a=$(echo "$rendered_a" | awk '/^  [a-z_]+:$/ && !/networks/ {print $1}' | sort)
    vols_b=$(echo "$rendered_b" | awk '/^  [a-z_]+:$/ && !/networks/ {print $1}' | sort)
    if [ "$vols_a" = "$vols_b" ] && [ -n "$vols_a" ]; then
        pass "compose volumes 跨目录一致: $(echo "$vols_a" | tr '\n' ' ')"
    else
        fail "compose volumes 跨目录不一致: a=[$vols_a] b=[$vols_b]"
    fi

    # 检查 volumes 是 explicit name(满足"固定卷名"要求)
    # volumes: 段下每个卷应有一个 `name:` 行;docker compose 渲染时
    # 自动用 project_name 前缀(`omnidesk-rc_postgres_data`)→ 验证 prefix 锁定。
    volume_names=$(echo "$rendered_a" | awk '/^  [a-z_]+:$/ && !/networks/ && !/services/ {name=$1; getline; if ($1 == "name:") print $2}')
    if echo "$volume_names" | grep -E '^omnidesk-rc(_|-)' >/dev/null; then
        pass "compose volume 用了 project-name 前缀的固定 name: $(echo "$volume_names" | tr '\n' ' ')"
    else
        fail "compose volume 缺固定 name: 行(brief 要求 external/固定 name,实际=$volume_names)"
    fi
else
    echo "  SKIP: docker compose 不可用,跳过跨目录解析断言"
fi

# 7. 协调员 follow-up 要求:验证新的"example fallback"门禁行为
#    - bundle 必须含 compose/.env.production.example
#    - 在未初始化(compose/.env.production 缺失)时,verify.sh 应通过(用 example)
#    - package_offline_bundle.sh 应同时把 example 拷到 config/ 和 compose/ 两个目录
assert_file_exists "$ENV_EXAMPLE_SRC"

# 构造"未初始化"bundle(只有 .example,没有 .env.production)模拟刚解压的状态
uninit_bundle="$TEST_TMPDIR/uninit_bundle"
mkdir -p "$uninit_bundle/scripts" "$uninit_bundle/compose" "$uninit_bundle/images" "$uninit_bundle/config"
cp "$ROOT/upgrade.sh"   "$uninit_bundle/scripts/upgrade.sh"
cp "$ROOT/rollback.sh"  "$uninit_bundle/scripts/rollback.sh"
cp "$ROOT/backup.sh"    "$uninit_bundle/scripts/backup.sh"
cp "$ROOT/verify.sh"    "$uninit_bundle/scripts/verify.sh"
cp "$ROOT/deploy_offline.sh" "$uninit_bundle/scripts/deploy_offline.sh"
cp "$ROOT/smoke_tests.sh"    "$uninit_bundle/scripts/smoke_tests.sh"
cp "$ROOT/upgrade_state.sh"  "$uninit_bundle/scripts/upgrade_state.sh"
# Step 3(Task 5):uninit bundle 也必须含 smoke_common.sh / deploy_tests.sh / validate_artifacts.sh
[ -f "$ROOT/smoke_common.sh" ]    && cp "$ROOT/smoke_common.sh"    "$uninit_bundle/scripts/smoke_common.sh"
[ -f "$ROOT/deploy_tests.sh" ]    && cp "$ROOT/deploy_tests.sh"    "$uninit_bundle/scripts/deploy_tests.sh"
[ -f "$ROOT/validate_artifacts.sh" ] && cp "$ROOT/validate_artifacts.sh" "$uninit_bundle/scripts/validate_artifacts.sh"
[ -f "$ROOT/test_helpers.sh" ] && cp "$ROOT/test_helpers.sh" "$uninit_bundle/scripts/test_helpers.sh"
[ -f "$ROOT/verify_backup_batch.sh" ] && cp "$ROOT/verify_backup_batch.sh" "$uninit_bundle/scripts/verify_backup_batch.sh"
[ -d "$ROOT/tests" ] && cp -r "$ROOT/tests" "$uninit_bundle/scripts/tests"
# scripts/deploy.sh 由 package_offline_bundle.sh 内联生成,不来自源码;
# 这里用 stub 占位(空脚本但存在)模拟打包后的产物。
cat > "$uninit_bundle/scripts/deploy.sh" <<'STUB_DEPLOY_EOF'
#!/bin/bash
# stub deploy.sh — 占位符,verify.sh 只检查存在性,不执行
echo "stub deploy"
STUB_DEPLOY_EOF
chmod +x "$uninit_bundle/scripts/deploy.sh"
cp "$COMPOSE_FILE_SRC"  "$uninit_bundle/compose/docker-compose.offline.yml"
cp "$ENV_EXAMPLE_SRC"   "$uninit_bundle/compose/.env.production.example"
cp "$ENV_EXAMPLE_SRC"   "$uninit_bundle/config/.env.production.example"
echo "0.7.0-rc.1" > "$uninit_bundle/VERSION"
echo '{}' > "$uninit_bundle/BUILD-MANIFEST.json"
# 生成 CHECKSUMS.sha256(空 sha256 即可,verify.sh 只校验空文件集的 checksum)
(cd "$uninit_bundle" && find . -type f ! -name 'CHECKSUMS.sha256' -exec sha256sum {} + > CHECKSUMS.sha256)
# 注意:不创建 compose/.env.production — 这是"未初始化 bundle"的关键标志

# 模拟 package_offline_bundle.sh 的镜像复制(verify.sh [3/3] 段会校验大小,
# 留 0 字节会被判"镜像过小" → 模拟真实 bundle 给镜像灌入合法大小)
dd if=/dev/zero of="$uninit_bundle/images/omni_desk_backend.tar" bs=1M count=60 2>/dev/null
dd if=/dev/zero of="$uninit_bundle/images/omni_desk_frontend.tar" bs=1M count=15 2>/dev/null
dd if=/dev/zero of="$uninit_bundle/images/postgres-14-alpine.tar" bs=1M count=80 2>/dev/null
dd if=/dev/zero of="$uninit_bundle/images/redis-7-alpine.tar" bs=1M count=15 2>/dev/null
dd if=/dev/zero of="$uninit_bundle/images/nginx-stable-alpine.tar" bs=1M count=30 2>/dev/null

# 7.1 compose/.env.production.example 必须存在
assert_file_exists "$uninit_bundle/compose/.env.production.example"

# 7.2 config/.env.production.example 也存在(双重备份)
assert_file_exists "$uninit_bundle/config/.env.production.example"

# 7.3 在未初始化 bundle 上运行 verify.sh 应通过(用 example fallback,不报 .env.production 缺失)
#    用 `|| true` 让 set -e 在 verify.sh 退非零时不杀进程,以便我们捕获退出码再断言。
set +e
verify_output=$(cd "$uninit_bundle" && bash scripts/verify.sh 2>&1)
verify_rc=$?
set -e
if [ "$verify_rc" -eq 0 ]; then
    pass "verify.sh 在未初始化 bundle 上通过(example fallback): exit=$verify_rc"
else
    fail "verify.sh 在未初始化 bundle 上失败: exit=$verify_rc"
    echo "$verify_output" | sed 's/^/    /'
fi

# 7.4 verify.sh 的输出应包含"example"提示(让用户知道发生了什么)
if echo "$verify_output" | grep -qE 'example|未初始化|已初始化'; then
    pass "verify.sh 输出包含 example 提示"
else
    fail "verify.sh 输出缺少 example 相关提示"
fi

# 7.5 启动/升级硬门禁:必须仍要求真实 .env.production
#    - deploy_offline.sh 用 require_env_file 函数
#    - upgrade.sh / rollback.sh 各自 inline 检查 [ -f $ENV_FILE_PATH ]
#    任一脚本丢掉门禁都会让"未初始化"包绕过安全检查。
if grep -q 'require_env_file' "$ROOT/deploy_offline.sh"; then
    pass "deploy_offline.sh 仍使用 require_env_file 硬要求实际 .env.production"
else
    fail "deploy_offline.sh 丢了 require_env_file 调用,启动/升级会失去门禁"
fi
if grep -qE '\[ ! -f "\$ENV_FILE_PATH" \]' "$ROOT/upgrade.sh"; then
    pass "upgrade.sh 仍硬要求 ENV_FILE_PATH 实际存在"
else
    fail "upgrade.sh 丢了硬门禁,升级可能在未部署包上误跑"
fi
if grep -qE '\[ ! -f "\$ENV_FILE_PATH" \]' "$ROOT/rollback.sh"; then
    pass "rollback.sh 仍硬要求 ENV_FILE_PATH 实际存在"
else
    fail "rollback.sh 丢了硬门禁,回滚可能在未部署包上误跑"
fi

# 8. 协调员 Important #1:真实调用 package_offline_bundle.sh(避免手工 cp 掩盖打包回退)
#    把整个 deployment/docker/ 脚本树复制到临时 SRC,真实运行 SKIP_GUARD=1 跳过
#    渠道-分支守卫,触发真实拷贝/IMAGE_TAG_SED/sed/CHECKSUMS 等流程,验证产出。
REAL_PACK_SRC="$(mktemp -d)/pack_src"
mkdir -p "$REAL_PACK_SRC"
cp "$ROOT/package_offline_bundle.sh" "$REAL_PACK_SRC/"
cp "$ROOT/upgrade.sh"             "$REAL_PACK_SRC/"
cp "$ROOT/rollback.sh"            "$REAL_PACK_SRC/"
cp "$ROOT/backup.sh"              "$REAL_PACK_SRC/"
cp "$ROOT/verify.sh"              "$REAL_PACK_SRC/"
cp "$ROOT/deploy_offline.sh"      "$REAL_PACK_SRC/"
cp "$ROOT/smoke_tests.sh"         "$REAL_PACK_SRC/"
cp "$ROOT/smoke_common.sh"        "$REAL_PACK_SRC/"
cp "$ROOT/deploy_tests.sh"        "$REAL_PACK_SRC/"
cp "$ROOT/validate_artifacts.sh"  "$REAL_PACK_SRC/"
cp "$ROOT/upgrade_state.sh"       "$REAL_PACK_SRC/"
[ -f "$ROOT/test_helpers.sh" ] && cp "$ROOT/test_helpers.sh" "$REAL_PACK_SRC/"
[ -f "$ROOT/verify_backup_batch.sh" ] && cp "$ROOT/verify_backup_batch.sh" "$REAL_PACK_SRC/"
[ -d "$ROOT/tests" ] && cp -r "$ROOT/tests" "$REAL_PACK_SRC/tests"
cp "$ROOT/docker-compose.offline.yml" "$REAL_PACK_SRC/"
cp "$ROOT/.env.production.example"     "$REAL_PACK_SRC/"
echo "0.7.0-rc.1" > "$REAL_PACK_SRC/VERSION"

# 占位 exported_images/(backend/frontend .tar),让脚本走"导出存在"路径而不触发 docker save
mkdir -p "$REAL_PACK_SRC/exported_images"
# 创建 fake tars:让 verify.sh [3/3] 体积阈值通过(backend>=50MB, frontend>=10MB);
# 同时给 base images(postgres/redis/nginx)也建空文件,避免 package_offline_bundle.sh
# 走到 docker save 分支却没产物。
dd if=/dev/zero of="$REAL_PACK_SRC/exported_images/omni_desk_backend.tar" bs=1M count=60 2>/dev/null
dd if=/dev/zero of="$REAL_PACK_SRC/exported_images/omni_desk_frontend.tar" bs=1M count=15 2>/dev/null
touch "$REAL_PACK_SRC/exported_images/postgres-14-alpine.tar"
touch "$REAL_PACK_SRC/exported_images/redis-7-alpine.tar"
touch "$REAL_PACK_SRC/exported_images/nginx-stable-alpine.tar"

# IMPORTANT:零字节/随机字节不是合法 docker image,`docker load -q -i` 会非零退出,
# 由于 package_offline_bundle.sh 顶部 set -e 会让脚本在此处 abort(并跳过 CHECKSUMS 与 README 的生成)。
# 用 stub docker 让 `load` 和 `images` 都返回 0/空输出,允许脚本继续。
DOCKER_STUB_DIR="$(mktemp -d)"
cat > "$DOCKER_STUB_DIR/docker" <<'STUB_EOF'
#!/bin/bash
# 简化版 docker stub:只让 package_offline_bundle.sh 的 load/images/inspect 走通。
# 其它子命令透传给真实 docker。
case "$1" in
    load)
        # load:不真正解析,直接 exit 0
        exit 0
        ;;
    images)
        # images --format:返回空(让 BACKEND_INFO / FRONTEND_INFO 为空,走 fallback 分支)
        exit 0
        ;;
    image)
        # docker image inspect:return 0 让脚本以为镜像存在
        exit 0
        ;;
    save)
        exit 0
        ;;
    *)
        # 透传给真实 docker
        exec /usr/bin/docker "$@"
        ;;
esac
STUB_EOF
chmod +x "$DOCKER_STUB_DIR/docker"
# 极简 BUILD-MANIFEST.json(脚本会优先 cp 它;docker load 路径 2>/dev/null 容错)
echo '{"version":"0.7.0-rc.1","channel":"preview"}' > "$REAL_PACK_SRC/exported_images/build-manifest.json"

real_pack_log="$(mktemp)"
set +e
# PATH = stub docker + 真实命令,让 docker load/images/save/inspect 走 stub(避免零字节 tar 让脚本 abort)
( cd "$REAL_PACK_SRC" && PATH="$DOCKER_STUB_DIR:$PATH" SKIP_GUARD=1 bash package_offline_bundle.sh 0.7.0-rc.1 ) >"$real_pack_log" 2>&1
real_pack_rc=$?
set -e

REAL_BUNDLE="$REAL_PACK_SRC/omnidesk-offline-rc-v0.7.0-rc.1"
if [ -d "$REAL_BUNDLE" ]; then
    pass "真实 package_offline_bundle.sh 产出存在: $REAL_BUNDLE (rc=$real_pack_rc)"
else
    fail "真实 package_offline_bundle.sh 没有产出 omnidesk-offline-rc-v0.7.0-rc.1/"
    echo "      --- package_offline_bundle.sh 日志 ---"
    sed 's/^/        /' "$real_pack_log"
fi

# 8.1 真实 bundle 含全部 brief 要求脚本
for s in deploy upgrade rollback backup verify deploy_offline smoke_tests verify_backup_batch; do
    if [ -f "$REAL_BUNDLE/scripts/${s}.sh" ]; then
        pass "real bundle 含 scripts/${s}.sh"
    else
        fail "real bundle 缺 scripts/${s}.sh"
    fi
done

# 8.2 真实 bundle 含 compose/docker-compose.offline.yml + compose/.env.production.example(Round 2)
assert_file_exists "$REAL_BUNDLE/compose/docker-compose.offline.yml"
assert_file_exists "$REAL_BUNDLE/compose/.env.production.example"

# 8.3 真实 bundle 不应预生成 compose/.env.production(由 deploy.sh start 生成)
if [ ! -f "$REAL_BUNDLE/compose/.env.production" ]; then
    pass "real bundle 未预生成 compose/.env.production(应 deploy 时生成)"
else
    fail "real bundle 错误地预生成了 compose/.env.production"
fi

# 8.4 real bundle VERSION 与 BUILD-MANIFEST.json
[ -f "$REAL_BUNDLE/VERSION" ] && pass "real bundle 含 VERSION" || fail "real bundle 缺 VERSION"
[ -f "$REAL_BUNDLE/BUILD-MANIFEST.json" ] && pass "real bundle 含 BUILD-MANIFEST.json" || fail "real bundle 缺 BUILD-MANIFEST.json"

# 8.5 真实 bundle 中 IMAGE_TAG 已被 sed 重写为 v0.7.0-rc.1(避免手工 cp 漏改)
if grep -qE 'BACKEND_IMAGE_TAG:-v0\.7\.0-rc\.1|FRONTEND_IMAGE_TAG:-v0\.7\.0-rc\.1' "$REAL_BUNDLE/compose/docker-compose.offline.yml"; then
    pass "real bundle sed 已把 IMAGE_TAG fallback 改成 v0.7.0-rc.1"
else
    fail "real bundle IMAGE_TAG 未被 sed 重写(还停留在原 fallback 值)"
fi

# 8.6 真实 bundle 上 verify.sh 应 exit 0(完整 bundle,镜像体积 WARN 不计 ERRORS)
set +e
( cd "$REAL_BUNDLE" && bash scripts/verify.sh >/dev/null 2>&1 )
real_verify_rc=$?
set -e
if [ "$real_verify_rc" = "0" ]; then
    pass "verify.sh 在 real bundle 上 exit 0(完整产物合格)"
else
    fail "verify.sh 在 real bundle 上 exit=$real_verify_rc"
fi

# 8.7 real bundle 内 upgrade.sh / rollback.sh 能 bash -n 通过(确认真实拷到了内容,
#     而不是空文件 — 后者在 hero scenarios 中常被静默忽略)
bash -n "$REAL_BUNDLE/scripts/upgrade.sh" 2>/dev/null && pass "real bundle upgrade.sh bash -n OK"  || fail "real bundle upgrade.sh bash -n FAIL"
bash -n "$REAL_BUNDLE/scripts/rollback.sh" 2>/dev/null && pass "real bundle rollback.sh bash -n OK" || fail "real bundle rollback.sh bash -n FAIL"
# P1-#12:验证 bundle 内的 verify_backup_batch.sh 不仅是占位文件,还能 bash 语法通过
bash -n "$REAL_BUNDLE/scripts/verify_backup_batch.sh" 2>/dev/null && pass "real bundle verify_backup_batch.sh bash -n OK" || fail "real bundle verify_backup_batch.sh bash -n FAIL"

# 9. 协调员 Important #2:verify.sh 注释行过滤 + 真实声明匹配
#    构造一个 example 文件,故意把字段名写在注释行 → 应被识别为"未声明"。
fake_compose="$(mktemp)"
cat > "$fake_compose" <<'EOF'
# 警告:COMPOSE_PROJECT_NAME 必须显式提供,但本测试故意把它只写在注释里
# COMPOSE_PROJECT_NAME=should-not-count
name: ${COMPOSE_PROJECT_NAME}
services:
  db:
    image: postgres:14-alpine
EOF
# 把 verify.sh 的核心匹配逻辑内联到本测试(因为涉及临时文件解析,不易直接 source)
fake_filter() {
    local file="$1" pattern="$2"
    local filtered
    filtered=$(grep -vE '^[[:space:]]*#' "$file" || true)
    if printf '%s\n' "$filtered" | grep -qE "(^|[^A-Z_])${pattern}([^A-Z_]|$)"; then
        return 0
    else
        return 1
    fi
}
if fake_filter "$fake_compose" 'COMPOSE_PROJECT_NAME'; then
    # 真有 `name: ${COMPOSE_PROJECT_NAME}` 声明,所以应匹配 — OK
    pass "verify.sh 注释过滤后仍能匹配真实声明(name: \${COMPOSE_PROJECT_NAME})"
else
    fail "verify.sh 注释过滤误杀真实声明"
fi

# 现在去掉 name: 那行,只留注释
fake_compose2="$(mktemp)"
cat > "$fake_compose2" <<'EOF'
# COMPOSE_PROJECT_NAME=only-in-comment
services:
  db:
    image: postgres:14-alpine
EOF
if fake_filter "$fake_compose2" 'COMPOSE_PROJECT_NAME'; then
    fail "verify.sh 注释过滤失效:注释行被当作真实声明"
else
    pass "verify.sh 注释过滤生效:仅注释时不匹配"
fi
rm -f "$fake_compose" "$fake_compose2"

# 9.2 同步校验 verify.sh 源代码确实包含注释过滤行(防回退)
if grep -q 'grep -vE' "$ROOT/verify.sh"; then
    pass "verify.sh 源码包含 grep -vE 注释过滤(Implementation)未回退"
else
    fail "verify.sh 源码丢了 grep -vE 注释过滤(实现回退)"
fi

# 10. 协调员 Important #3:compose name 字段使用硬门禁(:?),不应回退到目录名
#     在临时 bundle 中去掉 COMPOSE_PROJECT_NAME 让 docker compose config 解析,期望失败。
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    tmp_d="$TEST_TMPDIR/hard_gate"
    mkdir -p "$tmp_d/compose"
    cp "$REAL_BUNDLE/compose/docker-compose.offline.yml" "$tmp_d/compose/"
    # 写一个故意不带 COMPOSE_PROJECT_NAME 的 env
    cat > "$tmp_d/.env.production" <<'EOF'
POSTGRES_DB=test
POSTGRES_USER=u
POSTGRES_PASSWORD=p
SECRET_KEY=k
REDIS_PASSWORD=r
BACKEND_IMAGE_TAG=v0.7.0-rc.1
FRONTEND_IMAGE_TAG=v0.7.0-rc.1
EOF
    set +e
    ( cd "$tmp_d" && docker compose -f compose/docker-compose.offline.yml --env-file .env.production config >/dev/null 2>&1 )
    hard_rc=$?
    set -e
    if [ "$hard_rc" != "0" ]; then
        pass "缺 COMPOSE_PROJECT_NAME 时 docker compose config 拒绝(:? 硬门禁生效,rc=$hard_rc)"
    else
        fail "缺 COMPOSE_PROJECT_NAME 时 compose 仍通过 — name 字段缺硬门禁(回退到目录名)"
    fi
fi

# 10.2 源码层面:compose 文件第 1 处 `name:` 行必须包含 `:?` 硬门禁
if grep -E '^name:.*:?[A-Z]' "$COMPOSE_FILE_SRC" >/dev/null; then
    if grep -E '^name: \$\{COMPOSE_PROJECT_NAME:\?' "$COMPOSE_FILE_SRC" >/dev/null; then
        pass "compose name 字段使用 :? 硬门禁"
    else
        fail "compose name 字段没有 :? 硬门禁 — 没设默认会回退到目录名"
    fi
else
    fail "compose 缺顶层 name: 字段"
fi

# ─── 汇总 ────────────────────────────────────────────────────
# 清理所有 mktemp 临时目录(包括 real pack 测试创建的独立 mktemp -d,以及 docker stub)
rm -rf "$TEST_TMPDIR" "$(dirname "$REAL_PACK_SRC")" /tmp/pack_src "$DOCKER_STUB_DIR" 2>/dev/null || true

echo ""
echo "=========================================="
echo "  PASS: $PASS_COUNT"
echo "  FAIL: $FAIL_COUNT"
if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "  Failed cases: ${FAILED_CASES[*]}"
    exit 1
fi
echo "  全部通过"
echo "=========================================="
exit 0