#!/usr/bin/env bash
# verify_backup_batch.sh — 验证离线升级成组备份的完整性
#
# 校验项:
#   1. metadata.json 存在 + 必填字段齐全
#   2. database_file / media_file 不含路径穿越(..或绝对路径)
#   3. database.sql.gz sha256 + size 与 metadata 一致
#   4. media.tar.gz sha256 + size 与 metadata 一致
#   5. media.tar.gz 内 tar 成员路径无 ../ 且无绝对路径(防 zip-slip)
#
# 用法:
#   verify_backup_batch.sh [--skip-verify] [--report] <batch_dir>
#
# 退出码:
#   0  — 校验通过
#   非零 — 任一校验失败
#
# 这是 backup.sh 与 rollback.sh 共用的安全闸 — 失败立即拒绝。

set -euo pipefail

SKIP_VERIFY=0
REPORT_ONLY=0
BATCH_DIR=""

for arg in "$@"; do
    case "$arg" in
        --skip-verify) SKIP_VERIFY=1 ;;
        --report)      REPORT_ONLY=1 ;;
        -h|--help)
            sed -n '2,18p' "$0"
            exit 0
            ;;
        --*)
            echo "ERROR: unknown flag: $arg" >&2
            exit 2
            ;;
        *)
            BATCH_DIR="$arg"
            ;;
    esac
done

if [ -z "$BATCH_DIR" ]; then
    echo "ERROR: usage: $0 [--skip-verify] [--report] <batch_dir>" >&2
    exit 2
fi

if [ ! -d "$BATCH_DIR" ]; then
    echo "ERROR: batch_dir not found: $BATCH_DIR" >&2
    exit 3
fi

META="$BATCH_DIR/metadata.json"
if [ ! -f "$META" ]; then
    echo "ERROR: $META missing — paired backup must include metadata.json" >&2
    exit 4
fi

# 必填字段(与 backup_db.py / restore_db.py / smoke_tests.sh 阶段 11 对齐)
REQUIRED_KEYS='upgrade_id channel source_version database_file media_file database_sha256 media_sha256 database_size media_size restore_verified created_at'
for key in $REQUIRED_KEYS; do
    VAL=$(jq -r ".$key // \"__MISSING__\"" "$META" 2>/dev/null || echo "__PARSE_ERROR__")
    if [ "$VAL" = "__MISSING__" ] || [ "$VAL" = "__PARSE_ERROR__" ] || [ -z "$VAL" ]; then
        echo "ERROR: metadata.json missing required field: $key" >&2
        exit 5
    fi
done

# ─── 严格 JSON boolean 校验 ────────────────────────────────
# restore_verified 是"备份曾被实际恢复并验证过"的唯一凭据,
# 任何非 JSON boolean true 都必须拒绝,防止以下绕过:
#   - "true"  (字符串) — 语义漂移
#   - 1       (数字)   — 语义漂移
#   - false   (布尔)   — 备份未真正恢复验证
#   - null    (JSON)   — 等价缺失
#   - missing (字段)   — 上一步骤应当已写入但漏了
# jq -e 在结果为 false / null 时退 1,只有 JSON boolean true 才退 0。
if ! jq -e '.restore_verified == true' "$META" >/dev/null 2>&1; then
    ACTUAL_TYPE=$(jq -r '.restore_verified | type' "$META" 2>/dev/null || echo "missing")
    ACTUAL_VAL=$(jq -r '.restore_verified // "missing"' "$META" 2>/dev/null || echo "missing")
    echo "ERROR: restore_verified must be JSON boolean true (actual type=$ACTUAL_TYPE value=$ACTUAL_VAL)" >&2
    exit 5
fi

DATABASE_FILE=$(jq -r '.database_file' "$META")
MEDIA_FILE=$(jq -r '.media_file' "$META")
DATABASE_SHA=$(jq -r '.database_sha256' "$META")
MEDIA_SHA=$(jq -r '.media_sha256' "$META")
DATABASE_SIZE=$(jq -r '.database_size' "$META")
MEDIA_SIZE=$(jq -r '.media_size' "$META")
UPGRADE_ID=$(jq -r '.upgrade_id' "$META")
CHANNEL=$(jq -r '.channel' "$META")

# ─── 路径穿越防御 ─────────────────────────────────────
# 拒绝 ../、以 / 开头的绝对路径、空字符串
case "$DATABASE_FILE" in
    ""|*".."*|/*) echo "ERROR: database_file has invalid path: $DATABASE_FILE" >&2; exit 6 ;;
esac
case "$MEDIA_FILE" in
    ""|*".."*|/*) echo "ERROR: media_file has invalid path: $MEDIA_FILE" >&2; exit 6 ;;
esac

DB_PATH="$BATCH_DIR/$DATABASE_FILE"
MEDIA_PATH="$BATCH_DIR/$MEDIA_FILE"

if [ ! -f "$DB_PATH" ]; then
    echo "ERROR: database file missing: $DB_PATH" >&2
    exit 7
fi
if [ ! -f "$MEDIA_PATH" ]; then
    echo "ERROR: media file missing: $MEDIA_PATH" >&2
    exit 7
fi

# ─── sha256 + size 校验 ────────────────────────────────
if [ "$SKIP_VERIFY" -eq 0 ]; then
    ACTUAL_DB_SHA=$(sha256sum "$DB_PATH" | awk '{print $1}')
    if [ "$ACTUAL_DB_SHA" != "$DATABASE_SHA" ]; then
        echo "ERROR: database sha256 mismatch (actual=$ACTUAL_DB_SHA expected=$DATABASE_SHA)" >&2
        exit 8
    fi
    ACTUAL_DB_SIZE=$(stat -c%s "$DB_PATH")
    if [ "$ACTUAL_DB_SIZE" != "$DATABASE_SIZE" ]; then
        echo "ERROR: database size mismatch (actual=$ACTUAL_DB_SIZE expected=$DATABASE_SIZE)" >&2
        exit 8
    fi

    ACTUAL_MEDIA_SHA=$(sha256sum "$MEDIA_PATH" | awk '{print $1}')
    if [ "$ACTUAL_MEDIA_SHA" != "$MEDIA_SHA" ]; then
        echo "ERROR: media sha256 mismatch (actual=$ACTUAL_MEDIA_SHA expected=$MEDIA_SHA)" >&2
        exit 8
    fi
    ACTUAL_MEDIA_SIZE=$(stat -c%s "$MEDIA_PATH")
    if [ "$ACTUAL_MEDIA_SIZE" != "$MEDIA_SIZE" ]; then
        echo "ERROR: media size mismatch (actual=$ACTUAL_MEDIA_SIZE expected=$MEDIA_SIZE)" >&2
        exit 8
    fi
else
    echo "WARN: --skip-verify active; sha256/size NOT checked" >&2
fi

# ─── media.tar.gz tar 成员路径穿越防御 ─────────────────
# 检查每个 tar 成员路径不含 .. 或绝对路径(防 zip-slip 类攻击)
TEMP_LIST="$(mktemp)"
trap 'rm -f "$TEMP_LIST"' EXIT
tar -tzf "$MEDIA_PATH" > "$TEMP_LIST" 2>/dev/null || {
    echo "ERROR: failed to list media.tar.gz members" >&2
    exit 9
}
while IFS= read -r member; do
    case "$member" in
        ""|*".."*|/*)
            echo "ERROR: media tar contains unsafe member path: $member" >&2
            exit 10
            ;;
    esac
done < "$TEMP_LIST"
rm -f "$TEMP_LIST"
trap - EXIT

# ─── 输出报告 ─────────────────────────────────────────
if [ "$REPORT_ONLY" -eq 1 ]; then
    echo "─── backup batch report ───"
    echo "upgrade_id:        $UPGRADE_ID"
    echo "channel:           $CHANNEL"
    echo "database_file:     $DATABASE_FILE"
    echo "database_sha256:   $DATABASE_SHA"
    echo "media_file:        $MEDIA_FILE"
    echo "media_sha256:      $MEDIA_SHA"
    echo "database_size:     $DATABASE_SIZE bytes"
    echo "media_size:        $MEDIA_SIZE bytes"
    echo "───────────────────────────"
fi

echo "OK: batch verified: $BATCH_DIR (upgrade_id=$UPGRADE_ID, channel=$CHANNEL)"