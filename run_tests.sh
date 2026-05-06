#!/bin/bash
# OmniDesk 统一测试运行脚本
# 用法: ./run_tests.sh [backend|frontend|all]

set -e

MODE="${1:-all}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== OmniDesk 测试运行器 ===${NC}\n"

# 运行 Backend 测试
run_backend() {
    echo -e "${YELLOW}>>> 运行 Backend 测试 (pytest)...${NC}"
    cd "$PROJECT_ROOT/omni_desk_backend"

    # 检查依赖
    if ! python -c "import pytest" 2>/dev/null; then
        echo -e "${RED}错误: pytest 未安装${NC}"
        echo "请运行: pip install -r requirements-dev.txt"
        exit 1
    fi

    pytest --cov=. --cov-report=term-missing --cov-report=html -v
    echo -e "${GREEN}Backend 测试完成!${NC}"
    echo -e "覆盖率报告: $PROJECT_ROOT/omni_desk_backend/htmlcov/index.html"
}

# 运行 Frontend 测试
run_frontend() {
    echo -e "${YELLOW}>>> 运行 Frontend 测试 (Jest)...${NC}"
    cd "$PROJECT_ROOT/omni_desk_frontend"

    # 检查依赖
    if ! npm ls jest 2>/dev/null | grep -q "jest"; then
        echo -e "${RED}错误: npm 依赖未安装${NC}"
        echo "请运行: cd omni_desk_frontend && npm install"
        exit 1
    fi

    npm run test:coverage -- --watchAll=false
    echo -e "${GREEN}Frontend 测试完成!${NC}"
    echo -e "覆盖率报告: $PROJECT_ROOT/omni_desk_frontend/coverage/index.html"
}

# 运行所有测试
run_all() {
    run_backend
    echo ""
    run_frontend
    echo -e "${GREEN}=== 所有测试完成 ===${NC}"
}

# 显示帮助
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  all       运行所有测试 (默认)"
    echo "  backend   只运行后端 pytest"
    echo "  frontend  只运行前端 jest"
    echo "  help      显示此帮助"
    echo ""
    echo "示例:"
    echo "  ./run_tests.sh         # 运行所有测试"
    echo "  ./run_tests.sh backend  # 只测试后端"
}

# 根据模式执行
case "$MODE" in
    backend)
        run_backend
        ;;
    frontend)
        run_frontend
        ;;
    all)
        run_all
        ;;
    help)
        show_help
        ;;
    *)
        echo "无效选项: $MODE"
        echo ""
        show_help
        exit 1
        ;;
esac
