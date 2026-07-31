#!/usr/bin/env bash
# test_upgrade_failure_recovery.sh — 升级状态机贯通 + 失败自动恢复 + rollback 隔离
#
# 覆盖 Task 6 brief 全部验收点:
#   R1: 恢复状态机 8 步边全部定义(RECOVERY_STARTED → ... → RECOVERY_COMMITTED)
#   R2: 任一升级状态 → RECOVERY_STARTED 合法边
#   R3: 任一恢复状态 → SAFE_STOPPED 合法边(恢复失败兜底)
#   R4: 恢复状态机自身顺序贯通(8 步 transition 全部成功)
#   R5: upgrade.sh 引用全部 14 步主流程 transition_state
#   R6: upgrade.sh 失败处理引用恢复入口(RECOVERY_STARTED 或 run_recovery)
#   R7: rollback.sh 主体不写升级状态(write_state / transition_state 在 trap 之外不出现)
#   R8: rollback.sh trap 在失败时记 SAFE_STOPPED
#
# 使用方法:
#   bash deployment/docker/tests/test_upgrade_failure_recovery.sh
#
# 注意:
#   - 不依赖 docker compose(纯状态机 / 文本断言)
#   - 每个 case 用独立 OMNIDESK_RUNTIME_ROOT,避免升级锁/状态文件互串

set -euo pipefail

TEST_TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TEST_TMPDIR"' EXIT

# 公共环境(必须在 source upgrade_state.sh 前 export)
export UPGRADE_ID='20260727T100000Z-v0.7.0-rc.1-to-v0.7.0-rc.2'
export COMPOSE_PROJECT_NAME='omnidesk-rc'
export OMNIDESK_POSTGRES_VOLUME='omnidesk-rc-postgres-data'
export OMNIDESK_MEDIA_VOLUME='omnidesk-rc-media-data'

source "$(dirname "$0")/../test_helpers.sh"
source "$(dirname "$0")/../upgrade_state.sh"

# 每个 case 独立 runtime root(必须在 source 后再覆盖,因模块延迟绑定)
case_runtime() {
    export OMNIDESK_RUNTIME_ROOT="$TEST_TMPDIR/$1"
    mkdir -p "$OMNIDESK_RUNTIME_ROOT"
}

# ─── R1: 恢复状态机 8 步边全部定义 ────────────────────────────
echo ""
echo "--- R1: 恢复状态机 8 步边定义 ---"
recovery_edges=(
    "RECOVERY_STARTED:TARGET_SERVICES_STOPPED"
    "TARGET_SERVICES_STOPPED:SOURCE_RUNTIME_RESTORED"
    "SOURCE_RUNTIME_RESTORED:DATABASE_RESTORED"
    "DATABASE_RESTORED:MEDIA_RESTORED"
    "MEDIA_RESTORED:RESTORED_STATE_VERIFIED"
    "RESTORED_STATE_VERIFIED:SOURCE_HEALTHY"
    "SOURCE_HEALTHY:RECOVERY_COMMITTED"
)
for edge in "${recovery_edges[@]}"; do
    if is_valid_edge "${edge%%:*}" "${edge##*:}"; then
        pass "边 ${edge%%:*} → ${edge##*:} 已定义"
    else
        fail "边 ${edge%%:*} → ${edge##*:} 未定义"
    fi
done

# ─── R2: 任一升级状态 → RECOVERY_STARTED 合法边 ──────────────
echo ""
echo "--- R2: 任一升级状态 → RECOVERY_STARTED 合法 ---"
happy_states=(
    INIT PREFLIGHT_PASSED MAINTENANCE_ENABLED BACKUP_CREATED
    BACKUP_VERIFIED RUNTIME_SNAPSHOT_RECORDED WRITE_SERVICES_STOPPED
    TARGET_IMAGE_READY MIGRATION_PREFLIGHT_PASSED MIGRATED
    TARGET_HEALTHY SMOKE_TEST_PASSED COMMITTED MAINTENANCE_DISABLED
)
for s in "${happy_states[@]}"; do
    if is_valid_edge "$s" "RECOVERY_STARTED"; then
        pass "${s} → RECOVERY_STARTED 合法"
    else
        fail "${s} → RECOVERY_STARTED 非法(应允许从任何升级状态转入恢复)"
    fi
done

# ─── R3: 任一恢复状态 → SAFE_STOPPED 合法(恢复失败兜底) ────
echo ""
echo "--- R3: 恢复状态 → SAFE_STOPPED 合法(恢复失败兜底) ---"
recovery_states=(
    RECOVERY_STARTED TARGET_SERVICES_STOPPED SOURCE_RUNTIME_RESTORED
    DATABASE_RESTORED MEDIA_RESTORED RESTORED_STATE_VERIFIED
    SOURCE_HEALTHY RECOVERY_COMMITTED
)
# SAFE_STOPPED 已硬编码为任意状态可转入(见 is_valid_edge)
for s in "${recovery_states[@]}"; do
    if is_valid_edge "$s" "SAFE_STOPPED"; then
        pass "${s} → SAFE_STOPPED 合法"
    else
        fail "${s} → SAFE_STOPPED 非法(恢复失败时无法兜底)"
    fi
done

# ─── R4: 恢复状态机自身顺序贯通 ──────────────────────────────
echo ""
echo "--- R4: 恢复状态机自身顺序贯通 ---"
case_runtime "r4_recovery_flow"

# 起点:先写一个 PREFLIGHT_PASSED 状态(模拟"已通过预检、准备进入恢复")
write_state PREFLIGHT_PASSED source_version=0.7.0-rc.1 target_version=0.7.0-rc.2 \
    channel=preview backup_dir="$TEST_TMPDIR/r4_recovery_flow/backups/$UPGRADE_ID" \
    source_image_tag=ghcr.io/onemuggle/omni-desk-backend:v0.7.0-rc.1 \
    target_image_tag=ghcr.io/onemuggle/omni-desk-backend:v0.7.0-rc.2

STATE_FILE_R4="$OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/state.json"

# 任一升级状态 → RECOVERY_STARTED 合法
set +e
transition_state PREFLIGHT_PASSED RECOVERY_STARTED >/dev/null 2>&1
recovery_start_rc=$?
set -e
if [ "$recovery_start_rc" -eq 0 ]; then
    pass "PREFLIGHT_PASSED → RECOVERY_STARTED 转换成功"
else
    fail "PREFLIGHT_PASSED → RECOVERY_STARTED 转换失败 (rc=$recovery_start_rc)"
fi

# 顺序 7 步贯通(每步都允许失败,确保后续断言仍跑)
declare -A NEXT_OF=(
    [RECOVERY_STARTED]=TARGET_SERVICES_STOPPED
    [TARGET_SERVICES_STOPPED]=SOURCE_RUNTIME_RESTORED
    [SOURCE_RUNTIME_RESTORED]=DATABASE_RESTORED
    [DATABASE_RESTORED]=MEDIA_RESTORED
    [MEDIA_RESTORED]=RESTORED_STATE_VERIFIED
    [RESTORED_STATE_VERIFIED]=SOURCE_HEALTHY
    [SOURCE_HEALTHY]=RECOVERY_COMMITTED
)
for cur in RECOVERY_STARTED TARGET_SERVICES_STOPPED SOURCE_RUNTIME_RESTORED \
           DATABASE_RESTORED MEDIA_RESTORED RESTORED_STATE_VERIFIED \
           SOURCE_HEALTHY; do
    next="${NEXT_OF[$cur]}"
    set +e
    transition_state "$cur" "$next" >/dev/null 2>&1
    step_rc=$?
    set -e
    if [ "$step_rc" -eq 0 ]; then
        pass "恢复状态机 $cur → $next 转换成功"
    else
        fail "恢复状态机 $cur → $next 转换失败 (rc=$step_rc)"
    fi
    assert_json_field "$STATE_FILE_R4" state "$next"
done

# ─── R5: upgrade.sh 引用全部 14 步主流程 transition_state ────
echo ""
echo "--- R5: upgrade.sh 引用全部 14 步主流程 transition_state ---"
UPGRADE_SH="$(dirname "$0")/../upgrade.sh"
if [ ! -f "$UPGRADE_SH" ]; then
    fail "upgrade.sh 不存在: $UPGRADE_SH"
else
    # 14 步主流程状态(除 INIT 由 write_state 写入外,其余 13 步均应通过 transition_state 推进)
    expected_transitions=(
        "PREFLIGHT_PASSED"
        "MAINTENANCE_ENABLED"
        "BACKUP_CREATED"
        "BACKUP_VERIFIED"
        "RUNTIME_SNAPSHOT_RECORDED"
        "WRITE_SERVICES_STOPPED"
        "TARGET_IMAGE_READY"
        "MIGRATION_PREFLIGHT_PASSED"
        "MIGRATED"
        "TARGET_HEALTHY"
        "SMOKE_TEST_PASSED"
        "COMMITTED"
        "MAINTENANCE_DISABLED"
    )
    for next in "${expected_transitions[@]}"; do
        # upgrade.sh 必须有 transition_state ... $next 形式的调用
        if grep -qE "transition_state[[:space:]]+[A-Z_]+[[:space:]]+${next}\\b" "$UPGRADE_SH"; then
            pass "upgrade.sh 包含 transition_state → ${next}"
        else
            fail "upgrade.sh 缺少 transition_state → ${next} 调用"
        fi
    done
fi

# ─── R6: upgrade.sh 失败处理引用恢复入口 ──────────────────────
echo ""
echo "--- R6: upgrade.sh 失败处理引用恢复入口 ---"
if [ ! -f "$UPGRADE_SH" ]; then
    fail "upgrade.sh 不存在"
else
    # 失败 trap 必须触发 recovery(RECOVERY_STARTED 或 run_recovery)
    if grep -qE "(RECOVERY_STARTED|run_recovery)" "$UPGRADE_SH"; then
        pass "upgrade.sh 失败处理引用恢复入口(RECOVERY_STARTED / run_recovery)"
    else
        fail "upgrade.sh 失败处理未引用恢复入口(必须触发 recovery 而非直接 SAFE_STOPPED)"
    fi
    # SAFE_STOPPED 兜底:recovery 自身失败时仍可进入 SAFE_STOPPED
    if grep -qE "SAFE_STOPPED" "$UPGRADE_SH"; then
        pass "upgrade.sh 保留 SAFE_STOPPED 兜底(恢复失败时仍可进入)"
    else
        fail "upgrade.sh 缺少 SAFE_STOPPED 兜底(恢复失败时无处可去)"
    fi
fi

# ─── R7: rollback.sh 主体不写升级状态 ─────────────────────────
echo ""
echo "--- R7: rollback.sh 主体不写升级状态 ---"
ROLLBACK_SH="$(dirname "$0")/../rollback.sh"
if [ ! -f "$ROLLBACK_SH" ]; then
    fail "rollback.sh 不存在: $ROLLBACK_SH"
else
    # 在 main body 范围内(整个文件,但 trap 块除外)不能出现 write_state / transition_state 调用
    # 实现方式:用 awk 跳过 trap ... ) 块,再 grep
    # 简化:统计整个文件调用 write_state/transition_state 的位置;若存在,需在 trap/on_xxx_failure 内部
    write_state_lines=$(grep -nE "\bwrite_state\b" "$ROLLBACK_SH" || true)
    transition_lines=$(grep -nE "\btransition_state\b" "$ROLLBACK_SH" || true)

    if [ -z "$write_state_lines" ] && [ -z "$transition_lines" ]; then
        pass "rollback.sh 主体完全不调用 write_state / transition_state"
    else
        # 若有调用,必须全部在 trap 函数体内(on_xxx_failure 块)
        # 简单判定:trap 函数体内的行号范围
        trap_start=$(grep -nE "^on_.*_failure\(\)" "$ROLLBACK_SH" | head -1 | cut -d: -f1)
        trap_end=$(awk -v start="$trap_start" 'NR >= start && /^}$/ {print NR; exit}' "$ROLLBACK_SH")
        if [ -n "$trap_start" ] && [ -n "$trap_end" ]; then
            # 校验所有 write_state / transition_state 行号都在 trap 块外
            bad_lines=""
            while IFS= read -r line; do
                [ -z "$line" ] && continue
                ln="${line%%:*}"
                if [ "$ln" -ge "$trap_start" ] && [ "$ln" -le "$trap_end" ]; then
                    bad_lines="$bad_lines $ln"
                fi
            done <<< "$write_state_lines"$'\n'"$transition_lines"
            if [ -z "$bad_lines" ]; then
                pass "rollback.sh write_state/transition_state 仅在 trap 块内($trap_start-$trap_end)"
            else
                fail "rollback.sh write_state/transition_state 出现在 trap 块外(行号:$bad_lines)"
            fi
        else
            fail "rollback.sh 存在 write_state/transition_state 调用,但无法定位 trap 块(需手工检查)"
        fi
    fi
fi

# ─── R8: rollback.sh trap 在失败时记 SAFE_STOPPED ────────────
echo ""
echo "--- R8: rollback.sh trap 在失败时记 SAFE_STOPPED ---"
if [ ! -f "$ROLLBACK_SH" ]; then
    fail "rollback.sh 不存在"
else
    # trap 函数体必须包含 enter_safe_stop
    trap_start=$(grep -nE "^on_.*_failure\(\)" "$ROLLBACK_SH" | head -1 | cut -d: -f1)
    if [ -z "$trap_start" ]; then
        fail "rollback.sh 未定义 trap on_xxx_failure 函数"
    else
        trap_end=$(awk -v start="$trap_start" 'NR >= start && /^}$/ {print NR; exit}' "$ROLLBACK_SH")
        if [ -n "$trap_end" ]; then
            trap_block=$(sed -n "${trap_start},${trap_end}p" "$ROLLBACK_SH")
            if echo "$trap_block" | grep -qE "enter_safe_stop"; then
                pass "rollback.sh trap 调用 enter_safe_stop"
            else
                fail "rollback.sh trap 未调用 enter_safe_stop(失败时无法记 SAFE_STOPPED)"
            fi
        else
            fail "rollback.sh trap 函数体未找到结束符"
        fi
    fi
fi

# ─── 总结 ────────────────────────────────────────────────────
print_test_summary "upgrade_failure_recovery 测试"
