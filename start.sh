#!/bin/bash
#
# TradingCrew 启动脚本
#
# 同时启动 Python 分析服务和 Bun Web 服务
#

set -e

echo "┌─────────────────────────────────────────────┐"
echo "│     TradingCrew - Starting Services         │"
echo "└─────────────────────────────────────────────┘"

# 设置 Python 路径
export PYTHONPATH="${PYTHONPATH}:/app"

# 启动 Python 分析服务（后台运行）
echo ""
echo "Starting Python Analysis Service on port 8000..."
cd /app
python -m uvicorn analysis_service.main:app --host 127.0.0.1 --port 8000 &
PYTHON_PID=$!

# 等待 Python 服务就绪
echo "Waiting for Analysis Service to be ready..."
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
        echo "✓ Analysis Service is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "⚠ Analysis Service not responding, continuing anyway..."
    fi
    sleep 1
done

# 启动 Bun Web 服务
echo ""
echo "Starting Bun Web Service on port ${PORT:-1788}..."
cd /app/web

# 设置环境变量让 Web 服务等待分析服务
export WAIT_FOR_ANALYSIS=false  # 已经在上面等待过了

exec bun run src/index.ts
