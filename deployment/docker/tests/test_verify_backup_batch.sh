#!/usr/bin/env bash
# test_verify_backup_batch.sh — 单元测试:verify_backup_batch 函数
#
# 覆盖 Task 4 关键安全场景:
#   V1: 合法 batch (metadata + database.sql.gz + media.tar.gz + sha256 一致) → exit 0
#   V2: 缺 metadata.json → exit 非零
#   V3: metadata.json 必填字段缺失 → exit 非零
#   V4: database.sql.gz sha256 不匹配 → exit 非零
#   V5: media.tar.gz sha256 不匹配 → exit 非零
#   V6: media.tar.gz 含路径穿越成员(../../etc/passwd) → exit 非零
#   V7: database_file 是绝对路径或 ..  → exit 非零 (防路径穿越)
#   V8: media_file 是绝对路径或 ..   → exit 非零
#   V9: --skip-verify 跳过 sha256 检查,允许暂放过期备份(紧急用)
#  V10: print_report 输出关键字段(便于人肉审计)
#
# 使用方式:
#   bash deployment/docker/tests/test_verify_backup_batch.sh

set -euo pipefail

TEST_TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TEST_TMPDIR"' EXIT

source "$(dirname "$0")/../test_helpers.sh"

# verify_backup_batch.sh 路径
VERIFY_SCRIPT="$(dirname "$0")/../verify_backup_batch.sh"
if [ ! -f "$VERIFY_SCRIPT" ]; then
    echo "ERROR: verify_backup_batch.sh not found at $VERIFY_SCRIPT" >&2
    exit 1
fi

# ─── helper: 构造一个合法的成组备份 batch ───────────────
make_valid_batch() {
    local dir="$1"
    mkdir -p "$dir"
    # 写合法的 SQL + 真实 tar.gz 归档(verify_backup_batch.sh 要 tar -tzf 验成员)
    echo "CREATE TABLE sample(id integer);" | gzip > "$dir/database.sql.gz"
    mkdir -p "$dir/.staging_media"
    echo "placeholder-media-content-$(date +%s)" > "$dir/.staging_media/sample.txt"
    tar -czf "$dir/media.tar.gz" -C "$dir" .staging_media
    rm -rf "$dir/.staging_media"
    # 计算 sha256
    local db_sha=$(sha256sum "$dir/database.sql.gz" | awk '{print $1}')
    local media_sha=$(sha256sum "$dir/media.tar.gz" | awk '{print $1}')
    local db_size=$(stat -c%s "$dir/database.sql.gz")
    local media_size=$(stat -c%s "$dir/media.tar.gz")
    # 写 metadata.json
    cat > "$dir/metadata.json" <<EOF
{
  "upgrade_id": "test-20260727-001",
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

# ─── V1: 合法 batch → exit 0 ──────────────────────────────
echo "--- V1: valid batch passes ---"
BATCH_V1="$TEST_TMPDIR/v1"
make_valid_batch "$BATCH_V1"
if bash "$VERIFY_SCRIPT" "$BATCH_V1" >/dev/null 2>&1; then
    pass "V1: valid batch → exit 0"
else
    fail "V1: valid batch should pass but failed"
fi

# ─── V2: 缺 metadata.json → exit 非零 ──────────────────────
echo "--- V2: missing metadata.json ---"
BATCH_V2="$TEST_TMPDIR/v2"
mkdir -p "$BATCH_V2"
echo "data" | gzip > "$BATCH_V2/database.sql.gz"
# 写一个合法 tar.gz
mkdir -p "$BATCH_V2/.staging"
echo "media" > "$BATCH_V2/.staging/m.txt"
tar -czf "$BATCH_V2/media.tar.gz" -C "$BATCH_V2" .staging
rm -rf "$BATCH_V2/.staging"
if bash "$VERIFY_SCRIPT" "$BATCH_V2" >/dev/null 2>&1; then
    fail "V2: missing metadata should fail"
else
    pass "V2: missing metadata.json → rejected"
fi

# ─── V3: metadata.json 必填字段缺失 → exit 非零 ──────────
echo "--- V3: incomplete metadata.json ---"
BATCH_V3="$TEST_TMPDIR/v3"
mkdir -p "$BATCH_V3"
echo "data" | gzip > "$BATCH_V3/database.sql.gz"
mkdir -p "$BATCH_V3/.staging"
echo "media" > "$BATCH_V3/.staging/m.txt"
tar -czf "$BATCH_V3/media.tar.gz" -C "$BATCH_V3" .staging
rm -rf "$BATCH_V3/.staging"
cat > "$BATCH_V3/metadata.json" <<EOF
{"database_file":"database.sql.gz","media_file":"media.tar.gz"}
EOF
if bash "$VERIFY_SCRIPT" "$BATCH_V3" >/dev/null 2>&1; then
    fail "V3: incomplete metadata should fail"
else
    pass "V3: incomplete metadata → rejected"
fi

# ─── V4: database.sql.gz sha256 不匹配 → exit 非零 ──────
echo "--- V4: database sha256 mismatch ---"
BATCH_V4="$TEST_TMPDIR/v4"
make_valid_batch "$BATCH_V4"
# 篡改 database.sql.gz(覆盖为不同内容,留下旧 sha)
echo "TAMPERED SQL" | gzip > "$BATCH_V4/database.sql.gz"
if bash "$VERIFY_SCRIPT" "$BATCH_V4" >/dev/null 2>&1; then
    fail "V4: tampered database.sql.gz should fail"
else
    pass "V4: tampered database.sql.gz → rejected"
fi

# ─── V5: media.tar.gz sha256 不匹配 → exit 非零 ──────────
echo "--- V5: media sha256 mismatch ---"
BATCH_V5="$TEST_TMPDIR/v5"
make_valid_batch "$BATCH_V5"
# 重新打包一个内容不同的合法 tar.gz(让 sha256 变)
mkdir -p "$BATCH_V5/.staging_evil"
echo "evil content" > "$BATCH_V5/.staging_evil/evil.txt"
tar -czf "$BATCH_V5/media.tar.gz" -C "$BATCH_V5" .staging_evil
rm -rf "$BATCH_V5/.staging_evil"
if bash "$VERIFY_SCRIPT" "$BATCH_V5" >/dev/null 2>&1; then
    fail "V5: tampered media.tar.gz should fail"
else
    pass "V5: tampered media.tar.gz → rejected"
fi

# ─── V6: media.tar.gz 含路径穿越成员 → exit 非零 ──────────
echo "--- V6: media tar with traversal member ---"
BATCH_V6="$TEST_TMPDIR/v6"
mkdir -p "$BATCH_V6"
echo "data" | gzip > "$BATCH_V6/database.sql.gz"
# 用 tar 创建含 ../../../etc/passwd 的恶意归档
mkdir -p "$BATCH_V6/staging"
echo "evil" > "$BATCH_V6/staging/evil.txt"
tar -czf "$BATCH_V6/media.tar.gz" -C "$BATCH_V6/staging" \
    --transform 's,evil.txt,../../../etc/passwd,' evil.txt
db_sha=$(sha256sum "$BATCH_V6/database.sql.gz" | awk '{print $1}')
db_size=$(stat -c%s "$BATCH_V6/database.sql.gz")
media_sha=$(sha256sum "$BATCH_V6/media.tar.gz" | awk '{print $1}')
media_size=$(stat -c%s "$BATCH_V6/media.tar.gz")
cat > "$BATCH_V6/metadata.json" <<EOF
{
  "upgrade_id": "test",
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
if bash "$VERIFY_SCRIPT" "$BATCH_V6" >/dev/null 2>&1; then
    fail "V6: traversal media tar should fail"
else
    pass "V6: traversal media tar member → rejected"
fi

# ─── V7: database_file 含 ../ → exit 非零 ──────────────────
echo "--- V7: database_file with traversal ---"
BATCH_V7="$TEST_TMPDIR/v7"
mkdir -p "$BATCH_V7"
echo "data" | gzip > "$BATCH_V7/database.sql.gz"
mkdir -p "$BATCH_V7/.staging"
echo "media" > "$BATCH_V7/.staging/m.txt"
tar -czf "$BATCH_V7/media.tar.gz" -C "$BATCH_V7" .staging
rm -rf "$BATCH_V7/.staging"
db_sha=$(sha256sum "$BATCH_V7/database.sql.gz" | awk '{print $1}')
media_sha=$(sha256sum "$BATCH_V7/media.tar.gz" | awk '{print $1}')
cat > "$BATCH_V7/metadata.json" <<EOF
{
  "upgrade_id": "test",
  "channel": "stable",
  "source_version": "v0.7.0",
  "database_file": "../../../etc/passwd",
  "media_file": "media.tar.gz",
  "database_sha256": "${db_sha}",
  "media_sha256": "${media_sha}",
  "database_size": $(stat -c%s "$BATCH_V7/database.sql.gz"),
  "media_size": $(stat -c%s "$BATCH_V7/media.tar.gz"),
  "restore_verified": true,
  "created_at": "2026-07-27T10:00:00Z"
}
EOF
if bash "$VERIFY_SCRIPT" "$BATCH_V7" >/dev/null 2>&1; then
    fail "V7: database_file traversal should fail"
else
    pass "V7: database_file traversal → rejected"
fi

# ─── V8: media_file 是绝对路径 → exit 非零 ──────────────────
echo "--- V8: media_file absolute path ---"
BATCH_V8="$TEST_TMPDIR/v8"
mkdir -p "$BATCH_V8"
echo "data" | gzip > "$BATCH_V8/database.sql.gz"
mkdir -p "$BATCH_V8/.staging"
echo "media" > "$BATCH_V8/.staging/m.txt"
tar -czf "$BATCH_V8/media.tar.gz" -C "$BATCH_V8" .staging
rm -rf "$BATCH_V8/.staging"
cat > "$BATCH_V8/metadata.json" <<EOF
{
  "upgrade_id": "test",
  "channel": "stable",
  "source_version": "v0.7.0",
  "database_file": "database.sql.gz",
  "media_file": "/etc/passwd",
  "database_sha256": "$(sha256sum "$BATCH_V8/database.sql.gz" | awk '{print $1}')",
  "media_sha256": "$(sha256sum "$BATCH_V8/media.tar.gz" | awk '{print $1}')",
  "database_size": $(stat -c%s "$BATCH_V8/database.sql.gz"),
  "media_size": $(stat -c%s "$BATCH_V8/media.tar.gz"),
  "restore_verified": true,
  "created_at": "2026-07-27T10:00:00Z"
}
EOF
if bash "$VERIFY_SCRIPT" "$BATCH_V8" >/dev/null 2>&1; then
    fail "V8: absolute media_file should fail"
else
    pass "V8: absolute media_file path → rejected"
fi

# ─── V9: --skip-verify 跳过 sha256 校验 ────────────────────
echo "--- V9: --skip-verify allows mismatched checksums ---"
BATCH_V9="$TEST_TMPDIR/v9"
make_valid_batch "$BATCH_V9"
# 重新打包一个内容不同的合法 tar.gz(让 sha256 变)
mkdir -p "$BATCH_V9/.staging_evil"
echo "evil content" > "$BATCH_V9/.staging_evil/evil.txt"
tar -czf "$BATCH_V9/media.tar.gz" -C "$BATCH_V9" .staging_evil
rm -rf "$BATCH_V9/.staging_evil"
if bash "$VERIFY_SCRIPT" --skip-verify "$BATCH_V9" >/dev/null 2>&1; then
    pass "V9: --skip-verify allows mismatched media.tar.gz (emergency path)"
else
    fail "V9: --skip-verify should skip checksum but rejected anyway"
fi

# ─── V10: print_report 输出关键字段 ────────────────────────
echo "--- V10: print_report includes key fields ---"
BATCH_V10="$TEST_TMPDIR/v10"
make_valid_batch "$BATCH_V10"
OUTPUT=$(bash "$VERIFY_SCRIPT" --report "$BATCH_V10" 2>&1 || true)
if echo "$OUTPUT" | grep -q "upgrade_id"; then
    pass "V10: report mentions upgrade_id"
else
    fail "V10: report should mention upgrade_id, got: $OUTPUT"
fi
if echo "$OUTPUT" | grep -q "channel"; then
    pass "V10: report mentions channel"
else
    fail "V10: report should mention channel"
fi
if echo "$OUTPUT" | grep -q "database_sha256"; then
    pass "V10: report mentions database_sha256"
else
    fail "V10: report should mention database_sha256"
fi

print_test_summary "test_verify_backup_batch"