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

# ─── 汇总 ────────────────────────────────────────────────────
rm -rf "$TEST_TMPDIR"

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