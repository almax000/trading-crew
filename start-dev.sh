#!/bin/bash
#
# TradingCrew 本地开发启动脚本
#
# 需要安装:
#   - Python 3.11+
#   - Bun (https://bun.sh)
#
# 使用方法:
#   ./start-dev.sh          # 启动所有服务
#   ./start-dev.sh python   # 仅启动 Python 分析服务
#   ./start-dev.sh web      # 仅启动 Web 服务
#

set -e

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# 加载 .env 文件
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 设置 Python 路径
export PYTHONPATH="${PYTHONPATH}:${PROJECT_ROOT}"

start_python() {
    echo "Starting Python Analysis Service on port 8000..."
    cd "$PROJECT_ROOT"
    python -m uvicorn analysis_service.main:app --host 127.0.0.1 --port 8000 --reload
}

start_web() {
    echo "Starting Bun Web Service on port ${PORT:-1788}..."
    cd "$PROJECT_ROOT/web"

    # 确保依赖已安装
    if [ ! -d "node_modules" ]; then
        echo "Installing dependencies..."
        bun install
    fi

    bun run dev
}

start_all() {
    echo "┌─────────────────────────────────────────────┐"
    echo "│     TradingCrew - Local Development        │"
    echo "└─────────────────────────────────────────────┘"
    echo ""

    # 启动 Python 服务（后台）
    start_python &
    PYTHON_PID=$!
    echo "Python service PID: $PYTHON_PID"

    # 等待 Python 服务就绪
    echo "Waiting for Analysis Service..."
    for i in $(seq 1 15); do
        if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
            echo "✓ Analysis Service is ready"
            break
        fi
        sleep 1
    done

    # 启动 Web 服务（前台）
    echo ""
    start_web

    # 清理
    kill $PYTHON_PID 2>/dev/null || true
}

case "${1:-all}" in
    python)
        start_python
        ;;
    web)
        start_web
        ;;
    all|*)
        start_all
        ;;
esac
