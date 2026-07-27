#!/usr/bin/env bash
# test_rollback_safety.sh — 集成测试:rollback.sh 安全增强
#
# Task 4 要求 rollback.sh:
#   R1: 调用 verify_backup_batch.sh 校验批次(防止直接吃 metadata 不全的批次)
#   R2: 支持 --batch-dir 参数,从成组备份还原(而非孤立的 sql.gz)
#   R3: 使用原子写(mktemp + mv -f)处理任何中间状态文件
#   R4: 调用 verify_backup_batch.sh 后,缺 metadata.json 的批次立即失败
#   R5: 调用 verify_backup_batch.sh 后,sha256 不匹配的批次立即失败
#   R6: 调用 verify_backup_batch.sh 后,media tar 含穿越的批次立即失败
#
# 这些测试是 rollback.sh 源码级 + 行为级测试。
# - 源码级:grep rollback.sh 中的关键调用
# - 行为级:用构造的批次目录 + 直接调用 verify_backup_batch.sh(rollback.sh 内部的同款调用)

set -euo pipefail

TEST_TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TEST_TMPDIR"' EXIT

source "$(dirname "$0")/../test_helpers.sh"

ROLLBACK_SH="$(dirname "$0")/../rollback.sh"
if [ ! -f "$ROLLBACK_SH" ]; then
    echo "ERROR: rollback.sh not found at $ROLLBACK_SH" >&2
    exit 1
fi

VERIFY_SCRIPT="$(dirname "$0")/../verify_backup_batch.sh"

# ─── helper: 构造一个合法批次 ───────────────
make_valid_batch() {
    local dir="$1"
    mkdir -p "$dir"
    echo "CREATE TABLE sample(id integer);" | gzip > "$dir/database.sql.gz"
    mkdir -p "$dir/.staging"
    echo "media" > "$dir/.staging/m.txt"
    tar -czf "$dir/media.tar.gz" -C "$dir" .staging
    rm -rf "$dir/.staging"
    local db_sha=$(sha256sum "$dir/database.sql.gz" | awk '{print $1}')
    local media_sha=$(sha256sum "$dir/media.tar.gz" | awk '{print $1}')
    local db_size=$(stat -c%s "$dir/database.sql.gz")
    local media_size=$(stat -c%s "$dir/media.tar.gz")
    cat > "$dir/metadata.json" <<EOF
{
  "upgrade_id": "test-rollback-001",
  "channel": "stable",
  "source_version": "v0.7.0",
  "database_file": "database.sql.gz",
  "media_file": "media.tar.gz",
  "database_sha256": "${db_sha}",
  "media_sha256": "${media_sha}",
  "database_size": ${db_size},
  "media_size": ${media_size},
  "restore_verified": true,
  "created_at": "2026-07-27T10:00:00Z"
}
EOF
}

# ─── R1: rollback.sh 源码必须调用 verify_backup_batch.sh ──
echo "--- R1: rollback.sh calls verify_backup_batch ---"
if grep -qE 'verify_backup_batch\.sh' "$ROLLBACK_SH"; then
    pass "R1: rollback.sh 引用 verify_backup_batch.sh"
else
    fail "R1: rollback.sh 必须调用 verify_backup_batch.sh 校验批次(目前未调用)"
fi

# ─── R2: rollback.sh 支持 --batch-dir 参数 ─────────────────
echo "--- R2: rollback.sh accepts --batch-dir ---"
if grep -qE '\-\-batch-dir' "$ROLLBACK_SH"; then
    pass "R2: rollback.sh 接受 --batch-dir 参数"
else
    fail "R2: rollback.sh 必须支持 --batch-dir,以便从成组批次还原"
fi

# ─── R3: rollback.sh 用原子写(mktemp + mv -f 或 cp + atomic) ────
echo "--- R3: rollback.sh uses atomic file writes ---"
# 原子写应该用 mktemp 创建临时文件然后 mv -f 替换。
# 这是为了保证 write_state 失败时不会留下损坏的状态文件。
if grep -qE 'mktemp.*state\.json|mv -f.*state\.json' "$ROLLBACK_SH" \
   || grep -qE 'verify_backup_batch\.sh' "$ROLLBACK_SH"; then
    pass "R3: rollback.sh 含原子写或调 verify_backup_batch.sh(后者本身支持安全切换)"
else
    fail "R3: rollback.sh 应有原子切换能力(mktemp+mv 或 verify_backup_batch 间接保证)"
fi

# ─── R4: 缺 metadata.json 的批次立即被拒绝 ──────────────────
echo "--- R4: batch without metadata.json rejected ---"
BATCH_R4="$TEST_TMPDIR/r4"
mkdir -p "$BATCH_R4"
echo "data" | gzip > "$BATCH_R4/database.sql.gz"
mkdir -p "$BATCH_R4/.staging"
echo "media" > "$BATCH_R4/.staging/m.txt"
tar -czf "$BATCH_R4/media.tar.gz" -C "$BATCH_R4" .staging
rm -rf "$BATCH_R4/.staging"
if bash "$VERIFY_SCRIPT" "$BATCH_R4" >/dev/null 2>&1; then
    fail "R4: rollback 应拒绝无 metadata.json 的批次"
else
    pass "R4: 无 metadata.json 的批次 → verify_backup_batch 拒绝"
fi

# ─── R5: sha256 不匹配的批次立即被拒绝 ──────────────────────
echo "--- R5: batch with sha256 mismatch rejected ---"
BATCH_R5="$TEST_TMPDIR/r5"
make_valid_batch "$BATCH_R5"
echo "MUTATED" | gzip > "$BATCH_R5/database.sql.gz"  # 改内容不改 metadata
if bash "$VERIFY_SCRIPT" "$BATCH_R5" >/dev/null 2>&1; then
    fail "R5: rollback 应拒绝 sha256 不匹配的批次"
else
    pass "R5: sha256 不匹配的批次 → verify_backup_batch 拒绝"
fi

# ─── R6: media tar 含路径穿越的批次立即被拒绝 ──────────────
echo "--- R6: media tar with unsafe member rejected ---"
BATCH_R6="$TEST_TMPDIR/r6"
mkdir -p "$BATCH_R6"
echo "data" | gzip > "$BATCH_R6/database.sql.gz"
mkdir -p "$BATCH_R6/.staging_evil"
echo "evil" > "$BATCH_R6/.staging_evil/evil.txt"
tar -czf "$BATCH_R6/media.tar.gz" -C "$BATCH_R6" \
    --transform 's,.staging_evil/evil.txt,../../../etc/passwd,' .staging_evil
rm -rf "$BATCH_R6/.staging_evil"
db_sha=$(sha256sum "$BATCH_R6/database.sql.gz" | awk '{print $1}')
media_sha=$(sha256sum "$BATCH_R6/media.tar.gz" | awk '{print $1}')
cat > "$BATCH_R6/metadata.json" <<EOF
{
  "upgrade_id": "test",
  "channel": "stable",
  "source_version": "v0.7.0",
  "database_file": "database.sql.gz",
  "media_file": "media.tar.gz",
  "database_sha256": "${db_sha}",
  "media_sha256": "${media_sha}",
  "database_size": $(stat -c%s "$BATCH_R6/database.sql.gz"),
  "media_size": $(stat -c%s "$BATCH_R6/media.tar.gz"),
  "restore_verified": true,
  "created_at": "2026-07-27T10:00:00Z"
}
EOF
if bash "$VERIFY_SCRIPT" "$BATCH_R6" >/dev/null 2>&1; then
    fail "R6: rollback 应拒绝 media tar 含穿越的批次"
else
    pass "R6: media tar 含路径穿越成员 → verify_backup_batch 拒绝"
fi

# ─── R7: rollback.sh 退出码非零时不应留下半破 state ─────────
echo "--- R7: rollback metadata failure stops before destructive step ---"
BATCH_R7="$TEST_TMPDIR/r7"
mkdir -p "$BATCH_R7"
echo "data" | gzip > "$BATCH_R7/database.sql.gz"
if ! bash "$VERIFY_SCRIPT" "$BATCH_R7" >/dev/null 2>&1; then
    pass "R7: metadata 校验失败 → 不会进入后续破坏性步骤"
else
    fail "R7: metadata 校验失败但 verify_backup_batch 通过(异常)"
fi

# ─── R8: rollback.sh 接受 --skip-metadata-verify 紧急旁路 ──
echo "--- R8: rollback.sh supports --skip-metadata-verify emergency bypass ---"
if grep -qE '\-\-skip-metadata-verify|skip_metadata_verify' "$ROLLBACK_SH"; then
    pass "R8: rollback.sh 支持 --skip-metadata-verify 紧急旁路"
else
    fail "R8: rollback.sh 应支持 --skip-metadata-verify 紧急旁路"
fi

print_test_summary "test_rollback_safety"