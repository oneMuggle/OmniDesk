#!/usr/bin/env bash
# test_deploy_offline_syntax.sh — 防 case 跨分支 bash-only 语法回归测试
#
# 背景(2026-08-27 用户报告):
#   deploy_offline.sh 的 clean 分支用了 bash 进程替换 `done < <(find ...)`,
#   bash 在 case 解析阶段会扫描所有分支的语法,即使只跑 start 也会撞
#   "syntax error near unexpected token '<'"(line 388)。
#
# 覆盖目标:
#   S1: 源码不含 bash 进程替换 `<(...)`(除注释外)
#   S2: bash -n 静态语法检查通过
#   S3: 真跑无害命令(status / nonexistent),case 解析期不报错
#   S4: 跑 clean --help,case 解析期不报错(原 bug 所在地)
#   S5: 源码 grep `done < <(` 必须 0 命中
#   S6: mktemp + 重定向替代方案已落地(SF_LIST mktemp + rm -f)
#
# 使用方法:
#   bash deployment/docker/tests/test_deploy_offline_syntax.sh
#
# 设计:
#   - 复制 deploy_offline.sh 到临时 bundle,避免污染源码树
#   - 用 stub docker 拦截 docker compose 调用
#   - 不依赖真实 docker / 网络
#   - CI 通过 tests/test_*.sh glob 自动拾取本测试(无需 CI 改动)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ─── 内联 assertion helpers ──────────────────────────────────
PASS_COUNT=0
FAIL_COUNT=0
FAILED_CASES=()

pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS: $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); FAILED_CASES+=("$1"); echo "  FAIL: $1"; }

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
echo "  deploy_offline.sh 语法防回归测试"
echo "=========================================="

# 1. 前置 — 源文件存在
[ -f "$ROOT/deploy_offline.sh" ] || { echo "FATAL: $ROOT/deploy_offline.sh missing"; exit 2; }

# ─── S1 / S5: 源码层面无 bash 进程替换 ─────────────────────────
echo ""
echo "--- S1/S5: 源码无 bash 进程替换 ---"
# S1:排除注释行(行首为 #)后再查 `<(`
BASH_PROC_SUB_LINES=$(grep -nE '^[[:space:]]*[^#]*(<|\<)[ \t]*\(' "$ROOT/deploy_offline.sh" 2>/dev/null || true)
if [ -z "$BASH_PROC_SUB_LINES" ]; then
    pass "S1 源码无非注释的 <(...) 进程替换"
else
    fail "S1 源码发现 bash 进程替换(违反 case 跨分支解析约束):
$BASH_PROC_SUB_LINES"
fi
# S5:同样排除注释行后断言 `done < <(` 必须 0 命中
# 用 awk 数行(grep -c + || true 会污染 stdout,导致 "0\n0")
DONE_PROC_SUB=$(awk '
    /^[[:space:]]*[^#].*done[[:space:]]+<[[:space:]]+<\(/ { c++ }
    END { print c+0 }
' "$ROOT/deploy_offline.sh")
if [ "$DONE_PROC_SUB" -eq 0 ]; then
    pass "S5 done < <( 出现次数 = 0(排除注释行)"
else
    fail "S5 done < <( 出现次数 = $DONE_PROC_SUB (必须为 0)"
    grep -nE '^[[:space:]]*[^#]*done[[:space:]]+<[[:space:]]+<\(' "$ROOT/deploy_offline.sh"
fi

# ─── S2: bash -n 静态语法检查 ───────────────────────────────
echo ""
echo "--- S2: bash -n 静态语法检查 ---"
if bash -n "$ROOT/deploy_offline.sh" 2>/dev/null; then
    pass "S2 bash -n $ROOT/deploy_offline.sh 通过"
else
    fail "S2 bash -n $ROOT/deploy_offline.sh 失败"
    bash -n "$ROOT/deploy_offline.sh" || true
fi

# ─── S3 / S4: 运行时 case 解析不报错 ─────────────────────────
echo ""
echo "--- S3/S4: case 解析不报错 ---"
TEST_TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TEST_TMPDIR"' EXIT

# stub docker:让所有 docker 调用返回 0;模拟 ragflow/mysql 镜像缺失,
# # 模拟 redis 容器 healthy(让 wait_for_healthy 不超时)
STUB_BIN="$TEST_TMPDIR/stub_bin"
mkdir -p "$STUB_BIN"
DOCKER_LOG="$STUB_BIN/docker.log"
: > "$DOCKER_LOG"
cat > "$STUB_BIN/docker" <<STUB_EOF
#!/bin/bash
echo "ARGS: \$*" >> "$DOCKER_LOG"
case "\$1" in
    compose)
        case "\$2" in
            version) echo "Docker Compose version v2.27.0"; exit 0 ;;
            ps)      exit 0 ;;
            *)       exit 0 ;;
        esac
        ;;
    image)
        # docker image inspect:模拟"ragflow/mysql 镜像缺失"让脚本走 fallback
        exit 1
        ;;
    inspect)
        # 模拟容器 healthy(让 wait_for_healthy 通过)
        if echo "\$*" | grep -q "State.Health"; then
            echo '{"Status":"healthy"}'
            exit 0
        fi
        exit 0
        ;;
    load)
        exit 0
        ;;
    *)
        exit 0
        ;;
esac
STUB_EOF
chmod +x "$STUB_BIN/docker"

# 创建假 bundle 布局
BUNDLE="$TEST_TMPDIR/bundle"
mkdir -p "$BUNDLE/scripts" "$BUNDLE/compose"
cp "$ROOT/deploy_offline.sh" "$BUNDLE/scripts/deploy_offline.sh"
chmod +x "$BUNDLE/scripts/deploy_offline.sh"
cat > "$BUNDLE/compose/docker-compose.offline.yml" <<'COMPOSE_EOF'
name: ${COMPOSE_PROJECT_NAME:?COMPOSE_PROJECT_NAME must be set}
services:
  db:
    image: postgres:14-alpine
volumes:
  postgres_data:
    name: ${OMNIDESK_POSTGRES_VOLUME}
COMPOSE_EOF
cat > "$BUNDLE/compose/.env.production" <<'ENV_EOF'
COMPOSE_PROJECT_NAME=omnidesk-rc
OMNIDESK_POSTGRES_VOLUME=omnidesk-rc-postgres-data
OMNIDESK_BACKUP_ROOT=/tmp/omnidesk-test-backups
OMNIDESK_RUNTIME_ROOT=/tmp/omnidesk-test-runtime
BACKEND_IMAGE_TAG=v0.7.0
FRONTEND_IMAGE_TAG=v0.7.0
POSTGRES_DB=testdb
POSTGRES_USER=testuser
POSTGRES_PASSWORD=testpass
SECRET_KEY=testsecretkey
REDIS_PASSWORD=testredispass
CHANNEL=rc
ENV_EOF

# S3a: 跑 nonexistent 命令触发 *) 分支,确认整份脚本解析通过
echo ""
echo "--- S3a: nonexistent 命令触发 *) 分支 ---"
set +e
PATH="$STUB_BIN:$PATH" \
    bash "$BUNDLE/scripts/deploy_offline.sh" nonexistent \
    > "$TEST_TMPDIR/nonexistent.stdout" 2> "$TEST_TMPDIR/nonexistent.stderr"
RC=$?
set -e
if grep -qiE 'syntax error' "$TEST_TMPDIR/nonexistent.stderr"; then
    fail "S3a 撞 syntax error(回归!)"
    cat "$TEST_TMPDIR/nonexistent.stderr" | head -10
else
    pass "S3a nonexistent 命令无 syntax error (rc=$RC)"
fi
if grep -q "Usage:" "$TEST_TMPDIR/nonexistent.stdout"; then
    pass "S3a nonexistent 触发 *) 分支,输出 Usage"
else
    fail "S3a nonexistent 未触发 *) 分支"
fi

# S3b: 跑 status 命令确认 case 解析(start 分支前面的命令)
echo ""
echo "--- S3b: status 命令 ---"
set +e
PATH="$STUB_BIN:$PATH" \
    bash "$BUNDLE/scripts/deploy_offline.sh" status \
    > "$TEST_TMPDIR/status.stdout" 2> "$TEST_TMPDIR/status.stderr"
RC=$?
set -e
if grep -qiE 'syntax error' "$TEST_TMPDIR/status.stderr"; then
    fail "S3b status 撞 syntax error(回归!)"
else
    pass "S3b status 无 syntax error (rc=$RC)"
fi

# S4: 跑 clean --help —— 原 bug 所在的分支
# clean --help 在原脚本里是 case 内 --help 分支输出 Usage 然后 exit 0,
# 这会真的执行到 clean 分支的语法(就是 line 388 之前的代码)。
echo ""
echo "--- S4: clean --help 触达原 bug 所在分支 ---"
set +e
PATH="$STUB_BIN:$PATH" \
    bash "$BUNDLE/scripts/deploy_offline.sh" clean --help \
    > "$TEST_TMPDIR/clean-help.stdout" 2> "$TEST_TMPDIR/clean-help.stderr"
RC=$?
set -e
if grep -qiE 'syntax error' "$TEST_TMPDIR/clean-help.stderr"; then
    fail "S4 clean --help 撞 syntax error(回归 line 388)"
    cat "$TEST_TMPDIR/clean-help.stderr" | head -10
else
    pass "S4 clean --help 无 syntax error (rc=$RC)"
fi

# ─── S6: mktemp + 重定向替代方案已落地 ──────────────────────
echo ""
echo "--- S6: mktemp 替代方案已落地 ---"
# SF_LIST="$(mktemp)" 的形式(`SF_LIST=` + `mktemp`)
assert_contains "$ROOT/deploy_offline.sh" "SF_LIST=.*mktemp" "S6 mktemp 替代:SF_LIST 创建"
# rm -f "$SF_LIST" 的形式(允许空格、可选引号)
assert_contains "$ROOT/deploy_offline.sh" 'rm -f[[:space:]]+"?\$SF_LIST"?' "S6 临时文件清理"

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