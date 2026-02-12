#!/bin/bash
#
# TradingCrew local development startup script
#
# Requirements:
#   - Python 3.11+
#   - Bun (https://bun.sh)
#
# Usage:
#   ./start-dev.sh          # Start all services
#   ./start-dev.sh python   # Start Python analysis service only
#   ./start-dev.sh web      # Start web service only
#

set -e

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# Load .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Set Python path
export PYTHONPATH="${PYTHONPATH}:${PROJECT_ROOT}"

start_python() {
    echo "Starting Python Analysis Service on port 8000..."
    cd "$PROJECT_ROOT"
    python -m uvicorn analysis_service.main:app --host 127.0.0.1 --port 8000 --reload
}

start_web() {
    echo "Starting Bun Web Service on port ${PORT:-1788}..."
    cd "$PROJECT_ROOT/web"

    # Ensure dependencies are installed
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

    # Start Python service (background)
    start_python &
    PYTHON_PID=$!
    echo "Python service PID: $PYTHON_PID"

    # Wait for Python service to be ready
    echo "Waiting for Analysis Service..."
    for i in $(seq 1 15); do
        if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
            echo "✓ Analysis Service is ready"
            break
        fi
        sleep 1
    done

    # Start web service (foreground)
    echo ""
    start_web

    # Cleanup
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
