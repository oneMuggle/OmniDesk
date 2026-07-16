#!/bin/bash
# L3 E2E smoke test for channel-sync cherry-pick logic

set -uo pipefail

TESTDIR=$(mktemp -d)
trap "rm -rf $TESTDIR" EXIT

echo "=== Dry-run channel-sync cherry-pick in $TESTDIR ==="

# 1. One shared bare repo as "origin"
cd "$TESTDIR"
git init --quiet --bare origin.git

# 2. Source branch clones origin, adds init commit
git clone --quiet origin.git src
cd src
git config user.email "test@test.com"
git config user.name "Test"
echo "v1" > file.txt
git add . && git commit -q -m "fix: init"
git push -q origin main

# 3. Target branch clones origin (same base as source), then diverges
cd "$TESTDIR"
git clone --quiet origin.git tgt
cd tgt
git config user.email "test@test.com"
git config user.name "Test"
echo "v1 conflict" > file.txt
git add . && git commit -q -m "feat: change"
git push -q origin main

# 4. Source branch creates NEW_FIX
cd "$TESTDIR/src"
echo "v2 fix" > file.txt
git add . && git commit -q -m "fix(scope): test cherry-pick"
NEW_FIX=$(git rev-parse HEAD)

# 5. Target fetches source's NEW_FIX commit directly from src
# (src does not push NEW_FIX to origin because tgt already advanced main there;
#  fetching directly from src's local repo avoids the non-fast-forward issue)
cd "$TESTDIR/tgt"
git fetch -q "$TESTDIR/src" "$NEW_FIX"

# 6. Try cherry-pick - should conflict because file.txt differs
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
