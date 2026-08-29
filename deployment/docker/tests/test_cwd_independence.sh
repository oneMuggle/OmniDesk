#!/usr/bin/env bash
# test_cwd_independence.sh — 回归测试:离线包/源码树脚本从任意 cwd 都能定位文件
#
# 覆盖目标(P1 阶段 brief 第 1 项):
#   "先补源码树与 bundle 两种布局下从任意工作目录执行的路径回归测试"
#
# 假设/约束:
#   1. 离线包布局:bundle/{compose/,scripts/,images/,CHECKSUMS.sha256,BUILD-MANIFEST.json,...}
#   2. 源码树布局:deployment/docker/ 直接含 docker-compose.offline.yml
#   3. 脚本必须用 `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"` 推导自身位置,
#      不能依赖调用者 cwd。
#   4. 探测手法:每个支持 --help 的脚本,exit 0/1 + 输出 "Usage:";
#      这允许在没 Docker、没真实镜像、没真实部署的状态下,
#      仍然穿过布局检测 + env 硬门禁两个高风险路径。
#
# 用法:
#   bash deployment/docker/tests/test_cwd_independence.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 内联 assertion helpers(避免与 test_helpers.sh 循环依赖)
PASS_COUNT=0
FAIL_COUNT=0
FAILED_CASES=()

pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS: $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); FAILED_CASES+=("$1"); echo "  FAIL: $1"; }

# ─── 探测:从任意 cwd 执行脚本 --help,验证"Usage:"出现 + 无 env 错误 ───
# 接受 rc=0 或 rc=1:
#   - rc=0:rollback.sh / upgrade.sh / validate_artifacts.sh (top-level --help 处理器)
#   - rc=1:deploy_offline.sh (top-level 默认 * 路径,exits 1 with Usage:)
# 关键反断言:输出中不能含 env.production 错误信息(意味着布局检测失败)
assert_help_probe() {
    local layout="$1" script_name="$2" cwd_label="$3"
    local script_path="$4" cwd="$5"
    shift 5
    local help_args=("$@")  # e.g. ("--help") 或 ("clean" "--help")

    local output rc
    set +e
    output=$(cd "$cwd" && bash "$script_path" "${help_args[@]}" 2>&1)
    rc=$?
    set -e

    # Usage: 或 使用方法: 都算通过(validate_artifacts.sh 用中文)
    if echo "$output" | grep -qE 'Usage:|使用方法:'; then
        pass "[$layout/$script_name/$cwd_label] 布局检测成功(Usage: 已输出)"
    else
        fail "[$layout/$script_name/$cwd_label] 未输出 Usage: → 布局检测可能失败"
        echo "$output" | sed 's/^/        /'
        return
    fi

    # 反断言:不能因为 .env.production 缺失而退出(说明 cd 错了目录)
    if echo "$output" | grep -qE 'env.production not found|env.production 不存在|必须在已部署的实例上运行'; then
        fail "[$layout/$script_name/$cwd_label] 触发了 env 错误 → 布局检测失败"
        echo "$output" | sed 's/^/        /'
    fi

    # rc 应在 [0, 1] 之间(0=top-level --help handler;1=default case)
    if [ "$rc" -ne 0 ] && [ "$rc" -ne 1 ]; then
        fail "[$layout/$script_name/$cwd_label] 异常退出码 rc=$rc(期望 0 或 1)"
    fi
}

assert_verify_success() {
    local layout="$1" cwd_label="$2"
    local bundle="$3"
    local cwd="$4"

    local rc
    set +e
    (cd "$cwd" && bash "$bundle/scripts/verify.sh" >/dev/null 2>&1)
    rc=$?
    set -e

    if [ "$rc" -eq 0 ]; then
        pass "[$layout/verify.sh/$cwd_label] exit 0(完整 bundle 跨 cwd 验证)"
    else
        fail "[$layout/verify.sh/$cwd_label] exit=$rc(期望 0)"
    fi
}

# ─── 测试目录 ──────────────────────────────────────────────────
TMPDIR_BASE="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_BASE"' EXIT

NESTED_DIR="$TMPDIR_BASE/a/b/c/e"
mkdir -p "$NESTED_DIR"

# 4 个测试 cwd(避免依赖 $HOME 真实路径,用我们建的固定子目录替代)
TEST_CWDS=(
    "/"
    "/tmp"
    "$TMPDIR_BASE"
    "$NESTED_DIR"
)
CWD_LABELS=(
    "root"
    "tmp"
    "tmproot"
    "nested"
)

# ─── 构造 source tree fixture ──────────────────────────────────
SRC_TREE="$TMPDIR_BASE/src_tree"
mkdir -p "$SRC_TREE"
# 把核心脚本拷过去,保证 source tree 布局自包含
SCRIPTS_TO_COPY=(
    deploy_offline.sh rollback.sh upgrade.sh backup.sh
    smoke_tests.sh smoke_common.sh
    verify.sh validate_artifacts.sh deploy_tests.sh
    verify_backup_batch.sh upgrade_state.sh test_helpers.sh
)
for s in "${SCRIPTS_TO_COPY[@]}"; do
    [ -f "$ROOT/$s" ] && cp "$ROOT/$s" "$SRC_TREE/$s"
done
# source tree 的 compose 文件必须与脚本同级
[ -f "$ROOT/docker-compose.offline.yml" ] && cp "$ROOT/docker-compose.offline.yml" "$SRC_TREE/docker-compose.offline.yml"
[ -f "$ROOT/.env.production.example" ] && cp "$ROOT/.env.production.example" "$SRC_TREE/.env.production.example"
# 写一个真实的 .env.production 让硬门禁通过(source tree 的 .env.production 与脚本同级)
cat > "$SRC_TREE/.env.production" <<EOF
CHANNEL=stable
COMPOSE_PROJECT_NAME=omnidesk-cwd-test
OMNIDESK_POSTGRES_VOLUME=omnidesk-cwd-test-postgres
OMNIDESK_MEDIA_VOLUME=omnidesk-cwd-test-media
BACKEND_IMAGE_TAG=v0.7.0
FRONTEND_IMAGE_TAG=v0.7.0
POSTGRES_DB=test
POSTGRES_USER=u
POSTGRES_PASSWORD=p
SECRET_KEY=k
REDIS_PASSWORD=r
EOF

# ─── 构造 bundle fixture(扁平 bundle 根目录)────────────────────
BUNDLE="$TMPDIR_BASE/bundle"
mkdir -p "$BUNDLE/scripts" "$BUNDLE/compose" "$BUNDLE/images" "$BUNDLE/config"

for s in "${SCRIPTS_TO_COPY[@]}"; do
    [ -f "$ROOT/$s" ] && cp "$ROOT/$s" "$BUNDLE/scripts/$s"
done
# deploy.sh 由 package_offline_bundle.sh 内联生成,这里 stub 一个保证 verify.sh 必需文件存在
cat > "$BUNDLE/scripts/deploy.sh" <<'STUB_DEPLOY_EOF'
#!/bin/bash
# stub deploy.sh — verify.sh 只检查存在性,不执行
echo "stub deploy"
STUB_DEPLOY_EOF
chmod +x "$BUNDLE/scripts/deploy.sh"

# tests/ 子目录(verify.sh 要求 scripts/tests/test_upgrade_state.sh)
# 注意:不要 mkdir scripts/tests/ 然后 cp -r,会让路径变成 scripts/tests/tests/
[ -d "$ROOT/tests" ] && cp -r "$ROOT/tests" "$BUNDLE/scripts/tests"

[ -f "$ROOT/docker-compose.offline.yml" ] && cp "$ROOT/docker-compose.offline.yml" "$BUNDLE/compose/docker-compose.offline.yml"
[ -f "$ROOT/.env.production.example" ] && cp "$ROOT/.env.production.example" "$BUNDLE/compose/.env.production.example"
[ -f "$ROOT/.env.production.example" ] && cp "$ROOT/.env.production.example" "$BUNDLE/config/.env.production.example"
# bundle 内的 .env.production(模拟"已部署"状态,让硬门禁通过)
cat > "$BUNDLE/compose/.env.production" <<EOF
CHANNEL=stable
COMPOSE_PROJECT_NAME=omnidesk-cwd-test
OMNIDESK_POSTGRES_VOLUME=omnidesk-cwd-test-postgres
OMNIDESK_MEDIA_VOLUME=omnidesk-cwd-test-media
BACKEND_IMAGE_TAG=v0.7.0
FRONTEND_IMAGE_TAG=v0.7.0
POSTGRES_DB=test
POSTGRES_USER=u
POSTGRES_PASSWORD=p
SECRET_KEY=k
REDIS_PASSWORD=r
EOF
echo "0.7.0" > "$BUNDLE/VERSION"
echo '{"version":"0.7.0","channel":"stable"}' > "$BUNDLE/BUILD-MANIFEST.json"
# 镜像 placeholder(达到 verify.sh 体积阈值)
dd if=/dev/zero of="$BUNDLE/images/omni_desk_backend.tar"  bs=1M count=60 2>/dev/null
dd if=/dev/zero of="$BUNDLE/images/omni_desk_frontend.tar" bs=1M count=15 2>/dev/null
dd if=/dev/zero of="$BUNDLE/images/postgres-14-alpine.tar" bs=1M count=80 2>/dev/null
dd if=/dev/zero of="$BUNDLE/images/redis-7-alpine.tar"     bs=1M count=15 2>/dev/null
dd if=/dev/zero of="$BUNDLE/images/nginx-stable-alpine.tar" bs=1M count=30 2>/dev/null
# CHECKSUMS.sha256(对所有非 CHECKSUMS 文件生成)
(cd "$BUNDLE" && find . -type f ! -name 'CHECKSUMS.sha256' -exec sha256sum {} + > CHECKSUMS.sha256)

# ─── 主测试矩阵 ───────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  CWD 独立性回归测试(source tree × bundle)"
echo "=========================================="

# 有 top-level --help(退出码 0)
# rollback.sh: line 64-67  -h|--help) echo "Usage:"; exit 0
# upgrade.sh: line 286-287 -h|--help) echo "Usage:"; exit 0
# validate_artifacts.sh: line 21 --help|-h) sed -n '2,11p' "$0"; exit 0
TOP_LEVEL_HELP_SCRIPTS=(rollback.sh upgrade.sh validate_artifacts.sh)
for s in "${TOP_LEVEL_HELP_SCRIPTS[@]}"; do
    for layout in src bundle; do
        if [ "$layout" = "src" ]; then
            script_path="$SRC_TREE/$s"
        else
            script_path="$BUNDLE/scripts/$s"
        fi
        if [ ! -f "$script_path" ]; then
            echo "  SKIP: [$layout/$s] 副本不存在"
            continue
        fi
        for i in 0 1 2 3; do
            assert_help_probe "$layout" "$s" "${CWD_LABELS[$i]}" "$script_path" "${TEST_CWDS[$i]}" --help
        done
    done
done

# deploy_offline.sh: --help 只在 `clean` 子命令里(exit 0)
# top-level --help 落到默认 * case(exit 1 + "Usage:")
# 用 "clean --help" 让所有路径走布局检测 + env 硬门禁
for layout in src bundle; do
    if [ "$layout" = "src" ]; then
        script_path="$SRC_TREE/deploy_offline.sh"
    else
        script_path="$BUNDLE/scripts/deploy_offline.sh"
    fi
    if [ ! -f "$script_path" ]; then
        echo "  SKIP: [$layout/deploy_offline.sh] 副本不存在"
        continue
    fi
    for i in 0 1 2 3; do
        assert_help_probe "$layout" "deploy_offline.sh" "${CWD_LABELS[$i]}" "$script_path" "${TEST_CWDS[$i]}" "clean" "--help"
    done
done

# backup.sh: 没有 --help,任何调用都直接调 docker compose。
# 用静态反向断言 + bash -n 语法检查覆盖,不进入 runtime 矩阵。
echo ""
echo "[backup.sh 静态检查(无 --help 探针,绕过 Docker 依赖)]"
for layout in src bundle; do
    if [ "$layout" = "src" ]; then
        script_path="$SRC_TREE/backup.sh"
    else
        script_path="$BUNDLE/scripts/backup.sh"
    fi
    if [ ! -f "$script_path" ]; then
        echo "  SKIP: [$layout/backup.sh] 副本不存在"
        continue
    fi
    if bash -n "$script_path" 2>/dev/null; then
        pass "[$layout/backup.sh] bash -n 语法通过(布局检测代码完整)"
    else
        fail "[$layout/backup.sh] bash -n 失败"
    fi
done

# verify.sh: 在合法 bundle 上应 exit 0,无论 cwd 在哪
# (verify.sh 自带 `cd SCRIPT_DIR/..`,理论上 cwd 无影响,
#  但我们要确认它不依赖任何遗留的 $PWD 路径。)
echo ""
echo "[verify.sh 跨 cwd 验证]"
for i in 0 1 2 3; do
    assert_verify_success "bundle" "${CWD_LABELS[$i]}" "$BUNDLE" "${TEST_CWDS[$i]}"
done

# ─── 静态反向断言:每个脚本必须用 SCRIPT_DIR="$(cd ... && pwd)" 推导 ───
# 目的:防止后人误把 `SCRIPT_DIR=$PWD` 之类引入导致 cwd 依赖回归。
echo ""
echo "[静态 SCRIPT_DIR 推导检查]"
ALL_SCRIPTS=(deploy_offline.sh rollback.sh upgrade.sh backup.sh validate_artifacts.sh)
for s in "${ALL_SCRIPTS[@]}"; do
    src="$ROOT/$s"
    if [ ! -f "$src" ]; then
        echo "  SKIP: $s (源码不存在)"
        continue
    fi
    if grep -qE 'SCRIPT_DIR="\$\(cd "\$\(dirname "\$0"\)" && pwd\)"' "$src"; then
        pass "$s 使用 SCRIPT_DIR=\"\$(cd \"\$(dirname \"\$0\")\" && pwd)\" 推导"
    else
        fail "$s 缺规范的 SCRIPT_DIR 推导,可能存在 cwd 依赖"
    fi
done

# ─── 反向断言:不能用 PWD 推导 SCRIPT_DIR ──────────────────────
# (排除注释行,排除"$SCRIPT_DIR_ENV" 类似变量名)
echo ""
echo "[静态反断言:不能用 PWD 推导]"
for s in "${ALL_SCRIPTS[@]}"; do
    src="$ROOT/$s"
    if [ ! -f "$src" ]; then
        echo "  SKIP: $s (源码不存在)"
        continue
    fi
    if grep -vE '^[[:space:]]*#' "$src" | grep -qE '^\s*SCRIPT_DIR="?\$\{?PWD\}?"?\s*$'; then
        fail "$s 含 PWD 推导 SCRIPT_DIR — 会引入 cwd 依赖"
    else
        pass "$s 未使用 PWD 推导 SCRIPT_DIR(无 cwd 依赖)"
    fi
done

# ─── 汇总 ────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  PASS: $PASS_COUNT"
echo "  FAIL: $FAIL_COUNT"
if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "  失败用例:"
    for c in "${FAILED_CASES[@]}"; do
        echo "    - $c"
    done
    exit 1
fi
echo "  全部通过"
echo "=========================================="
exit 0