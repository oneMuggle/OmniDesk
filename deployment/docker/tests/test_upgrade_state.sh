#!/usr/bin/env bash
# test_upgrade_state.sh — 单元测试: upgrade_state.sh 模块
#
# 覆盖场景 (Task 2 brief + 协调员 I3):
#   T1: write_state INIT 源/目标版本 → state.json.state == "INIT"
#   T2: transition_state INIT PREFLIGHT_PASSED → state.json.state == "PREFLIGHT_PASSED"
#   T3: 非法转换 INIT→BACKUP_CREATED → 非零退出 + state.json 不含 "BACKUP_CREATED"
#   T4: enter_safe_stop → state.json.state == "SAFE_STOPPED"(无论 stop 命令是否成功)
#   T5: 已有 SAFE_STOPPED 时拒绝新升级(写新 UPGRADE_ID 应失败)
#   T6: 升级锁 acquire/release 基础路径
#   T7: 状态 JSON 含 brief 列出的全部 10 个强制字段
#   T8: 并发互斥 — 同一 UPGRADE_ID 第二次 acquire_upgrade_lock 失败
#   T9: 非持有者 release_upgrade_lock 被拒绝(返回非零)
#  T10: enter_safe_stop 保留已有 state.json 的上下文字段
#
# 使用方法:
#   bash deployment/docker/tests/test_upgrade_state.sh
#
# 注意:
#   - 测试用 mktemp -d 隔离 OMNIDESK_RUNTIME_ROOT,trap 在 EXIT 时清理。
#   - 测试不依赖 docker compose(enter_safe_stop 在无 compose 环境会失败,但状态写入必须成功)。
#   - T8 用独立子 shell 模拟"另一进程":子 shell 拥有独立 PID,无法用 $$ 模拟。
#     实际做法:chmod 删 pid 文件可破坏持有者语义;此处用更直接的方式:
#     在主测试 PID 下 acquire 后,直接在子 shell 中尝试 acquire(同 UPGRADE_ID)期望失败。
#     "非持有者"语义由 T9 单独验证(通过手动覆盖 pid 文件到非 $$ 值)。

set -euo pipefail

TEST_TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TEST_TMPDIR"' EXIT

source "$(dirname "$0")/../test_helpers.sh"

# 公共环境变量(必须在 source upgrade_state.sh 前 export,
# 否则模块会用默认的 /opt/omnidesk/runtime)
export UPGRADE_ID='20260725T143000Z-v0.7.0-rc.1-to-v0.7.0-rc.2'
export COMPOSE_PROJECT_NAME='omnidesk-rc'
export OMNIDESK_POSTGRES_VOLUME='omnidesk-rc-postgres-data'
export OMNIDESK_MEDIA_VOLUME='omnidesk-rc-media-data'

source "$(dirname "$0")/../upgrade_state.sh"

# 每个 case 独立的 runtime root,避免升级锁互斥
# (必须在 source upgrade_state.sh 之后,因为 upgrade_state.sh 在 source 时
#  会读取 OMNIDESK_RUNTIME_ROOT 的值作为模块内部 $UPGRADES_ROOT 等的初值)
case1_root() { export OMNIDESK_RUNTIME_ROOT="$TEST_TMPDIR/runtime1"; mkdir -p "$OMNIDESK_RUNTIME_ROOT"; }
case4_root() { export OMNIDESK_RUNTIME_ROOT="$TEST_TMPDIR/runtime4"; mkdir -p "$OMNIDESK_RUNTIME_ROOT"; }
case5_root() { export OMNIDESK_RUNTIME_ROOT="$TEST_TMPDIR/runtime5"; mkdir -p "$OMNIDESK_RUNTIME_ROOT"; }
case6_root() { export OMNIDESK_RUNTIME_ROOT="$TEST_TMPDIR/runtime6"; mkdir -p "$OMNIDESK_RUNTIME_ROOT"; }
case7_root() { export OMNIDESK_RUNTIME_ROOT="$TEST_TMPDIR/runtime7"; mkdir -p "$OMNIDESK_RUNTIME_ROOT"; }
case8_root() { export OMNIDESK_RUNTIME_ROOT="$TEST_TMPDIR/runtime8"; mkdir -p "$OMNIDESK_RUNTIME_ROOT"; }
case9_root() { export OMNIDESK_RUNTIME_ROOT="$TEST_TMPDIR/runtime9"; mkdir -p "$OMNIDESK_RUNTIME_ROOT"; }
case10_root() { export OMNIDESK_RUNTIME_ROOT="$TEST_TMPDIR/runtime10"; mkdir -p "$OMNIDESK_RUNTIME_ROOT"; }

# ─── T1: write_state 写 INIT + 原子替换 ──────────────────────
echo ""
echo "--- T1: write_state INIT ---"
case1_root
write_state INIT source_version=0.7.0-rc.1 target_version=0.7.0-rc.2 \
    channel=preview backup_dir="$TEST_TMPDIR/backups/$UPGRADE_ID" \
    source_image_tag=ghcr.io/onemuggle/omni-desk-backend:v0.7.0-rc.1 \
    target_image_tag=ghcr.io/onemuggle/omni-desk-backend:v0.7.0-rc.2

STATE_FILE1="$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/state.json"
assert_file_exists "$STATE_FILE1"
assert_json_field "$STATE_FILE1" state              "INIT"
assert_json_field "$STATE_FILE1" source_version      "0.7.0-rc.1"
assert_json_field "$STATE_FILE1" target_version      "0.7.0-rc.2"
assert_json_field "$STATE_FILE1" upgrade_id          "$UPGRADE_ID"
assert_json_field "$STATE_FILE1" channel             "preview"
assert_json_field "$STATE_FILE1" compose_project_name "$COMPOSE_PROJECT_NAME"

# ─── T2: transition_state INIT → PREFLIGHT_PASSED ───────────
echo ""
echo "--- T2: transition_state INIT PREFLIGHT_PASSED ---"
transition_state INIT PREFLIGHT_PASSED
assert_json_field "$STATE_FILE1" state "PREFLIGHT_PASSED"

# ─── T3: 非法转换被拒绝(state.json 不应被污染)────────
echo ""
echo "--- T3: 非法转换 INIT→BACKUP_CREATED 被拒绝 ---"
set +e
transition_state INIT BACKUP_CREATED >/dev/null 2>&1
illegal_rc=$?
set -e
if [ "$illegal_rc" -ne 0 ]; then
    pass "非法转换 INIT→BACKUP_CREATED 被拒绝 (exit=$illegal_rc)"
else
    fail "非法转换 INIT→BACKUP_CREATED 未被拒绝 (exit=0)"
fi
assert_json_field "$STATE_FILE1" state "PREFLIGHT_PASSED"
assert_file_not_contains "$STATE_FILE1" '"state": "BACKUP_CREATED"'

# ─── T4: enter_safe_stop 写 SAFE_STOPPED ────────────────────
echo ""
echo "--- T4: enter_safe_stop 写 SAFE_STOPPED ---"
case4_root
write_state INIT source_version=0.5.9 target_version=0.5.9 \
    channel=stable backup_dir="$TEST_TMPDIR/backups/$UPGRADE_ID" \
    source_image_tag=ghcr.io/onemuggle/omni-desk-backend:v0.5.9 \
    target_image_tag=ghcr.io/onemuggle/omni-desk-backend:v0.5.9

STATE_FILE4="$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/state.json"

# enter_safe_stop 会尝试 docker compose stop。退出码依赖 .env.production
# 是否存在(无 → docker compose 失败 → rc=1;有 → docker compose 成功 → rc=0)。
# 这是真实生产环境的合理行为,因此 T4 不应断言特定退出码 — 改断言
# "无论如何都写入 SAFE_STOPPED" — 这才是 brief 真正要求的语义。
set +e
enter_safe_stop "test forced stop" >/dev/null 2>&1
set -e
# 核心断言(brief 原文):无论 stop 命令是否成功,SAFE_STOPPED 状态必须被写入
assert_json_field "$STATE_FILE4" state "SAFE_STOPPED"
# 进一步断言:reason 必须记录(保证 enter_safe_stop 真正走到了写状态分支)
assert_json_field "$STATE_FILE4" reason "test forced stop"
# stop_failures 必须记录(可能是 "none" 也可能是服务名列表)
STOP_FAILS=$(jq -r '.stop_failures // ""' "$STATE_FILE4" 2>/dev/null || echo "")
if [ -n "$STOP_FAILS" ]; then
    pass "stop_failures 已记录: [$STOP_FAILS]"
else
    fail "stop_failures 未记录"
fi

# ─── T5: SAFE_STOPPED 时拒绝新升级 ─────────────────────────
echo ""
echo "--- T5: SAFE_STOPPED 状态下新升级被拒绝 ---"
case5_root
mkdir -p "$OMNIDESK_RUNTIME_ROOT/upgrades/legacy-safestop-2026"
cat > "$OMNIDESK_RUNTIME_ROOT/upgrades/legacy-safestop-2026/state.json" <<EOF
{
  "upgrade_id": "legacy-safestop-2026",
  "state": "SAFE_STOPPED",
  "updated_at": "2026-07-25T12:00:00Z"
}
EOF
NEW_UPGRADE_ID='20260725T150000Z-v0.7.0-rc.2-to-v0.7.0-rc.3'
set +e
UPGRADE_ID="$NEW_UPGRADE_ID" write_state INIT \
    source_version=0.7.0-rc.2 target_version=0.7.0-rc.3 \
    channel=preview backup_dir="$TEST_TMPDIR/backups/$NEW_UPGRADE_ID" \
    source_image_tag=ghcr.io/onemuggle/omni-desk-backend:v0.7.0-rc.2 \
    target_image_tag=ghcr.io/onemuggle/omni-desk-backend:v0.7.0-rc.3 \
    >/dev/null 2>&1
reject_rc=$?
set -e
if [ "$reject_rc" -ne 0 ]; then
    pass "SAFE_STOPPED 拒绝新升级 (exit=$reject_rc)"
else
    fail "SAFE_STOPPED 未拒绝新升级(允许了写入)"
fi
if [ ! -d "$OMNIDESK_RUNTIME_ROOT/upgrades/$NEW_UPGRADE_ID" ]; then
    pass "新升级目录未被创建"
else
    fail "新升级目录被错误创建: $OMNIDESK_RUNTIME_ROOT/upgrades/$NEW_UPGRADE_ID"
fi

# ─── T6: 升级锁 acquire/release 基础路径 ───────────────────
echo ""
echo "--- T6: 升级锁 acquire/release 基础路径 ---"
case6_root
LOCK_DIR_T6="$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/upgrade.lock"

# (a) 初次 acquire 成功
if acquire_upgrade_lock; then
    pass "初次 acquire_upgrade_lock 成功"
else
    fail "初次 acquire_upgrade_lock 失败 (rc=$?)"
fi
assert_file_exists "$LOCK_DIR_T6/pid"
# pid 文件应记录当前 PID
LOCKED_PID_T6=$(cat "$LOCK_DIR_T6/pid" 2>/dev/null || echo "")
if [ "$LOCKED_PID_T6" = "$$" ]; then
    pass "锁 pid 文件记录当前进程 PID"
else
    fail "锁 pid 文件内容=[$LOCKED_PID_T6] 期望=[$$]"
fi

# (b) release 成功
if release_upgrade_lock; then
    pass "持有者 release_upgrade_lock 成功"
else
    fail "持有者 release_upgrade_lock 失败"
fi
# 锁目录应已被删除
if [ ! -d "$LOCK_DIR_T6" ]; then
    pass "release 后锁目录已删除"
else
    fail "release 后锁目录仍存在: $LOCK_DIR_T6"
fi

# (c) 锁不存在时 release 是幂等的(返回 0)
if release_upgrade_lock; then
    pass "无锁时 release_upgrade_lock 幂等成功"
else
    fail "无锁时 release_upgrade_lock 应幂等成功 (rc=$?)"
fi

# ─── T7: 状态 JSON 字段完整性 ─────────────────────────────
echo ""
echo "--- T7: 状态 JSON 字段完整性 ---"
case7_root
write_state INIT source_version=0.7.0-rc.1 target_version=0.7.0-rc.2 \
    channel=preview backup_dir="$TEST_TMPDIR/backups/$UPGRADE_ID" \
    source_image_tag=ghcr.io/onemuggle/omni-desk-backend:v0.7.0-rc.1 \
    target_image_tag=ghcr.io/onemuggle/omni-desk-backend:v0.7.0-rc.2

STATE_FILE7="$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/state.json"
required_fields=(
    upgrade_id source_version target_version channel state
    backup_dir source_image_tag target_image_tag compose_project_name updated_at
)
for f in "${required_fields[@]}"; do
    assert_contains "$STATE_FILE7" "\"$f\""
done

# ─── T8: 并发互斥 — 同一 UPGRADE_ID 第二次 acquire 失败 ──
echo ""
echo "--- T8: 同一 UPGRADE_ID 第二次 acquire 失败 ---"
case8_root
LOCK_DIR_T8="$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/upgrade.lock"

# 第一次 acquire 必须成功
if ! acquire_upgrade_lock; then
    fail "T8 前置: 第一次 acquire_upgrade_lock 失败"
    exit 1
fi
# 第二次 acquire 必须失败(锁目录已存在)
set +e
acquire_upgrade_lock >/dev/null 2>&1
second_rc=$?
set -e
if [ "$second_rc" -ne 0 ]; then
    pass "第二次 acquire_upgrade_lock 被拒绝 (rc=$second_rc)"
else
    fail "第二次 acquire_upgrade_lock 应被拒绝却成功"
fi
# 锁目录仍存在,pid 未被覆盖
LOCKED_PID_T8=$(cat "$LOCK_DIR_T8/pid" 2>/dev/null || echo "")
if [ "$LOCKED_PID_T8" = "$$" ]; then
    pass "第二次 acquire 未篡改持有者 pid"
else
    fail "第二次 acquire 篡改了 pid: [$LOCKED_PID_T8] 期望 [$$]"
fi
# 清理
release_upgrade_lock >/dev/null 2>&1 || true

# ─── T9: 非持有者 release_upgrade_lock 被拒绝 ─────────────
echo ""
echo "--- T9: 非持有者 release_upgrade_lock 被拒绝 ---"
case9_root
LOCK_DIR_T9="$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/upgrade.lock"
mkdir -p "$LOCK_DIR_T9"
# 写一个"其他人"的 pid
OTHER_PID=999999
echo "$OTHER_PID" > "$LOCK_DIR_T9/pid"

# 当前 $$ 不是 999999 → release 应被拒绝(返回非零)
set +e
release_upgrade_lock >/dev/null 2>&1
non_holder_rc=$?
set -e
if [ "$non_holder_rc" -ne 0 ]; then
    pass "非持有者 release_upgrade_lock 被拒绝 (rc=$non_holder_rc)"
else
    fail "非持有者 release_upgrade_lock 应被拒绝却成功"
fi
# 锁目录必须仍存在(未被非持有者删除)
if [ -d "$LOCK_DIR_T9" ]; then
    pass "非持有者 release 后锁目录仍存在"
else
    fail "非持有者 release 删除了锁目录(应被阻止)"
fi
# pid 应未改变
LOCKED_PID_T9=$(cat "$LOCK_DIR_T9/pid" 2>/dev/null || echo "")
if [ "$LOCKED_PID_T9" = "$OTHER_PID" ]; then
    pass "非持有者 release 未篡改原持有者 pid"
else
    fail "非持有者 release 篡改了 pid: [$LOCKED_PID_T9] 期望 [$OTHER_PID]"
fi

# 缺失 pid 文件的锁目录 → release 也应拒绝(防止误删)
mkdir -p "$OMNIDESK_RUNTIME_ROOT/upgrades/${UPGRADE_ID}-nopid/upgrade.lock"
NOPID_LOCK="$OMNIDESK_RUNTIME_ROOT/upgrades/${UPGRADE_ID}-nopid/upgrade.lock"
set +e
UPGRADE_ID="${UPGRADE_ID}-nopid" release_upgrade_lock >/dev/null 2>&1
nopid_rc=$?
set -e
if [ "$nopid_rc" -ne 0 ]; then
    pass "无 pid 文件的锁 release 被拒绝 (rc=$nopid_rc)"
else
    fail "无 pid 文件的锁 release 应被拒绝却成功"
fi

# ─── T10: enter_safe_stop 保留已有 state.json 的上下文字段 ──
echo ""
echo "--- T10: enter_safe_stop 保留已有 state.json 上下文 ---"
case10_root
# 先写一个完整的 INIT 状态(包含所有上下文字段)
write_state INIT source_version=0.7.0-rc.1 target_version=0.7.0-rc.2 \
    channel=preview backup_dir="$TEST_TMPDIR/backups/$UPGRADE_ID/full" \
    source_image_tag=ghcr.io/onemuggle/omni-desk-backend:v0.7.0-rc.1 \
    target_image_tag=ghcr.io/onemuggle/omni-desk-backend:v0.7.0-rc.2

STATE_FILE10="$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/state.json"

# 记录原始 updated_at
ORIG_UPDATED_AT=$(jq -r '.updated_at' "$STATE_FILE10")
sleep 1  # 确保 SAFE_STOPPED 的 updated_at 与原值不同

# 调用 enter_safe_stop
set +e
enter_safe_stop "preservation test" >/dev/null 2>&1
safe_stop_rc=$?
set -e

# state 应是 SAFE_STOPPED
assert_json_field "$STATE_FILE10" state "SAFE_STOPPED"
# 上下文字段应被保留(关键:I2 要求)
assert_json_field "$STATE_FILE10" source_version      "0.7.0-rc.1"
assert_json_field "$STATE_FILE10" target_version      "0.7.0-rc.2"
assert_json_field "$STATE_FILE10" channel             "preview"
assert_json_field "$STATE_FILE10" backup_dir          "$TEST_TMPDIR/backups/$UPGRADE_ID/full"
assert_json_field "$STATE_FILE10" source_image_tag    "ghcr.io/onemuggle/omni-desk-backend:v0.7.0-rc.1"
assert_json_field "$STATE_FILE10" target_image_tag    "ghcr.io/onemuggle/omni-desk-backend:v0.7.0-rc.2"
assert_json_field "$STATE_FILE10" upgrade_id          "$UPGRADE_ID"
assert_json_field "$STATE_FILE10" compose_project_name "$COMPOSE_PROJECT_NAME"
# updated_at 应被刷新
NEW_UPDATED_AT=$(jq -r '.updated_at' "$STATE_FILE10")
if [ "$NEW_UPDATED_AT" != "$ORIG_UPDATED_AT" ]; then
    pass "SAFE_STOPPED 刷新 updated_at: $ORIG_UPDATED_AT → $NEW_UPDATED_AT"
else
    fail "SAFE_STOPPED 未刷新 updated_at (仍为 $NEW_UPDATED_AT)"
fi
# reason / stop_failures 应被设置
assert_json_field "$STATE_FILE10" reason "preservation test"
# stop_failures 内容依赖环境(若有 compose 则尝试 stop 并失败,若无则标记 no-compose-file);
# 只断言非空且是字符串即可。
STOP_FAILS=$(jq -r '.stop_failures // ""' "$STATE_FILE10")
if [ -n "$STOP_FAILS" ] && [ "$STOP_FAILS" != "__MISSING__" ]; then
    pass "stop_failures 非空: [$STOP_FAILS]"
else
    fail "stop_failures 未设置: [$STOP_FAILS]"
fi

# ─── 总结 ──────────────────────────────────────────────────
print_test_summary "upgrade_state.sh 测试"
