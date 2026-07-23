#!/bin/bash
# test_deploy_image_tags.sh — 单元测试: deploy.sh IMAGE_TAG 派生逻辑
#
# 覆盖场景:
#   T1: 有 BUILD-MANIFEST.json + backend.name=v0.5.7 → IMAGE_TAG 应从 manifest 派生
#   T2: 有 manifest 但 backend.name/frontend.name 字段缺失 → IMAGE_TAG 保留原值
#   T3: 无 BUILD-MANIFEST.json (legacy, VERSION=v0.5.9) → 走 VERSION 派生路径
#   T4: 有 manifest + 无 jq (PATH 把 jq 隐藏) → grep fallback 正确解析
#
# 使用方法:
#   bash deployment/docker/tests/test_deploy_image_tags.sh
#
# 注意:
#   - 测试只覆盖 generate_env() 的 IMAGE_TAG 派生
#   - 用 awk 从 deploy.sh 提取该函数,避免 source 整个脚本触发的副作用(set -e / cd / main case)

set -u

DEPLOY_SH="${1:-deployment/docker/omnidesk-offline-v0.5.9/scripts/deploy.sh}"
if [ ! -f "$DEPLOY_SH" ]; then
    echo "FAIL: deploy.sh not found: $DEPLOY_SH"
    echo "用法: $0 [path/to/deploy.sh]"
    exit 2
fi

# 从 deploy.sh 提取 generate_env 函数(从 "generate_env() {" 到下一个第一列 "}")
GENERATE_ENV_FN=$(awk '
    /^generate_env\(\) \{/ { capture=1 }
    capture { print }
    capture && /^\}$/ { exit }
' "$DEPLOY_SH")

if [ -z "$GENERATE_ENV_FN" ]; then
    echo "FAIL: 无法从 deploy.sh 提取 generate_env 函数"
    exit 2
fi

PASS=0
FAIL=0
FAILED_CASES=()

# ─── Fixture 模板 ─────────────────────────────────────────────
make_bundle() {
    local tmpdir="$1"
    local with_manifest="$2"  # "yes" / "no"
    local manifest_content="$3"
    local version_content="$4"
    local env_initial="$5"

    mkdir -p "$tmpdir/compose" "$tmpdir/config"
    echo -n "$version_content" > "$tmpdir/VERSION"

    if [ "$with_manifest" = "yes" ]; then
        printf '%s' "$manifest_content" > "$tmpdir/BUILD-MANIFEST.json"
    fi

    # generate_env 函数会:
    #   1. 检查 config/.env.production(已存在),直接 cp 到 compose/.env.production
    #   2. 然后 sed 改 IMAGE_TAG 写回 compose/.env.production
    # 因此两边都要存在
    cat > "$tmpdir/config/.env.production" <<EOF
# generated
POSTGRES_DB=test
BACKEND_IMAGE_TAG=${env_initial}
FRONTEND_IMAGE_TAG=${env_initial}
EOF

    # compose/.env.production 一开始为空,generate_env 会先 cp 然后 sed
    : > "$tmpdir/compose/.env.production"
}

run_case() {
    local case_name="$1"
    local tmpdir="$2"
    local expected_backend="$3"
    local expected_frontend="$4"
    local jq_hide_dir="$5"

    (
        cd "$tmpdir"
        export BUNDLE_DIR="$tmpdir"

        if [ -n "$jq_hide_dir" ]; then
            export PATH="$jq_hide_dir:$PATH"
        fi

        # 把提取的函数体 eval 进当前 subshell
        eval "$GENERATE_ENV_FN"

        # 调用 generate_env(只读文件,不调 docker)
        generate_env >/dev/null 2>&1

        local got_backend
        local got_frontend
        got_backend=$(grep -E "^BACKEND_IMAGE_TAG=" compose/.env.production | cut -d= -f2)
        got_frontend=$(grep -E "^FRONTEND_IMAGE_TAG=" compose/.env.production | cut -d= -f2)

        if [ "$got_backend" = "$expected_backend" ] && [ "$got_frontend" = "$expected_frontend" ]; then
            echo "  PASS [$case_name]: backend=$got_backend, frontend=$got_frontend"
            exit 0
        else
            echo "  FAIL [$case_name]:"
            echo "    expected backend=$expected_backend, frontend=$expected_frontend"
            echo "    got      backend=$got_backend,      frontend=$got_frontend"
            exit 1
        fi
    )
    local rc=$?
    if [ $rc -eq 0 ]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        FAILED_CASES+=("$case_name")
    fi
}

# ─── T1: 有 manifest, backend=v0.5.7 ─────────────────────────
TMP1=$(mktemp -d)
make_bundle "$TMP1" "yes" \
'{
  "version": "0.5.9",
  "build_time": "2026-07-04T11:19:08Z",
  "git_sha": "a838764",
  "images": {
    "backend":  { "name": "omni-desk-backend-prod:v0.5.7" },
    "frontend": { "name": "omni-desk-frontend-prod:v0.5.6" }
  }
}' \
"0.5.9" "v0.4.0"

run_case "T1-manifest-backend-v0.5.7" "$TMP1" "v0.5.7" "v0.5.6" ""
rm -rf "$TMP1"

# ─── T2: 有 manifest 但 images 字段缺失 ──────────────────────
TMP2=$(mktemp -d)
make_bundle "$TMP2" "yes" \
'{
  "version": "0.5.9",
  "git_sha": "a838764"
}' \
"0.5.9" "v0.4.0"

run_case "T2-manifest-missing-images" "$TMP2" "v0.4.0" "v0.4.0" ""
rm -rf "$TMP2"

# ─── T3: 无 manifest (legacy), VERSION=v0.5.9 ─────────────────
TMP3=$(mktemp -d)
make_bundle "$TMP3" "no" "" "0.5.9" "v0.4.0"

run_case "T3-no-manifest-legacy-version" "$TMP3" "v0.5.9" "v0.5.9" ""
rm -rf "$TMP3"

# ─── T4: 有 manifest + 无 jq (grep fallback) ──────────────────
TMP4=$(mktemp -d)
make_bundle "$TMP4" "yes" \
'{
  "version": "0.5.9",
  "build_time": "2026-07-04T11:19:08Z",
  "git_sha": "a838764",
  "images": {
    "backend":  { "name": "omni-desk-backend-prod:v0.5.7" },
    "frontend": { "name": "omni-desk-frontend-prod:v0.5.6" }
  }
}' \
"0.5.9" "v0.4.0"

# JQFREE_DIR 是空目录,放 PATH 前会隐藏系统 jq(command -v jq 失败 → 走 grep fallback)
JQFREE_DIR=$(mktemp -d)

run_case "T4-grep-fallback-no-jq" "$TMP4" "v0.5.7" "v0.5.6" "$JQFREE_DIR"
rm -rf "$TMP4"
rm -rf "$JQFREE_DIR"

# ─── 总结 ─────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  deploy.sh IMAGE_TAG 派生逻辑测试"
echo "=========================================="
echo "  PASS: $PASS / $((PASS + FAIL))"
if [ "$FAIL" -gt 0 ]; then
    echo "  FAIL: $FAIL"
    echo "  失败用例: ${FAILED_CASES[*]}"
    exit 1
fi
echo "  全部通过"
echo "=========================================="
exit 0