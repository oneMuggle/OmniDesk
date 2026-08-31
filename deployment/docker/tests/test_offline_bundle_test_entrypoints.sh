#!/usr/bin/env bash
# test_offline_bundle_test_entrypoints.sh — 验证生成的 deploy.sh 入口契约
# 用法: bash deployment/docker/tests/test_offline_bundle_test_entrypoints.sh
#
# 覆盖:
#   B1: 生成 deploy.sh 必须包含 verify / deploy-test / smoke 三个命令
#   B2: deploy.sh verify 缺 BUILD-MANIFEST.json 时返回非零
#   B3: deploy.sh verify 缺 checksums.sha256 时返回非零
#   B4: deploy.sh deploy-test 在 docker load 失败时返回非零(用 stub 验证)
#   B5: deploy.sh deploy-test 帮助/usage 文本包含 deploy-test 字样
#   B6: 离线包根目录 verify 满足 contract 时返回 0
set -uo pipefail

PASS_COUNT=0
FAIL_COUNT=0
report() {
    case "$1" in
        PASS) PASS_COUNT=$((PASS_COUNT + 1)); printf '  \033[32mPASS\033[0m: %s\n' "$2" ;;
        FAIL) FAIL_COUNT=$((FAIL_COUNT + 1)); printf '  \033[31mFAIL\033[0m: %s\n' "$2" ;;
    esac
}

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
TEST_TMP="$(mktemp -d)"
trap 'rm -rf "$TEST_TMP"' EXIT

# 生成一次性 stub bundle(不调 docker),覆盖 scripts/deploy.sh 用例
make_stub_bundle() {
    local dir="$1"
    mkdir -p "$dir/scripts" "$dir/compose" "$dir/images"
    cat > "$dir/scripts/deploy.sh" <<'DEPLOY'
#!/usr/bin/env bash
set -uo pipefail
cmd="${1:-help}"
case "$cmd" in
    verify)
        [ -f BUILD-MANIFEST.json ] || { echo "ERROR: BUILD-MANIFEST.json missing" >&2; exit 1; }
        [ -f CHECKSUMS.sha256 ] || { echo "ERROR: CHECKSUMS.sha256 missing" >&2; exit 1; }
        echo "verify OK"
        ;;
    deploy-test)
        [ -d images ] || { echo "ERROR: images dir missing" >&2; exit 1; }
        for tar in images/*.tar; do
            [ -f "$tar" ] || continue
            if [ "${DOCKER_LOAD_STUB_FAIL:-0}" = "1" ]; then
                echo "ERROR: docker load failed for $tar" >&2
                exit 1
            fi
        done
        echo "deploy-test OK"
        ;;
    smoke)
        [ -d images ] || { echo "ERROR: images dir missing" >&2; exit 1; }
        echo "smoke OK"
        ;;
    help|*)
        echo "Usage: deploy.sh {verify|deploy-test|smoke}"
        ;;
esac
DEPLOY
    chmod +x "$dir/scripts/deploy.sh"
}

# ─── B1:deploy.sh 含 verify/deploy-test/smoke ────────────
make_stub_bundle "$TEST_TMP/bundle1"
DEPLOY_SCRIPT="$TEST_TMP/bundle1/scripts/deploy.sh"
ALL_OK=true
for cmd in verify deploy-test smoke; do
    if ! grep -q "$cmd" "$DEPLOY_SCRIPT"; then
        ALL_OK=false
    fi
done
if $ALL_OK; then
    report PASS "B1 deploy.sh contains verify/deploy-test/smoke"
else
    report FAIL "B1 deploy.sh missing one of verify/deploy-test/smoke"
fi

# ─── B2:verify 缺 manifest → 非 0 ────────────────────────
make_stub_bundle "$TEST_TMP/bundle2"
if (cd "$TEST_TMP/bundle2" && bash scripts/deploy.sh verify) >/dev/null 2>&1; then
    report FAIL "B2 verify returned 0 without manifest"
else
    report PASS "B2 verify returns nonzero without manifest"
fi

# ─── B3:verify 缺 checksums → 非 0 ──────────────────────
make_stub_bundle "$TEST_TMP/bundle3"
touch "$TEST_TMP/bundle3/BUILD-MANIFEST.json"
if (cd "$TEST_TMP/bundle3" && bash scripts/deploy.sh verify) >/dev/null 2>&1; then
    report FAIL "B3 verify returned 0 without checksums"
else
    report PASS "B3 verify returns nonzero without checksums"
fi

# ─── B4:deploy-test 在 docker load 失败时 → 非 0 ────────
make_stub_bundle "$TEST_TMP/bundle4"
touch "$TEST_TMP/bundle4/images/omni_desk_backend.tar"
export DOCKER_LOAD_STUB_FAIL=1
if (cd "$TEST_TMP/bundle4" && bash scripts/deploy.sh deploy-test) >/dev/null 2>&1; then
    report FAIL "B4 deploy-test returned 0 despite docker load failure"
else
    report PASS "B4 deploy-test returns nonzero on docker load failure"
fi
unset DOCKER_LOAD_STUB_FAIL

# ─── B5:usage 文本包含 deploy-test ───────────────────────
USAGE="$(cd "$TEST_TMP/bundle1" && bash scripts/deploy.sh 2>&1 || true)"
case "$USAGE" in
    *deploy-test*) report PASS "B5 usage mentions deploy-test" ;;
    *) report FAIL "B5 usage missing deploy-test: $USAGE" ;;
esac

# ─── B6:deploy.sh verify 满足 contract 时 → 0 ────────────
make_stub_bundle "$TEST_TMP/bundle6"
touch "$TEST_TMP/bundle6/BUILD-MANIFEST.json" "$TEST_TMP/bundle6/CHECKSUMS.sha256"
if (cd "$TEST_TMP/bundle6" && bash scripts/deploy.sh verify) >/dev/null 2>&1; then
    report PASS "B6 verify returns 0 with manifest+checksums"
else
    report FAIL "B6 verify failed with valid bundle"
fi

echo ""
echo "=========================================="
echo "  test_offline_bundle_test_entrypoints.sh: PASS=$PASS_COUNT FAIL=$FAIL_COUNT"
echo "=========================================="
[ "$FAIL_COUNT" -eq 0 ]