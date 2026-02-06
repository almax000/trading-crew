"""
Web UI 配置
"""

import os
from typing import Set, Tuple, List
from datetime import datetime, timedelta


def get_invite_codes() -> Set[Tuple[str, str]]:
    """
    从环境变量读取邀请码

    支持两种格式:
    1. INVITE_CODES=user1:pass1,user2:pass2  (推荐，Railway 部署用)
    2. INVITE_CODE_1=user1:pass1, INVITE_CODE_2=user2:pass2  (兼容旧格式)

    Returns:
        Set of (username, password) tuples
    """
    codes: Set[Tuple[str, str]] = set()

    # 格式1: INVITE_CODES 环境变量 (逗号分隔)
    codes_str = os.environ.get("INVITE_CODES", "")
    if codes_str:
        for pair in codes_str.split(","):
            pair = pair.strip()
            if ":" in pair:
                user, pwd = pair.split(":", 1)
                user, pwd = user.strip(), pwd.strip()
                if user and pwd:
                    codes.add((user, pwd))

    # 格式2: INVITE_CODE_N 环境变量 (兼容旧格式)
    for key, value in os.environ.items():
        if key.startswith("INVITE_CODE_"):
            parts = value.split(":", 1)
            if len(parts) == 2:
                user, pwd = parts[0].strip(), parts[1].strip()
                if user and pwd:
                    codes.add((user, pwd))

    # 如果没有配置任何邀请码，添加默认的 demo 用户 (仅本地开发)
    if not codes and not os.environ.get("RAILWAY_ENVIRONMENT"):
        codes.add(("demo", "tradingcrew2024"))

    return codes


# 邀请码列表
INVITE_CODES: Set[Tuple[str, str]] = get_invite_codes()


def get_admin_users() -> Set[str]:
    """
    从环境变量读取管理员用户列表

    格式: ADMIN_USERS=user1,user2,user3

    Returns:
        Set of admin usernames
    """
    admins: Set[str] = set()

    admin_str = os.environ.get("ADMIN_USERS", "")
    if admin_str:
        for user in admin_str.split(","):
            user = user.strip()
            if user:
                admins.add(user)

    # 默认 demo 用户是管理员 (本地开发)
    if not admins and not os.environ.get("RAILWAY_ENVIRONMENT"):
        admins.add("demo")

    return admins


# 管理员用户列表
ADMIN_USERS: Set[str] = get_admin_users()


def is_admin(username: str) -> bool:
    """检查用户是否是管理员"""
    return username in ADMIN_USERS

# 服务端口 (支持 Railway 的 PORT 环境变量)
WEB_PORT = int(os.environ.get("PORT", os.environ.get("WEB_PORT", 1788)))

# 默认市场
DEFAULT_MARKET = "A-share"

# 市场选项
MARKET_OPTIONS = {
    "A股": "A-share",
    "美股": "US",
    "港股": "HK",
}

# 分析师选项
ANALYST_OPTIONS = {
    "市场分析师": "market",
    "舆情分析师": "social",
    "新闻分析师": "news",
    "基本面分析师": "fundamentals",
}

# Agent 显示名称映射
AGENT_DISPLAY_NAMES = {
    "Market Analyst": "市场分析师",
    "Social Analyst": "舆情分析师",
    "News Analyst": "新闻分析师",
    "Fundamentals Analyst": "基本面分析师",
    "Bull Researcher": "看多研究员",
    "Bear Researcher": "看空研究员",
    "Research Manager": "研究主管",
    "Trader": "交易员",
    "Risky Analyst": "激进风控",
    "Safe Analyst": "保守风控",
    "Neutral Analyst": "中性风控",
    "Risk Manager": "风控主管",
    "Portfolio Manager": "组合经理",
}

# Agent 执行顺序
AGENT_ORDER = [
    "Market Analyst",
    "Social Analyst",
    "News Analyst",
    "Fundamentals Analyst",
    "Bull Researcher",
    "Bear Researcher",
    "Research Manager",
    "Trader",
    "Risky Analyst",
    "Safe Analyst",
    "Neutral Analyst",
    "Risk Manager",
    "Portfolio Manager",
]


# ============ Session 相关配置 ============

# 最大并发 Session 数
MAX_CONCURRENT_SESSIONS = 3

# Session 状态显示
SESSION_STATUS_DISPLAY = {
    "pending": ("待运行", "#888"),
    "running": ("运行中", "#f0ad4e"),
    "completed": ("已完成", "#5cb85c"),
    "error": ("出错", "#d9534f"),
}

# 决策显示
DECISION_DISPLAY = {
    "BUY": ("买入", "#5cb85c", "buy"),
    "SELL": ("卖出", "#d9534f", "sell"),
    "HOLD": ("持有", "#5bc0de", "hold"),
}


def get_date_presets() -> List[dict]:
    """
    获取日期预设选项

    Returns:
        预设列表，每项包含 label, start, end
    """
    today = datetime.now()

    # 计算各个预设的日期
    presets = []

    # 最近一周
    week_ago = today - timedelta(days=7)
    presets.append({
        "label": "最近一周",
        "start": week_ago.strftime("%Y-%m-%d"),
        "end": today.strftime("%Y-%m-%d"),
    })

    # 最近一月
    month_ago = today - timedelta(days=30)
    presets.append({
        "label": "最近一月",
        "start": month_ago.strftime("%Y-%m-%d"),
        "end": today.strftime("%Y-%m-%d"),
    })

    # 最近三月
    three_months_ago = today - timedelta(days=90)
    presets.append({
        "label": "最近三月",
        "start": three_months_ago.strftime("%Y-%m-%d"),
        "end": today.strftime("%Y-%m-%d"),
    })

    # 今年以来
    year_start = datetime(today.year, 1, 1)
    presets.append({
        "label": "今年以来",
        "start": year_start.strftime("%Y-%m-%d"),
        "end": today.strftime("%Y-%m-%d"),
    })

    # 单日（今天）
    presets.append({
        "label": "单日分析",
        "start": today.strftime("%Y-%m-%d"),
        "end": today.strftime("%Y-%m-%d"),
    })

    return presets


def get_default_dates() -> Tuple[str, str]:
    """
    获取默认日期范围

    Returns:
        (start_date, end_date)
    """
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    return (
        week_ago.strftime("%Y-%m-%d"),
        today.strftime("%Y-%m-%d"),
    )
