#!/usr/bin/env bash
# test_helpers.sh — 共享测试断言 / fixture helpers
#
# 提供最小工具集(不引外部依赖),供 deployment/docker/tests/*.sh 复用:
#   - assert_file_exists <path>
#   - assert_contains <file> <pattern>            # grep -E
#   - assert_file_not_contains <file> <pattern>   # 用于"拒绝写"类断言
#   - assert_json_field <json_file> <field> <expected_value>
#   - assert_equals <expected> <actual>
#   - assert_failure <cmd...>                     # 期望非零退出
#
# 约定:测试文件应 `set -euo pipefail`,并 `source "$(dirname "$0")/../test_helpers.sh"`。

set -euo pipefail

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

assert_file_not_contains() {
    local f="$1" pattern="$2"
    if [ ! -f "$f" ]; then
        fail "assert_file_not_contains: file missing: $f"
        return
    fi
    if ! grep -qE "$pattern" "$f"; then
        pass "does NOT contain '$pattern' in $f"
    else
        fail "should NOT contain '$pattern' in $f (FOUND)"
    fi
}

assert_equals() {
    local expected="$1" actual="$2" label="${3:-assert_equals}"
    if [ "$expected" = "$actual" ]; then
        pass "$label: [$actual]"
    else
        fail "$label: expected=[$expected] actual=[$actual]"
    fi
}

assert_failure() {
    # 期望命令以非零退出
    local label="$1"
    shift
    set +e
    "$@" >/dev/null 2>&1
    local rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
        pass "$label (exit=$rc)"
    else
        fail "$label expected failure but got exit=0"
    fi
}

# assert_json_field: 用 jq 取 JSON 字段并断言其值
# 注:这是脚本上下文里的 jq,而非本模块内的实现细节。
assert_json_field() {
    local f="$1" field="$2" expected="$3"
    if [ ! -f "$f" ]; then
        fail "assert_json_field: file missing: $f"
        return
    fi
    local actual
    actual=$(jq -r ".$field // \"__MISSING__\"" "$f" 2>/dev/null || echo "__PARSE_ERROR__")
    assert_equals "$expected" "$actual" "json.$field"
}

print_test_summary() {
    local label="${1:-test}"
    echo ""
    echo "=========================================="
    echo "  ${label}: PASS=$PASS_COUNT FAIL=$FAIL_COUNT"
    if [ "$FAIL_COUNT" -gt 0 ]; then
        echo "  失败用例: ${FAILED_CASES[*]}"
        echo "=========================================="
        exit 1
    fi
    echo "  全部通过"
    echo "=========================================="
}
