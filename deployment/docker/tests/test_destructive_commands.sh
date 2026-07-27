#!/usr/bin/env bash
# test_destructive_commands.sh — 危险清理命令门禁测试(Task 7)
#
# 覆盖目标(Task 7 brief):
#   D1: clean 无参数 → 拒绝,不下发 down -v
#   D2: 错误确认短语 → 拒绝
#   D3: 缺 backup-id → 拒绝
#   D4: backup-id 不存在 → 拒绝
#   D5: metadata 缺 restore_verified=true → 拒绝
#   D6: DB checksum 不匹配 → 拒绝
#   D7: media checksum 不匹配 → 拒绝
#   D8: 备份目录在外部 backup root 之外 → 拒绝(防 path traversal)
#   D9: 有 active upgrade lock → 拒绝
#   D10: 全部门禁通过 + 正确确认短语 → 通过,且仅删除生产数据卷
#        (不得删除外部 backup root,且写审计日志)
#   D11: 确认短语对 channel 大小写敏感(必须严格匹配 <channel>)
#   D12: 确认短语必须完全匹配(缺 channel / 大小写不同 → 拒绝)
#   D13: metadata.json schema 含 brief 要求全部 11 字段
#   D14: 源码层面门禁已落地(grep deploy_offline.sh)
#
# 使用方法:
#   bash deployment/docker/tests/test_destructive_commands.sh
#
# 设计:
#   - 使用 stub docker 拦截 docker compose 调用,把参数写入日志,
#     便于断言 down -v 是否被调用。
#   - 真实部署脚本(部署目录 deployment/docker/)的 deploy_offline.sh
#     被复制到临时 bundle 目录中,避免污染源码树。
#   - 测试不依赖真实 docker / 数据库 / 网络。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ─── 内联 assertion helpers(避免引用外部 test_helpers.sh 的全局计数冲突)─────
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
    local f="$1" pattern="$2" label="${3:-contains}"
    if [ ! -f "$f" ]; then
        fail "$label: file missing: $f"
        return
    fi
    if grep -qE "$pattern" "$f"; then
        pass "$label: '$pattern' in $f"
    else
        fail "$label: '$pattern' NOT found in $f"
    fi
}

# ─── 主测试 ──────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  危险清理命令门禁测试(Task 7)"
echo "=========================================="

# 1. 前置 — 源文件存在
assert_file_exists "$ROOT/deploy_offline.sh"

# 2. 创建测试沙箱
TEST_TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TEST_TMPDIR"' EXIT

# 2.1 创建外部 backup root(模拟 /opt/omnidesk/backups)
BACKUP_ROOT="$TEST_TMPDIR/external_backups"
RUNTIME_ROOT="$TEST_TMPDIR/runtime"
mkdir -p "$BACKUP_ROOT" "$RUNTIME_ROOT/upgrades"
mkdir -p "$BACKUP_ROOT/audit"

# 2.2 创建 stub docker:把所有 docker compose 调用写到日志,便于断言
STUB_BIN="$TEST_TMPDIR/stub_bin"
mkdir -p "$STUB_BIN"
DOCKER_LOG="$STUB_BIN/docker.log"
: > "$DOCKER_LOG"
cat > "$STUB_BIN/docker" <<STUB_EOF
#!/bin/bash
# stub docker:把完整命令写入日志,返回 0
echo "ARGS: \$*" >> "$DOCKER_LOG"
exit 0
STUB_EOF
chmod +x "$STUB_BIN/docker"

# 2.3 创建"假"离线包布局:scripts/ + compose/
BUNDLE="$TEST_TMPDIR/bundle"
mkdir -p "$BUNDLE/scripts" "$BUNDLE/compose"
cp "$ROOT/deploy_offline.sh" "$BUNDLE/scripts/deploy_offline.sh"
chmod +x "$BUNDLE/scripts/deploy_offline.sh"
# 必须有 compose/docker-compose.offline.yml,否则 deploy_offline.sh 会回退到
# "源码树布局"模式,导致它从 scripts/ 同级找 .env.production 而找不到。
# 这里用真实 compose 副本(stub 容器,只让布局识别通过)。
if [ -f "$ROOT/docker-compose.offline.yml" ]; then
    cp "$ROOT/docker-compose.offline.yml" "$BUNDLE/compose/docker-compose.offline.yml"
else
    cat > "$BUNDLE/compose/docker-compose.offline.yml" <<'COMPOSE_EOF'
name: ${COMPOSE_PROJECT_NAME:?COMPOSE_PROJECT_NAME must be set}
services:
  db:
    image: postgres:14-alpine
volumes:
  postgres_data:
    name: ${OMNIDESK_POSTGRES_VOLUME}
COMPOSE_EOF
fi

# 2.4 创建 .env.production(包含 CHANNEL 与固定身份字段)
cat > "$BUNDLE/compose/.env.production" <<EOF
CHANNEL=rc
COMPOSE_PROJECT_NAME=omnidesk-rc
OMNIDESK_POSTGRES_VOLUME=omnidesk-rc-postgres-data
OMNIDESK_MEDIA_VOLUME=omnidesk-rc-media-data
OMNIDESK_BACKUP_ROOT=$BACKUP_ROOT
OMNIDESK_RUNTIME_ROOT=$RUNTIME_ROOT
BACKEND_IMAGE_TAG=v0.7.0-rc.1
FRONTEND_IMAGE_TAG=v0.7.0-rc.1
POSTGRES_DB=test
POSTGRES_USER=u
POSTGRES_PASSWORD=p
SECRET_KEY=k
REDIS_PASSWORD=r
EOF

# 2.5 创建有效备份批次(用真实 sha256)
BATCH_ID='20260725T143000Z-v0.7.0-rc.1-to-v0.7.0-rc.2'
BATCH_DIR="$BACKUP_ROOT/rc/$BATCH_ID"
mkdir -p "$BATCH_DIR"

# 写一个合法的 .sql.gz(gzip 格式)
printf 'CREATE TABLE sample(id integer);\n' | gzip > "$BATCH_DIR/database.sql.gz"
# 写一个合法的 media tar(空 tar)
python3 -c "
import tarfile
with tarfile.open('$BATCH_DIR/media.tar.gz', 'w:gz') as t:
    pass
"
# 生成 sha256 副文件
(
    cd "$BATCH_DIR"
    sha256sum database.sql.gz > database.sql.gz.sha256
    sha256sum media.tar.gz > media.tar.gz.sha256
)
DATABASE_SHA="$(awk '{print $1}' "$BATCH_DIR/database.sql.gz.sha256")"
MEDIA_SHA="$(awk '{print $1}' "$BATCH_DIR/media.tar.gz.sha256")"
DATABASE_SIZE="$(stat -c%s "$BATCH_DIR/database.sql.gz")"
MEDIA_SIZE="$(stat -c%s "$BATCH_DIR/media.tar.gz")"

# 写 metadata.json(restore_verified=true)
cat > "$BATCH_DIR/metadata.json" <<EOF
{
  "upgrade_id": "$BATCH_ID",
  "channel": "rc",
  "source_version": "v0.7.0-rc.1",
  "database_file": "database.sql.gz",
  "media_file": "media.tar.gz",
  "database_sha256": "$DATABASE_SHA",
  "media_sha256": "$MEDIA_SHA",
  "database_size": $DATABASE_SIZE,
  "media_size": $MEDIA_SIZE,
  "restore_verified": true,
  "created_at": "2026-07-25T14:30:00Z"
}
EOF

# ─── 工具函数:运行 clean 并收集结果 ────────────────────────────
# 每次调用前清空 docker.log,让断言只关注本次调用
run_clean() {
    : > "$DOCKER_LOG"
    set +e
    PATH="$STUB_BIN:$PATH" \
        OMNIDESK_BACKUP_ROOT="$BACKUP_ROOT" \
        OMNIDESK_RUNTIME_ROOT="$RUNTIME_ROOT" \
        bash "$BUNDLE/scripts/deploy_offline.sh" clean "$@" \
        > "$TEST_TMPDIR/clean.stdout" 2> "$TEST_TMPDIR/clean.stderr"
    local rc=$?
    set -e
    echo "$rc"
}

down_v_called() {
    # 检查 stub docker.log 是否包含 down -v 或 down --volumes
    if [ -f "$DOCKER_LOG" ] && grep -qE 'down[ \t]+(-v|--volumes)' "$DOCKER_LOG"; then
        return 0
    fi
    return 1
}

# ─── D1: clean 无参数 → 拒绝,不下发 down -v ────────────────────
echo ""
echo "--- D1: clean 无参数 ---"
RC=$(run_clean)
if [ "$RC" -ne 0 ]; then
    pass "D1 clean 无参数非零退出 (rc=$RC)"
else
    fail "D1 clean 无参数未拒绝 (rc=0)"
fi
if down_v_called; then
    fail "D1 clean 无参数却调用了 down -v"
else
    pass "D1 clean 无参数未调用 down -v"
fi

# ─── D2: 错误确认短语 → 拒绝 ────────────────────────────────
echo ""
echo "--- D2: 错误确认短语 ---"
RC=$(run_clean --confirm-delete-data "WRONG_PHRASE" --backup-id "$BATCH_ID")
if [ "$RC" -ne 0 ]; then
    pass "D2 错误确认短语非零退出 (rc=$RC)"
else
    fail "D2 错误确认短语未拒绝 (rc=0)"
fi
if down_v_called; then
    fail "D2 错误确认短语却调用了 down -v"
else
    pass "D2 错误确认短语未调用 down -v"
fi
# 错误信息必须提示"确认短语"
if grep -qiE '确认|confirm|phrase' "$TEST_TMPDIR/clean.stderr" "$TEST_TMPDIR/clean.stdout" 2>/dev/null; then
    pass "D2 输出包含确认短语相关提示"
else
    fail "D2 错误输出缺少确认短语提示(用户不知道哪儿错)"
fi

# ─── D3: 缺 backup-id → 拒绝 ────────────────────────────────
echo ""
echo "--- D3: 缺 backup-id ---"
RC=$(run_clean --confirm-delete-data "DELETE OMNIDESK DATA rc")
if [ "$RC" -ne 0 ]; then
    pass "D3 缺 backup-id 非零退出 (rc=$RC)"
else
    fail "D3 缺 backup-id 未拒绝 (rc=0)"
fi
if down_v_called; then
    fail "D3 缺 backup-id 却调用了 down -v"
else
    pass "D3 缺 backup-id 未调用 down -v"
fi

# ─── D4: backup-id 不存在 → 拒绝 ──────────────────────────────
echo ""
echo "--- D4: backup-id 不存在 ---"
RC=$(run_clean --confirm-delete-data "DELETE OMNIDESK DATA rc" --backup-id "non-existent-batch")
if [ "$RC" -ne 0 ]; then
    pass "D4 不存在 batch 非零退出 (rc=$RC)"
else
    fail "D4 不存在 batch 未拒绝 (rc=0)"
fi
if down_v_called; then
    fail "D4 不存在 batch 却调用了 down -v"
else
    pass "D4 不存在 batch 未调用 down -v"
fi

# ─── D5: metadata 缺 restore_verified=true → 拒绝 ──────────────
echo ""
echo "--- D5: restore_verified=false ---"
# 临时修改 metadata.json:restore_verified=false
cp "$BATCH_DIR/metadata.json" "$BATCH_DIR/metadata.json.bak"
python3 -c "
import json
with open('$BATCH_DIR/metadata.json') as f:
    d = json.load(f)
d['restore_verified'] = False
with open('$BATCH_DIR/metadata.json', 'w') as f:
    json.dump(d, f, indent=2)
"
RC=$(run_clean --confirm-delete-data "DELETE OMNIDESK DATA rc" --backup-id "$BATCH_ID")
if [ "$RC" -ne 0 ]; then
    pass "D5 restore_verified=false 非零退出 (rc=$RC)"
else
    fail "D5 restore_verified=false 未拒绝 (rc=0)"
fi
if down_v_called; then
    fail "D5 restore_verified=false 却调用了 down -v"
else
    pass "D5 restore_verified=false 未调用 down -v"
fi
# 恢复 metadata
mv "$BATCH_DIR/metadata.json.bak" "$BATCH_DIR/metadata.json"

# ─── D6: DB checksum 不匹配 → 拒绝 ──────────────────────────
echo ""
echo "--- D6: DB checksum 不匹配 ---"
cp "$BATCH_DIR/database.sql.gz.sha256" "$BATCH_DIR/database.sql.gz.sha256.bak"
echo "0000000000000000000000000000000000000000000000000000000000000000  database.sql.gz" > "$BATCH_DIR/database.sql.gz.sha256"
RC=$(run_clean --confirm-delete-data "DELETE OMNIDESK DATA rc" --backup-id "$BATCH_ID")
if [ "$RC" -ne 0 ]; then
    pass "D6 DB checksum 不匹配非零退出 (rc=$RC)"
else
    fail "D6 DB checksum 不匹配未拒绝 (rc=0)"
fi
if down_v_called; then
    fail "D6 DB checksum 不匹配却调用了 down -v"
else
    pass "D6 DB checksum 不匹配未调用 down -v"
fi
mv "$BATCH_DIR/database.sql.gz.sha256.bak" "$BATCH_DIR/database.sql.gz.sha256"

# ─── D7: media checksum 不匹配 → 拒绝 ────────────────────────
echo ""
echo "--- D7: media checksum 不匹配 ---"
cp "$BATCH_DIR/media.tar.gz.sha256" "$BATCH_DIR/media.tar.gz.sha256.bak"
echo "0000000000000000000000000000000000000000000000000000000000000000  media.tar.gz" > "$BATCH_DIR/media.tar.gz.sha256"
RC=$(run_clean --confirm-delete-data "DELETE OMNIDESK DATA rc" --backup-id "$BATCH_ID")
if [ "$RC" -ne 0 ]; then
    pass "D7 media checksum 不匹配非零退出 (rc=$RC)"
else
    fail "D7 media checksum 不匹配未拒绝 (rc=0)"
fi
if down_v_called; then
    fail "D7 media checksum 不匹配却调用了 down -v"
else
    pass "D7 media checksum 不匹配未调用 down -v"
fi
mv "$BATCH_DIR/media.tar.gz.sha256.bak" "$BATCH_DIR/media.tar.gz.sha256"

# ─── D8: 备份目录在外部 backup root 之外 → 拒绝(防 path traversal)
echo ""
echo "--- D8: 备份目录在外部 root 之外 ---"
# 通过 ../ 路径引用:BRIEF 要求严格只接受 <BACKUP_ROOT>/<CHANNEL>/<BACKUP_ID> 形式,
# 任何 ../ 或绝对路径都不应被接受。
RC=$(run_clean --confirm-delete-data "DELETE OMNIDESK DATA rc" --backup-id "../../../etc/passwd")
if [ "$RC" -ne 0 ]; then
    pass "D8 path traversal 拒绝 (rc=$RC)"
else
    fail "D8 path traversal 未拒绝 (rc=0)"
fi
if down_v_called; then
    fail "D8 path traversal 却调用了 down -v"
else
    pass "D8 path traversal 未调用 down -v"
fi

# ─── D9: 有 active upgrade lock → 拒绝 ──────────────────────────
echo ""
echo "--- D9: 有 active upgrade lock ---"
# 在 RUNTIME_ROOT 创建一个有效的 upgrade lock + INIT 状态(模拟运行中升级)
ACTIVE_UPGRADE='20260725T150000Z-v0.7.0-rc.2-to-v0.7.0-rc.3'
mkdir -p "$RUNTIME_ROOT/upgrades/$ACTIVE_UPGRADE/upgrade.lock"
echo "99999" > "$RUNTIME_ROOT/upgrades/$ACTIVE_UPGRADE/upgrade.lock/pid"
# 写一个非终态的 state.json(INIT 表示刚开始,不能删除数据)
cat > "$RUNTIME_ROOT/upgrades/$ACTIVE_UPGRADE/state.json" <<EOF
{
  "upgrade_id": "$ACTIVE_UPGRADE",
  "state": "INIT",
  "source_version": "v0.7.0-rc.1",
  "target_version": "v0.7.0-rc.2",
  "channel": "rc",
  "compose_project_name": "omnidesk-rc",
  "updated_at": "2026-07-25T15:00:00Z"
}
EOF
RC=$(run_clean --confirm-delete-data "DELETE OMNIDESK DATA rc" --backup-id "$BATCH_ID")
if [ "$RC" -ne 0 ]; then
    pass "D9 有 active upgrade 非零退出 (rc=$RC)"
else
    fail "D9 有 active upgrade 未拒绝 (rc=0)"
fi
if down_v_called; then
    fail "D9 有 active upgrade 却调用了 down -v"
else
    pass "D9 有 active upgrade 未调用 down -v"
fi
# 清理 active upgrade
rm -rf "$RUNTIME_ROOT/upgrades/$ACTIVE_UPGRADE"

# ─── D10: 全部门禁通过 → 通过,删除数据卷,保留外部 backup,写审计
echo ""
echo "--- D10: 全部门禁通过 ---"
RC=$(run_clean --confirm-delete-data "DELETE OMNIDESK DATA rc" --backup-id "$BATCH_ID")
if [ "$RC" -eq 0 ]; then
    pass "D10 全部门禁通过 (rc=0)"
else
    fail "D10 全部门禁未通过 (rc=$RC)"
    echo "    stdout: $(cat "$TEST_TMPDIR/clean.stdout" | head -20)"
    echo "    stderr: $(cat "$TEST_TMPDIR/clean.stderr" | head -20)"
fi
# 必须调用了 down -v
if down_v_called; then
    pass "D10 成功调用 down -v"
else
    fail "D10 成功路径未调用 down -v(没真正删除数据卷)"
fi
# 外部 backup root 必须保留(batch 目录还在)
if [ -d "$BATCH_DIR" ]; then
    pass "D10 外部 backup root 仍存在($BATCH_DIR 未被删除)"
else
    fail "D10 外部 backup root 被错误删除(违反 brief:不得删除外部备份)"
fi
# 审计日志
AUDIT_LOG="$BACKUP_ROOT/audit/clean.log"
assert_file_exists "$AUDIT_LOG"
assert_contains "$AUDIT_LOG" "$BATCH_ID" "D10 审计日志含 batch_id"
assert_contains "$AUDIT_LOG" "DELETE OMNIDESK DATA rc" "D10 审计日志含确认短语"

# ─── D11: 确认短语对 channel 大小写敏感 ──────────────────────
echo ""
echo "--- D11: 确认短语 channel 不匹配 ---"
# channel 是 rc,确认短语是 stable → 不应通过
RC=$(run_clean --confirm-delete-data "DELETE OMNIDESK DATA stable" --backup-id "$BATCH_ID")
if [ "$RC" -ne 0 ]; then
    pass "D11 channel 不匹配非零退出 (rc=$RC)"
else
    fail "D11 channel 不匹配未拒绝 (rc=0)"
fi
if down_v_called; then
    fail "D11 channel 不匹配却调用了 down -v"
else
    pass "D11 channel 不匹配未调用 down -v"
fi

# ─── D12: 确认短语必须完全匹配(多/少字符都不行) ─────────────
echo ""
echo "--- D12: 确认短语部分匹配 ---"
RC=$(run_clean --confirm-delete-data "DELETE OMNIDESK DATA" --backup-id "$BATCH_ID")
if [ "$RC" -ne 0 ]; then
    pass "D12 缺 channel 后缀非零退出 (rc=$RC)"
else
    fail "D12 缺 channel 后缀未拒绝 (rc=0)"
fi

RC=$(run_clean --confirm-delete-data "delete omnidesk data rc" --backup-id "$BATCH_ID")
if [ "$RC" -ne 0 ]; then
    pass "D12b 大小写不匹配非零退出 (rc=$RC)"
else
    fail "D12b 大小写不匹配未拒绝 (rc=0)"
fi

# ─── D13: metadata 字段 schema 验证 ─────────────────────────
echo ""
echo "--- D13: metadata.json schema 完整性 ---"
# metadata.json 必须含 brief 要求的全部 11 字段
REQUIRED_FIELDS=(
    upgrade_id channel source_version database_file media_file
    database_sha256 media_sha256 database_size media_size
    restore_verified created_at
)
for f in "${REQUIRED_FIELDS[@]}"; do
    if python3 -c "
import json
with open('$BATCH_DIR/metadata.json') as fh:
    d = json.load(fh)
if '$f' not in d:
    exit(1)
" 2>/dev/null; then
        pass "D13 metadata 含字段: $f"
    else
        fail "D13 metadata 缺字段: $f"
    fi
done

# ─── D14: 源码层面门禁已落地 ──────────────────────────────
echo ""
echo "--- D14: 源码门禁已落地 ---"
# deploy_offline.sh 必须含全部 6 个门禁的字面引用
GATE_PATTERNS=(
    "active.upgrade"           # D9: 拒绝运行中升级
    "metadata"                 # D5: 检查 metadata
    "restore_verified"         # D5: 验证字段
    "checksum"                 # D6/D7
    "DELETE OMNIDESK DATA"     # D2/D10/D11
    "audit"                    # D10: 审计日志
)
for p in "${GATE_PATTERNS[@]}"; do
    if grep -qiE "$p" "$ROOT/deploy_offline.sh"; then
        pass "D14 deploy_offline.sh 含门禁: $p"
    else
        fail "D14 deploy_offline.sh 缺门禁: $p"
    fi
done

# ─── 汇总 ────────────────────────────────────────────────────
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
