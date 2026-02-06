#!/bin/bash
# 管理员工具：查看所有用户的会话
# 用法: ./scripts/admin-sessions.sh [命令]
#   list     - 列出所有会话（默认）
#   detail   - 查看会话详情（需要 session_id）
#   stats    - 只显示统计信息

set -e

# 配置
BASE_URL="${TRADING_CREW_URL:-https://trading-crew-production.up.railway.app}"
ADMIN_TOKEN="${ADMIN_TOKEN:?Error: ADMIN_TOKEN environment variable is required}"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取所有会话
fetch_sessions() {
    curl -s "${BASE_URL}/api/sessions/admin/all?token=${ADMIN_TOKEN}"
}

# 列出会话
cmd_list() {
    echo -e "${BLUE}=== TradingCrew 会话管理 ===${NC}"
    echo ""

    data=$(fetch_sessions)

    if echo "$data" | grep -q '"error"'; then
        echo -e "${RED}错误: $(echo "$data" | jq -r '.error')${NC}"
        exit 1
    fi

    total=$(echo "$data" | jq '.total')
    echo -e "${GREEN}总会话数: ${total}${NC}"
    echo ""

    echo -e "${YELLOW}按用户统计:${NC}"
    echo "$data" | jq -r '.byUser | to_entries[] | "  \(.key): \(.value) 个会话"'
    echo ""

    echo -e "${YELLOW}会话列表:${NC}"
    echo "$data" | jq -r '.sessions[] | "[\(.status | if . == "completed" then "✓" elif . == "running" then "▶" elif . == "error" then "✗" else "○" end)] \(.id) | \(.ticker) (\(.stockName // "")) | @\(.userId // "anonymous") | \(.createdAt)"'
}

# 显示统计
cmd_stats() {
    echo -e "${BLUE}=== 会话统计 ===${NC}"
    echo ""

    data=$(fetch_sessions)

    total=$(echo "$data" | jq '.total')
    completed=$(echo "$data" | jq '[.sessions[] | select(.status == "completed")] | length')
    running=$(echo "$data" | jq '[.sessions[] | select(.status == "running")] | length')
    error=$(echo "$data" | jq '[.sessions[] | select(.status == "error")] | length')
    pending=$(echo "$data" | jq '[.sessions[] | select(.status == "pending")] | length')

    echo -e "总数:     ${GREEN}${total}${NC}"
    echo -e "已完成:   ${GREEN}${completed}${NC}"
    echo -e "运行中:   ${YELLOW}${running}${NC}"
    echo -e "出错:     ${RED}${error}${NC}"
    echo -e "等待中:   ${pending}"
    echo ""

    echo -e "${YELLOW}按用户:${NC}"
    echo "$data" | jq -r '.byUser | to_entries | sort_by(-.value)[] | "  \(.key): \(.value)"'
}

# 查看详情
cmd_detail() {
    session_id=$1
    if [ -z "$session_id" ]; then
        echo -e "${RED}请提供 session_id${NC}"
        echo "用法: $0 detail <session_id>"
        exit 1
    fi

    data=$(fetch_sessions)
    session=$(echo "$data" | jq ".sessions[] | select(.id == \"$session_id\")")

    if [ -z "$session" ] || [ "$session" == "null" ]; then
        echo -e "${RED}找不到会话: $session_id${NC}"
        exit 1
    fi

    echo -e "${BLUE}=== 会话详情 ===${NC}"
    echo "$session" | jq '.'
}

# 主入口
case "${1:-list}" in
    list)
        cmd_list
        ;;
    stats)
        cmd_stats
        ;;
    detail)
        cmd_detail "$2"
        ;;
    *)
        echo "用法: $0 [list|stats|detail <session_id>]"
        exit 1
        ;;
esac
