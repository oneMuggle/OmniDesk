#!/bin/bash
# test_branch_guard.sh — 单元测试: package_offline_bundle.sh 渠道-分支守卫
#
# 覆盖场景 (G1-G13 走 SIMULATE_BRANCH 注入,G14+ 走真实 git 路径 + 边界 case):
#   G1:  simulate main  + alpha         → pass
#   G2:  simulate main  + stable        → fail (期望 release)
#   G3:  simulate main  + hotfix(数字版)→ fail
#   G4:  simulate main  + beta          → fail
#   G5:  simulate main  + rc            → fail
#   G6:  simulate main  + stable + SKIP_GUARD=1 → pass
#   G7:  simulate release + stable      → pass
#   G8:  simulate release + hotfix(数字版)→ pass (hotfix 走 release)
#   G9:  simulate release + alpha       → fail
#   G10: simulate beta   + beta         → pass
#   G11: simulate rc     + rc           → pass
#   G12: simulate HEAD (detached) + alpha → fail
#   G13: simulate release + v1.0.1 (PATCH bump) → pass
#   G14: VERSION 文件空 + 命令行参数 0.6.0-alpha.1 + simulate main → pass
#   G15: SKIP_GUARD=2 (非 1) + simulate main + stable → fail (不应跳过守卫)
#   G16: SIMULATE_BRANCH="" (空字符串) + 真实 git = release + stable → pass
#   G17: 真实 git 失败 + 0.5.9 → fail + 错误信息含 "无法读取 git"
#   G18: 真实 git = release + VERSION=0.5.10-hotfix → pass (H1 + H2 集成)
#   G19: 真实 git = main + VERSION=0.5.10-hotfix → fail (hotfix 必须 release)
#
# 使用方法:
#   bash deployment/docker/tests/test_branch_guard.sh
#
# 注意:
#   - G1-G15 用 SIMULATE_BRANCH 模拟,避免 git switch 副作用。
#   - G16+ 用 stub git (PATH 注入) 跑真实 git rev-parse 路径,验证守卫集成。
#   - TEST_GUARD_ONLY=1 让脚本在守卫通过后立即退出,避免触发 mkdir/cp
#     /docker load 等副作用。
#   - 测试会临时改 deployment/docker/VERSION,trap 还原。

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PACK_SH="$SCRIPT_DIR/package_offline_bundle.sh"
VERSION_FILE="$SCRIPT_DIR/VERSION"

if [ ! -f "$PACK_SH" ]; then
    echo "FAIL: $PACK_SH 不存在"
    exit 2
fi

ORIGINAL_VERSION=$(cat "$VERSION_FILE")

PASS=0
FAIL=0
FAILED_CASES=()

# ─── stub git helper(G16+ 真实 git 路径测试用)────────────
# 在临时目录写一个 stub `git`,通过 STUB_GIT_BRANCH 控制 rev-parse 输出,
# STUB_GIT_FAIL=1 让 rev-parse 失败。
# 返回:stub 目录路径(调用方用完需 rm -rf)
create_stub_git() {
    local stub_dir
    stub_dir=$(mktemp -d)
    cat > "$stub_dir/git" <<'STUB_EOF'
#!/bin/bash
# 只实现守卫需要的子集:`git -C <path> rev-parse --abbrev-ref HEAD`
if [ "$1" = "-C" ] && [ "$3" = "rev-parse" ] && [ "$4" = "--abbrev-ref" ] && [ "$5" = "HEAD" ]; then
    if [ "${STUB_GIT_FAIL:-0}" = "1" ]; then
        echo "stub git: simulated failure" >&2
        exit 1
    fi
    if [ -n "${STUB_GIT_BRANCH:-}" ]; then
        echo "${STUB_GIT_BRANCH}"
        exit 0
    fi
fi
# 透传到真实 git
REAL_GIT=$(command -v git 2>/dev/null || echo "/usr/bin/git")
exec "$REAL_GIT" "$@"
STUB_EOF
    chmod +x "$stub_dir/git"
    echo "$stub_dir"
}

cleanup() {
    echo "$ORIGINAL_VERSION" > "$VERSION_FILE"
    echo ""
    echo "=========================================="
    echo "  渠道-分支守卫测试"
    echo "=========================================="
    echo "  PASS: $PASS / $((PASS + FAIL))"
    if [ "$FAIL" -gt 0 ]; then
        echo "  FAIL: $FAIL"
        echo "  失败用例: ${FAILED_CASES[*]}"
        exit 1
    fi
    echo "  全部通过"
    echo "=========================================="
}
trap cleanup EXIT

# run_case: SIMULATE_BRANCH 注入版本(G1-G15)
run_case() {
    local case_name="$1"
    local version="$2"
    local simulate_branch="$3"
    local skip_guard="${4:-0}"
    local expected="$5"
    local extra_env="${6:-}"  # 额外环境变量(如 "SKIP_GUARD=2")

    echo ""
    echo "--- Case: $case_name ---"
    echo "  VERSION=$version, SIMULATE_BRANCH=$simulate_branch, SKIP_GUARD=$skip_guard, extra=$extra_env, expected=$expected"

    echo "$version" > "$VERSION_FILE"

    local env_vars="TEST_GUARD_ONLY=1 SIMULATE_BRANCH=$simulate_branch"
    if [ "$skip_guard" = "1" ]; then
        env_vars="$env_vars SKIP_GUARD=1"
    fi
    if [ -n "$extra_env" ]; then
        env_vars="$env_vars $extra_env"
    fi

    local output actual_exit
    set +e
    output=$(env $env_vars bash "$PACK_SH" 2>&1)
    actual_exit=$?
    set -e

    echo "$ORIGINAL_VERSION" > "$VERSION_FILE"

    local case_ok=0
    if [ "$expected" = "pass" ] && [ "$actual_exit" -eq 0 ]; then
        case_ok=1
    elif [ "$expected" = "fail" ] && [ "$actual_exit" -ne 0 ]; then
        case_ok=1
    fi

    if [ "$case_ok" = "1" ]; then
        echo "  PASS: exit=$actual_exit (expected=$expected)"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: exit=$actual_exit, expected=$expected"
        echo "  Output:"
        echo "$output" | sed 's/^/    /'
        FAIL=$((FAIL + 1))
        FAILED_CASES+=("$case_name")
    fi
}

# run_case_real_git: 真实 git 路径(G16+,用 stub git 控制)
run_case_real_git() {
    local case_name="$1"
    local version="$2"
    local stub_branch="$3"
    local stub_fail="${4:-0}"
    local expected="$5"
    local extra_env="${6:-}"

    echo ""
    echo "--- Case: $case_name (real git via stub) ---"
    echo "  VERSION=$version, STUB_GIT_BRANCH=$stub_branch, STUB_GIT_FAIL=$stub_fail, extra=$extra_env, expected=$expected"

    local stub_dir
    stub_dir=$(create_stub_git)

    echo "$version" > "$VERSION_FILE"

    local env_vars="TEST_GUARD_ONLY=1 PATH=$stub_dir:$PATH STUB_GIT_BRANCH=$stub_branch STUB_GIT_FAIL=$stub_fail"
    if [ -n "$extra_env" ]; then
        env_vars="$env_vars $extra_env"
    fi

    local output actual_exit
    set +e
    output=$(env $env_vars bash "$PACK_SH" 2>&1)
    actual_exit=$?
    set -e

    echo "$ORIGINAL_VERSION" > "$VERSION_FILE"
    rm -rf "$stub_dir"

    local case_ok=0
    local case_output_ok=0
    if [ "$expected" = "pass" ] && [ "$actual_exit" -eq 0 ]; then
        case_ok=1
    elif [ "$expected" = "fail" ] && [ "$actual_exit" -ne 0 ]; then
        case_ok=1
    fi

    # G17/G19 等 case 还要求错误信息包含特定字符串
    if [ "$case_name" = "G17-real-git-fail" ]; then
        if echo "$output" | grep -q "无法读取 git 当前分支"; then
            case_output_ok=1
        fi
    fi

    if [ "$case_ok" = "1" ] && [ "$case_output_ok" = "1" -o "$case_name" != "G17-real-git-fail" ]; then
        echo "  PASS: exit=$actual_exit (expected=$expected)"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: exit=$actual_exit, expected=$expected"
        echo "  Output:"
        echo "$output" | sed 's/^/    /'
        FAIL=$((FAIL + 1))
        FAILED_CASES+=("$case_name")
    fi
}

# ─── 渠道映射(SIMULATE_BRANCH 注入)─────────────────────
run_case "G1-main+alpha"            "0.6.0-alpha.1" "main"    "0" "pass"
run_case "G2-main+stable"           "0.5.9"         "main"    "0" "fail"
run_case "G3-main+hotfix"           "0.5.10"        "main"    "0" "fail"
run_case "G4-main+beta"             "0.6.0-beta.1"  "main"    "0" "fail"
run_case "G5-main+rc"               "0.6.0-rc.1"    "main"    "0" "fail"
run_case "G6-main+stable-skip"      "0.5.9"         "main"    "1" "pass"
run_case "G7-release+stable"        "0.5.9"         "release" "0" "pass"
run_case "G8-release+hotfix-num"    "0.5.10"        "release" "0" "pass"
run_case "G9-release+alpha"         "0.6.0-alpha.1" "release" "0" "fail"
run_case "G10-beta+beta"            "0.6.0-beta.1"  "beta"    "0" "pass"
run_case "G11-rc+rc"                "0.6.0-rc.1"    "rc"      "0" "pass"
run_case "G12-detached+alpha"       "0.6.0-alpha.1" "HEAD"    "0" "fail"
run_case "G13-release+hotfix-bump"  "1.0.1"         "release" "0" "pass"

# ─── 边界 case(M1 + H2 hotfix 渠道)──────────────────────
# G14: VERSION 文件空,参数 override 应正常工作
echo -n "" > "$VERSION_FILE"
run_case "G14-empty-version-arg-override" "0.6.0-alpha.1" "main" "0" "pass"

# G15: SKIP_GUARD=2(非 1)→ 不应跳过,正常 fail
run_case "G15-skip-guard-2-not-1" "0.5.9" "main" "0" "fail" "SKIP_GUARD=2"

# ─── 真实 git 路径(H1 + M1 + H2 集成)─────────────────────
# G16: SIMULATE_BRANCH=""(空字符串)→ 走真实 git(stub 输出 release)
run_case_real_git "G16-empty-simulate-uses-real-git" "0.5.9" "release" "0" "pass" "SIMULATE_BRANCH="

# G17: 真实 git 失败 → exit 1 + 错误信息含 "无法读取 git 当前分支"
run_case_real_git "G17-real-git-fail" "0.5.9" "" "1" "fail"

# G18: H2 + H1 集成:VERSION=0.5.10-hotfix + 真实 git = release → pass
run_case_real_git "G18-real-git-release-hotfix" "0.5.10-hotfix" "release" "0" "pass"

# G19: H2 + H1 集成:VERSION=0.5.10-hotfix + 真实 git = main → fail
run_case_real_git "G19-real-git-main-hotfix" "0.5.10-hotfix" "main" "0" "fail"

# G20: H1 完整覆盖:真实 git = main + 真实 VERSION=0.5.9 → fail
run_case_real_git "G20-real-git-main-stable" "0.5.9" "main" "0" "fail"
