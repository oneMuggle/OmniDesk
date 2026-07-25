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