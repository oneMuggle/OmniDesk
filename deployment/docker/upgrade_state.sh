#!/usr/bin/env bash
# upgrade_state.sh — 离线升级状态机 + 维护标记 + 原子状态文件
#
# 提供能力:
#   - write_state <state> [key=value ...]
#       写入 $OMNIDESK_RUNTIME_ROOT/upgrades/$UPGRADE_ID/state.json(原子替换),
#       包含强制字段集(upgrade_id / source_version / target_version / channel / state /
#       backup_dir / source_image_tag / target_image_tag / compose_project_name / updated_at)。
#   - transition_state <expected> <next>
#       仅允许状态机中定义的边迁移,其他情况返回非零。
#   - enter_safe_stop <reason>
#       先尝试停 Backend/Worker/Beat/frontend(尽力而为,失败也继续),
#       再写 SAFE_STOPPED 状态(保留已有 state.json 的所有上下文字段),
#       最后非零退出(若 stop 全部失败)。
#   - acquire_upgrade_lock / release_upgrade_lock
#       基于 mkdir 原子锁,防止并发升级;非持有者不能释放他人锁。
#   - assert_no_existing_safe_stop
#       守卫:已有 SAFE_STOPPED 时拒绝新升级。
#
# 状态机(固定,严禁修改):
#   INIT → PREFLIGHT_PASSED → MAINTENANCE_ENABLED → BACKUP_CREATED → BACKUP_VERIFIED
#   → RUNTIME_SNAPSHOT_RECORDED → WRITE_SERVICES_STOPPED → TARGET_IMAGE_READY
#   → MIGRATION_PREFLIGHT_PASSED → MIGRATED → TARGET_HEALTHY → SMOKE_TEST_PASSED
#   → COMMITTED → MAINTENANCE_DISABLED
# SAFE_STOPPED 是终态/错误态,任何状态都可转入(用于紧急停机)。

set -euo pipefail

# ─── 配置 ─────────────────────────────────────────────────
# 模块内部路径在每次函数调用时重算(支持 OMNIDESK_RUNTIME_ROOT/UPGRADE_ID 在
# source 后再修改,例如测试隔离不同 UPGRADE_ID)。
: "${OMNIDESK_RUNTIME_ROOT:=/opt/omnidesk/runtime}"
: "${UPGRADE_ID:=unknown}"
: "${COMPOSE_PROJECT_NAME:=omnidesk}"

# 路径解析函数 — 每次调用都基于当前环境变量重算
_upgrades_root() { echo "$OMNIDESK_RUNTIME_ROOT/upgrades"; }
_state_dir()     { echo "$(_upgrades_root)/$UPGRADE_ID"; }
_state_file()    { echo "$(_state_dir)/state.json"; }
_lock_dir()      { echo "$(_state_dir)/upgrade.lock"; }

# ─── 状态机定义 ───────────────────────────────────────────
# 边迁移表(SOURCE:DEST 空格分隔)。SAFE_STOPPED 可由任何状态转入:
STATE_EDGES='INIT:PREFLIGHT_PASSED PREFLIGHT_PASSED:MAINTENANCE_ENABLED MAINTENANCE_ENABLED:BACKUP_CREATED BACKUP_CREATED:BACKUP_VERIFIED BACKUP_VERIFIED:RUNTIME_SNAPSHOT_RECORDED RUNTIME_SNAPSHOT_RECORDED:WRITE_SERVICES_STOPPED WRITE_SERVICES_STOPPED:TARGET_IMAGE_READY TARGET_IMAGE_READY:MIGRATION_PREFLIGHT_PASSED MIGRATION_PREFLIGHT_PASSED:MIGRATED MIGRATED:TARGET_HEALTHY TARGET_HEALTHY:SMOKE_TEST_PASSED SMOKE_TEST_PASSED:COMMITTED COMMITTED:MAINTENANCE_DISABLED'

# ─── JSON 序列化(jq 优先,Python fallback) ───────────────
# build_state_json <state> [k=v ...] — 生成 JSON 对象到 stdout
build_state_json() {
    local state="$1"
    shift
    local now
    now=$(date -u +'%Y-%m-%dT%H:%M:%SZ')

    # 收集所有键值对;缺省字段填 sentinel
    local upgrade_id="$UPGRADE_ID"
    local source_version="" target_version="" channel="" backup_dir=""
    local source_image_tag="" target_image_tag=""
    local kv key val
    for kv in "$@"; do
        key="${kv%%=*}"
        val="${kv#*=}"
        case "$key" in
            source_version)      source_version="$val" ;;
            target_version)      target_version="$val" ;;
            channel)             channel="$val" ;;
            backup_dir)          backup_dir="$val" ;;
            source_image_tag)    source_image_tag="$val" ;;
            target_image_tag)    target_image_tag="$val" ;;
            upgrade_id)          upgrade_id="$val" ;;
            *) echo "WARN: unknown key '$kv'" >&2 ;;
        esac
    done

    # 强制字段补全(允许调用方省略 schema 字段,模块负责填默认值)
    if [ -z "$backup_dir" ]; then
        backup_dir="$OMNIDESK_RUNTIME_ROOT/backups/$UPGRADE_ID"
    fi
    if [ -z "$channel" ]; then
        channel="unknown"
    fi

    # 序列化:优先用 jq;无 jq 用 python3
    if command -v jq >/dev/null 2>&1; then
        jq -n \
            --arg uid "$upgrade_id" \
            --arg sv  "$source_version" \
            --arg tv  "$target_version" \
            --arg ch  "$channel" \
            --arg st  "$state" \
            --arg bd  "$backup_dir" \
            --arg sit "$source_image_tag" \
            --arg tit "$target_image_tag" \
            --arg pn  "$COMPOSE_PROJECT_NAME" \
            --arg now "$now" \
            '{upgrade_id:$uid, source_version:$sv, target_version:$tv, channel:$ch,
              state:$st, backup_dir:$bd, source_image_tag:$sit, target_image_tag:$tit,
              compose_project_name:$pn, updated_at:$now}'
    else
        python3 - "$upgrade_id" "$source_version" "$target_version" "$channel" \
            "$state" "$backup_dir" "$source_image_tag" "$target_image_tag" \
            "$COMPOSE_PROJECT_NAME" "$now" <<'PY_EOF'
import json, sys
keys = ['upgrade_id','source_version','target_version','channel','state',
        'backup_dir','source_image_tag','target_image_tag',
        'compose_project_name','updated_at']
print(json.dumps(dict(zip(keys, sys.argv[1:])), indent=2))
PY_EOF
    fi
}

# ─── 状态机查询 ──────────────────────────────────────────
# is_valid_edge <from> <to> → 0 (valid) / 1 (invalid)
is_valid_edge() {
    local from="$1" to="$2"
    # SAFE_STOPPED 接受任意状态转入
    if [ "$to" = "SAFE_STOPPED" ]; then
        return 0
    fi
    local edge
    for edge in $STATE_EDGES; do
        if [ "$edge" = "${from}:${to}" ]; then
            return 0
        fi
    done
    return 1
}

# current_state [state_file] — 读 state.json 的 state 字段(默认本 UPGRADE_ID 的 state.json)
# 失败时返回 UNKNOWN
current_state() {
    local f="${1:-$(_state_file)}"
    if [ ! -f "$f" ]; then
        echo "UNKNOWN"
        return 0
    fi
    if command -v jq >/dev/null 2>&1; then
        jq -r '.state // "UNKNOWN"' "$f" 2>/dev/null || echo "UNKNOWN"
    else
        python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('state','UNKNOWN'))" "$f" 2>/dev/null || echo "UNKNOWN"
    fi
}

# ─── 升级锁(mkdir 原子) ─────────────────────────────────
# acquire_upgrade_lock → 0 (acquired) / 1 (already held)
acquire_upgrade_lock() {
    local lock_dir state_dir
    state_dir=$(_state_dir)
    lock_dir=$(_lock_dir)
    mkdir -p "$state_dir"
    if mkdir "$lock_dir" 2>/dev/null; then
        echo "$$" > "$lock_dir/pid" 2>/dev/null || true
        return 0
    fi
    return 1
}

# release_upgrade_lock → 0 (released) / 1 (not holder / no lock / already released)
# 强制规则:仅当 pid 文件存在且值等于当前进程 PID 时,才允许删除锁。
# 这样防止并发脚本误删别人的锁目录。
release_upgrade_lock() {
    local lock_dir
    lock_dir=$(_lock_dir)
    if [ ! -d "$lock_dir" ]; then
        # 锁不存在 → 视为"已释放"(幂等)
        return 0
    fi
    local lock_pid
    lock_pid=$(cat "$lock_dir/pid" 2>/dev/null || echo "")
    if [ -z "$lock_pid" ]; then
        echo "ERROR: 升级锁 $lock_dir 存在但缺 pid,拒绝释放(防止误删)。" >&2
        return 1
    fi
    if [ "$lock_pid" != "$$" ]; then
        echo "ERROR: 当前 PID $$ 不是升级锁持有者(锁 pid=$lock_pid),拒绝释放。" >&2
        return 1
    fi
    rm -rf "$lock_dir"
    return 0
}

# ─── 守卫 ──────────────────────────────────────────────
# 任何升级尝试前调用:已有 SAFE_STOPPED 拒绝新升级
assert_no_existing_safe_stop() {
    local upgrades_root
    upgrades_root=$(_upgrades_root)
    if [ ! -d "$upgrades_root" ]; then
        return 0
    fi
    local state_file
    while IFS= read -r -d '' state_file; do
        local st id
        st=$(current_state "$state_file")
        if [ "$st" = "SAFE_STOPPED" ]; then
            id=$(dirname "$state_file" | xargs -I{} basename {})
            echo "ERROR: 已存在 SAFE_STOPPED 升级 '$id',拒绝新升级。" >&2
            echo "  请先人工排查/恢复,再删除 $state_file 后重试。" >&2
            return 1
        fi
    done < <(find "$upgrades_root" -maxdepth 2 -name state.json -print0 2>/dev/null)
    return 0
}

# ─── write_state ───────────────────────────────────────
# write_state <state> [key=value ...]
write_state() {
    local state="$1"
    shift

    # 守卫:已有 SAFE_STOPPED 拒绝新写入
    if ! assert_no_existing_safe_stop; then
        return 1
    fi

    local state_dir state_file
    state_dir=$(_state_dir)
    state_file=$(_state_file)
    mkdir -p "$state_dir"

    local tmp
    tmp=$(mktemp "$state_dir/.state.json.tmp.XXXXXX")
    if ! build_state_json "$state" "$@" > "$tmp"; then
        rm -f "$tmp"
        echo "ERROR: 写入 state.json 失败(build_state_json 错误)" >&2
        return 1
    fi

    if ! mv -f "$tmp" "$state_file"; then
        rm -f "$tmp"
        echo "ERROR: 替换 state.json 失败($state_dir → $state_file)" >&2
        return 1
    fi
}

# ─── transition_state ─────────────────────────────────
# transition_state <expected> <next>
transition_state() {
    local expected="$1" next="$2"
    local state_file cur
    state_file=$(_state_file)
    cur=$(current_state "$state_file")
    if [ "$cur" != "$expected" ]; then
        echo "ERROR: 状态转换被拒绝:当前 [$cur],期望 [$expected] → [$next]" >&2
        return 1
    fi
    if ! is_valid_edge "$expected" "$next"; then
        echo "ERROR: 非法状态转换 [$expected] → [$next]" >&2
        return 1
    fi
    write_state "$next"
}

# ─── enter_safe_stop ──────────────────────────────────
# enter_safe_stop <reason>
# 流程:
#   1. 读已有 state.json(若有),保留所有上下文字段
#   2. best-effort 停 Backend/Worker/Beat/frontend(失败也继续)
#   3. 写 SAFE_STOPPED 状态(覆盖 state/updated_at/reason/stop_failures,保留其他字段)
#   4. 输出恢复信息
#   5. stop 全部失败时返回非零
enter_safe_stop() {
    local reason="${1:-forced safe stop}"
    local stop_rc=0
    local failures=()

    # 1. 尝试停业务服务(best-effort,失败也继续写状态)
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local compose_cmd=""
    if [ -f "$script_dir/../compose/docker-compose.offline.yml" ]; then
        compose_cmd="docker compose -f $script_dir/../compose/docker-compose.offline.yml --env-file $script_dir/../compose/.env.production"
    elif [ -f "$script_dir/docker-compose.offline.yml" ]; then
        compose_cmd="docker compose -f $script_dir/docker-compose.offline.yml --env-file $script_dir/.env.production"
    fi

    if [ -n "$compose_cmd" ]; then
        for svc in backend worker beat frontend; do
            if $compose_cmd stop "$svc" >/dev/null 2>&1; then
                :
            else
                failures+=("$svc")
            fi
        done
    else
        failures+=("no-compose-file")
    fi

    # 2. 写 SAFE_STOPPED 状态(必须写入;即使前面 stop 全失败)
    local now
    now=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
    local stop_failure_summary
    if [ "${#failures[@]}" -gt 0 ]; then
        stop_failure_summary=$(IFS=,; echo "${failures[*]}")
    else
        stop_failure_summary="none"
    fi

    local state_dir state_file
    state_dir=$(_state_dir)
    state_file=$(_state_file)
    mkdir -p "$state_dir"
    local tmp
    tmp=$(mktemp "$state_dir/.state.json.tmp.XXXXXX")

    # 序列化:优先 jq,无 jq 用 python
    # 用 jq slurpfile 读取已有 state.json 作为输入;若无则用 null,后续 . // {} 处理
    if command -v jq >/dev/null 2>&1; then
        # 构建 jq 表达式:从已有 state.json 加载,排除 state/updated_at/reason/stop_failures,
        # 再覆盖 4 个核心字段。输出到 tmp 文件。
        local jq_input='.'
        if [ ! -f "$state_file" ]; then
            jq_input='null'
        fi
        # 用 --slurpfile 读已有 state.json(若存在);否则用 null
        local jq_args=()
        if [ -f "$state_file" ]; then
            jq_args=(--slurpfile existing "$state_file")
            jq_input='$existing[0]'
        fi
        # jq 表达式:从已有对象剔除将被覆盖的 4 个字段,再 merge 新字段
        if ! jq -n \
            --arg st  "SAFE_STOPPED" \
            --arg now "$now" \
            --arg reason "$reason" \
            --arg stopfails "$stop_failure_summary" \
            "${jq_args[@]}" \
            "(${jq_input} // {}) | del(.state, .updated_at, .reason, .stop_failures) + {state: \$st, updated_at: \$now, reason: \$reason, stop_failures: \$stopfails}" > "$tmp"; then
            rm -f "$tmp"
            echo "ERROR: enter_safe_stop 写状态失败(jq)" >&2
            return 1
        fi
    else
        # Python fallback:读已有 state.json,merge 后写回
        if ! python3 -c "
import json, os, sys
existing = {}
state_file = sys.argv[1]
if os.path.isfile(state_file):
    with open(state_file) as f:
        existing = json.load(f)
# 移除将被覆盖的字段
for k in ['state', 'updated_at', 'reason', 'stop_failures']:
    existing.pop(k, None)
existing['state'] = 'SAFE_STOPPED'
existing['updated_at'] = sys.argv[2]
existing['reason'] = sys.argv[3]
existing['stop_failures'] = sys.argv[4]
with open(sys.argv[5], 'w') as f:
    json.dump(existing, f, indent=2)
" "$state_file" "$now" "$reason" "$stop_failure_summary" "$tmp"; then
            rm -f "$tmp"
            echo "ERROR: enter_safe_stop 写状态失败(python)" >&2
            return 1
        fi
    fi

    # mv 必须有错误处理 — 写临时文件后原子替换,失败时清理 tmp + 报错
    if ! mv -f "$tmp" "$state_file"; then
        rm -f "$tmp"
        echo "ERROR: enter_safe_stop 替换 state.json 失败($state_dir → $state_file)" >&2
        return 1
    fi

    # 3. 输出恢复信息
    {
        echo ""
        echo "=========================================="
        echo "  SAFE_STOPPED 状态已记录"
        echo "  upgrade_id: $UPGRADE_ID"
        echo "  reason: $reason"
        echo "  stop_failures: $stop_failure_summary"
        echo ""
        echo "  恢复步骤:"
        echo "    1. 排查失败服务(stop_failures 列表)"
        echo "    2. 必要时手动恢复: cd <bundle> && ./scripts/upgrade.sh"
        echo "    3. 清理 SAFE_STOPPED 标记: rm $state_file"
        echo "=========================================="
    } >&2

    # 4. 退出码:stop 失败时返回非零
    if [ "${#failures[@]}" -gt 0 ]; then
        stop_rc=1
    fi
    return "$stop_rc"
}
