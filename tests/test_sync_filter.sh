#!/usr/bin/env bash
# Test: commit type filter for channel-sync
# 用法: ./tests/test_sync_filter.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES="$SCRIPT_DIR/fixtures/sync_pr_scenarios.json"

# 通过 stdin 喂 JSON, 返回 JSON 结果
run_filter() {
    python3 -c "
import json, sys
sys.path.insert(0, '$SCRIPT_DIR/lib')
from sync_filter import filter_syncable
data = json.loads(sys.stdin.read())
for case in data['cases']:
    subjects = case['subjects']
    should, indices = filter_syncable(subjects)
    expected_trigger = case['expected_trigger']
    expected_commits = case['expected_commits']
    ok = (should == expected_trigger) and (indices == expected_commits)
    print(f\"{case['name']}: {'PASS' if ok else 'FAIL'}\")
    if not ok:
        print(f\"  expected trigger={expected_trigger}, commits={expected_commits}\")
        print(f\"  got      trigger={should}, commits={indices}\")
        sys.exit(1)
"
}

run_filter < "$FIXTURES"
echo "ALL TESTS PASSED"
