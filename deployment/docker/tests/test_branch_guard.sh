#!/bin/bash
# test_branch_guard.sh — 单元测试: package_offline_bundle.sh 渠道-分支守卫
#
# 覆盖场景:
#   G1:  simulate main  + alpha    → 守卫通过
#   G2:  simulate main  + stable   → 守卫拒绝 (期望 release)
#   G3:  simulate main  + hotfix   → 守卫拒绝 (期望 release)
#   G4:  simulate main  + beta     → 守卫拒绝
#   G5:  simulate main  + rc       → 守卫拒绝
#   G6:  simulate main  + stable + SKIP_GUARD=1 → 跳过守卫 (WARN)
#   G7:  simulate release + stable → 守卫通过
#   G8:  simulate release + hotfix → 守卫通过 (hotfix 走 release 分支)
#   G9:  simulate release + alpha  → 守卫拒绝
#   G10: simulate beta   + beta    → 守卫通过
#   G11: simulate rc     + rc      → 守卫通过
#   G12: simulate HEAD (detached) + alpha → 拒绝 (要求先 git switch)
#   G13: simulate release + hotfix v0.5.10 → 守卫通过 (PATCH bump 验证)
#
# 使用方法:
#   bash deployment/docker/tests/test_branch_guard.sh
#
# 注意:
#   - 测试用 SIMULATE_BRANCH 环境变量模拟当前分支,避免 git switch 副作用。
#   - 测试用 TEST_GUARD_ONLY=1 让脚本在守卫通过后立即退出,避免触发 mkdir/cp
#     /docker load 等副作用。
#   - 测试会临时改 deployment/docker/VERSION,trap 还原。
#   - 守卫逻辑只需在 main / beta / rc / release 任一渠道分支合入后,所有渠道
#     都共享同一份脚本,故单分支测试即可覆盖全部渠道-分支映射。

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

run_case() {
    local case_name="$1"
    local version="$2"
    local simulate_branch="$3"
    local skip_guard="${4:-0}"
    local expected="$5"  # "pass" or "fail"

    echo ""
    echo "--- Case: $case_name ---"
    echo "  VERSION=$version, SIMULATE_BRANCH=$simulate_branch, SKIP_GUARD=$skip_guard, expected=$expected"

    # 临时改 VERSION
    echo "$version" > "$VERSION_FILE"

    # 跑守卫
    local env_vars="TEST_GUARD_ONLY=1 SIMULATE_BRANCH=$simulate_branch"
    if [ "$skip_guard" = "1" ]; then
        env_vars="$env_vars SKIP_GUARD=1"
    fi

    local output
    local actual_exit
    set +e
    output=$(env $env_vars bash "$PACK_SH" 2>&1)
    actual_exit=$?
    set -e

    # 立刻还原 VERSION
    echo "$ORIGINAL_VERSION" > "$VERSION_FILE"

    # 验证
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

# ─── main 上的 case ─────────────────────────────────────────
run_case "G1-main+alpha"       "0.6.0-alpha.1" "main"    "0" "pass"
run_case "G2-main+stable"      "0.5.9"         "main"    "0" "fail"
run_case "G3-main+hotfix"      "0.5.10"        "main"    "0" "fail"
run_case "G4-main+beta"        "0.6.0-beta.1"  "main"    "0" "fail"
run_case "G5-main+rc"          "0.6.0-rc.1"    "main"    "0" "fail"
run_case "G6-main+stable-skip" "0.5.9"         "main"    "1" "pass"

# ─── release 上的 case ─────────────────────────────────────
run_case "G7-release+stable"   "0.5.9"         "release" "0" "pass"
run_case "G8-release+hotfix"   "0.5.10"        "release" "0" "pass"
run_case "G9-release+alpha"    "0.6.0-alpha.1" "release" "0" "fail"

# ─── beta / rc 上的 case ──────────────────────────────────
run_case "G10-beta+beta"       "0.6.0-beta.1"  "beta"    "0" "pass"
run_case "G11-rc+rc"           "0.6.0-rc.1"    "rc"      "0" "pass"

# ─── detached HEAD 拒绝 ──────────────────────────────────
run_case "G12-detached+alpha"  "0.6.0-alpha.1" "HEAD"    "0" "fail"

# ─── 跨版本号 hotfix(同 release 分支) ──────────────────
run_case "G13-release+hotfix-bump" "1.0.1"     "release" "0" "pass"
