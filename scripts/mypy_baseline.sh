#!/usr/bin/env bash
# mypy 错误基线验证脚本
# 用法:
#   bash scripts/mypy_baseline.sh           # 检查整个 backend
#   bash scripts/mypy_baseline.sh <path>    # 检查指定子目录
# 输出: mypy 末行 "Found N errors in M files (checked K source files)"
set -euo pipefail
TARGET="${1:-.}"
cd "$(dirname "$0")/../omni_desk_backend"
mypy "${TARGET}" --ignore-missing-imports --no-error-summary 2>&1 | tail -3
