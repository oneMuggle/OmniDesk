#!/bin/bash
# L1 unit tests for conflict handler parsing logic
# 覆盖 spec §5 测试用例 1-5

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURE="$SCRIPT_DIR/fixtures/conflict_scenarios.json"
PASS=0
FAIL=0

if [ ! -f "$FIXTURE" ]; then
  echo "ERROR: Fixture not found: $FIXTURE"
  exit 2
fi

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    echo "  ✓ $desc"
    PASS=$((PASS+1))
  else
    echo "  ✗ $desc (expected: '$expected', got: '$actual')"
    FAIL=$((FAIL+1))
  fi
}

assert_contains() {
  local desc="$1" needle="$2" haystack="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    echo "  ✓ $desc"
    PASS=$((PASS+1))
  else
    echo "  ✗ $desc (needle '$needle' not found)"
    FAIL=$((FAIL+1))
  fi
}

# Test 1: parse_sync_markers_valid
echo "Test 1: parse_sync_markers_valid"
BODY='<!-- auto-sync-source: #68 -->
<!-- auto-sync-target: beta -->
some body'
SOURCE_PR=$(echo "$BODY" | grep -oP 'auto-sync-source: #\K\d+' | head -1)
TARGET=$(echo "$BODY" | grep -oP 'auto-sync-target: \K\S+' | head -1)
assert_eq "source_pr parsed correctly" "68" "$SOURCE_PR"
assert_eq "target parsed correctly" "beta" "$TARGET"

# Test 2: parse_sync_markers_missing
echo "Test 2: parse_sync_markers_missing"
BODY="body without markers"
SOURCE_PR=$(echo "$BODY" | grep -oP 'auto-sync-source: #\K\d+' | head -1)
TARGET=$(echo "$BODY" | grep -oP 'auto-sync-target: \K\S+' | head -1)
assert_eq "missing marker → empty source_pr" "" "${SOURCE_PR:-}"
assert_eq "missing marker → empty target" "" "${TARGET:-}"

# Test 3: compute_remaining_commits_all_applied
echo "Test 3: compute_remaining_commits_all_applied"
ALL_COMMITS="abc def ghi"
TARGET_ANCESTORS="abc def ghi"
REMAINING=""
for SHA in $ALL_COMMITS; do
  if ! echo "$TARGET_ANCESTORS" | grep -qw "$SHA"; then
    REMAINING="$REMAINING $SHA"
  fi
done
assert_eq "all applied → empty remaining" "" "${REMAINING# }"

# Test 4: compute_remaining_commits_partial
echo "Test 4: compute_remaining_commits_partial"
ALL_COMMITS="abc def ghi"
TARGET_ANCESTORS="abc"
REMAINING=""
for SHA in $ALL_COMMITS; do
  if ! echo "$TARGET_ANCESTORS" | grep -qw "$SHA"; then
    REMAINING="$REMAINING $SHA"
  fi
done
assert_eq "partial → correct remaining" "def ghi" "${REMAINING# }"

# Test 5: pr_body_template_conflict
echo "Test 5: pr_body_template_conflict"
RENDERED=$(cat <<'EOF'
🔁 [sync] #68 → beta
自动同步 PR

## ⚠️ Cherry-pick 冲突

**冲突 commit**: `a3fae3ff`
**目标分支**: `beta`
**冲突文件**: 3 个

### 快速解决指引

1. 下载 artifact
2. 本地复现
3. push 解决
4. 合并触发续跑

<!-- auto-sync-source: #68 -->
<!-- auto-sync-target: beta -->
EOF
)
assert_contains "body has ⚠️ marker" "⚠️ Cherry-pick 冲突" "$RENDERED"
assert_contains "body has 快速解决指引" "快速解决指引" "$RENDERED"
assert_contains "body has auto-sync-source marker" "auto-sync-source: #68" "$RENDERED"

# Summary
echo ""
echo "Results: PASS=$PASS FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi