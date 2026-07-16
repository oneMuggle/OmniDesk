#!/bin/bash
# L3 E2E smoke test for channel-sync cherry-pick logic

set -uo pipefail

TESTDIR=$(mktemp -d)
trap "rm -rf $TESTDIR" EXIT

echo "=== Dry-run channel-sync cherry-pick in $TESTDIR ==="

cd "$TESTDIR"
git init --quiet --bare source.git
git init --quiet --bare target.git
git clone --quiet source.git src
cd src
git config user.email "test@test.com"
git config user.name "Test"
echo "v1" > file.txt
git add . && git commit -q -m "fix: init"
git push -q origin main

cd "$TESTDIR"
git clone --quiet target.git tgt
cd tgt
git config user.email "test@test.com"
git config user.name "Test"
git pull -q origin main
echo "v1 conflict" > file.txt
git add . && git commit -q -m "feat: change"
git push -q origin main

cd "$TESTDIR/src"
echo "v2 fix" > file.txt
git add . && git commit -q -m "fix(scope): test cherry-pick"
NEW_FIX=$(git rev-parse HEAD)

cd "$TESTDIR/tgt"
echo "--- Cherry-picking $NEW_FIX ---"
git cherry-pick -x "$NEW_FIX" 2>&1 || echo "(expected conflict)"

if git diff --name-only --diff-filter=U | grep -q .; then
  echo "✓ CONFLICT DETECTED (expected)"
  echo "Conflicted files:"
  git diff --name-only --diff-filter=U
  echo ""
  echo "would_conflict=true"
  exit 0
else
  echo "✗ NO CONFLICT (test scenario broken)"
  exit 1
fi
