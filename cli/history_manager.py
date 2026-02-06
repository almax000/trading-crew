"""
历史记录管理器

保存用户输入历史，提供智能建议功能：
- 股票代码历史
- 回测日期历史
- 常用配置
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import OrderedDict


# 历史记录文件路径
HISTORY_FILE = Path.home() / ".tradingcrew" / "history.json"


def _ensure_dir():
    """确保目录存在"""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_history() -> dict:
    """加载历史记录"""
    _ensure_dir()
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "stocks": {},      # market -> [codes]
        "dates": [],       # [{start, end, label}]
        "last_market": "A-share",
        "last_config": {},
    }


def _save_history(data: dict):
    """保存历史记录"""
    _ensure_dir()
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# 股票代码历史
# ============================================================

def get_stock_history(market: str, limit: int = 20) -> List[str]:
    """
    获取指定市场的股票代码历史

    Args:
        market: 市场类型
        limit: 最大返回数量

    Returns:
        股票代码列表 (最近使用的排前面)
    """
    history = _load_history()
    stocks = history.get("stocks", {}).get(market, [])
    return stocks[:limit]


def add_stock_to_history(market: str, codes: List[str]):
    """
    添加股票代码到历史记录

    Args:
        market: 市场类型
        codes: 股票代码列表
    """
    history = _load_history()

    if "stocks" not in history:
        history["stocks"] = {}

    if market not in history["stocks"]:
        history["stocks"][market] = []

    # 去重并保持顺序 (新的在前)
    existing = history["stocks"][market]
    for code in codes:
        if code in existing:
            existing.remove(code)
        existing.insert(0, code)

    # 限制数量
    history["stocks"][market] = existing[:50]
    history["last_market"] = market

    _save_history(history)


def get_favorite_stocks(market: str) -> List[Dict]:
    """
    获取收藏的股票 (使用频率高的)

    Returns:
        [{"code": "600519", "name": "贵州茅台", "count": 10}, ...]
    """
    # 常用股票名称映射
    STOCK_NAMES = {
        "A-share": {
            "600519": "贵州茅台",
            "000858": "五粮液",
            "601318": "中国平安",
            "600036": "招商银行",
            "000001": "平安银行",
            "300750": "宁德时代",
            "002415": "海康威视",
            "000333": "美的集团",
        },
        "US": {
            "AAPL": "Apple",
            "MSFT": "Microsoft",
            "GOOGL": "Google",
            "AMZN": "Amazon",
            "NVDA": "NVIDIA",
            "TSLA": "Tesla",
            "META": "Meta",
            "JPM": "JPMorgan",
        },
        "HK": {
            "0700.HK": "腾讯控股",
            "9988.HK": "阿里巴巴",
            "0005.HK": "汇丰控股",
            "0941.HK": "中国移动",
            "1299.HK": "友邦保险",
            "0388.HK": "香港交易所",
        },
    }

    history = get_stock_history(market)
    names = STOCK_NAMES.get(market, {})

    result = []
    for code in history[:10]:
        result.append({
            "code": code,
            "name": names.get(code, ""),
        })
    return result


# ============================================================
# 日期历史和预设
# ============================================================

def get_date_presets() -> List[Dict]:
    """
    获取日期预设选项

    Returns:
        [{"label": "最近30天", "start": "2024-01-01", "end": "2024-01-31"}, ...]
    """
    today = datetime.now()

    presets = [
        {
            "label": "最近 7 天",
            "start": (today - timedelta(days=7)).strftime("%Y-%m-%d"),
            "end": today.strftime("%Y-%m-%d"),
        },
        {
            "label": "最近 30 天",
            "start": (today - timedelta(days=30)).strftime("%Y-%m-%d"),
            "end": today.strftime("%Y-%m-%d"),
        },
        {
            "label": "最近 3 个月",
            "start": (today - timedelta(days=90)).strftime("%Y-%m-%d"),
            "end": today.strftime("%Y-%m-%d"),
        },
        {
            "label": "最近 6 个月",
            "start": (today - timedelta(days=180)).strftime("%Y-%m-%d"),
            "end": today.strftime("%Y-%m-%d"),
        },
        {
            "label": "今年至今",
            "start": f"{today.year}-01-01",
            "end": today.strftime("%Y-%m-%d"),
        },
        {
            "label": f"{today.year - 1} 年全年",
            "start": f"{today.year - 1}-01-01",
            "end": f"{today.year - 1}-12-31",
        },
    ]

    return presets


def get_date_history(limit: int = 5) -> List[Dict]:
    """
    获取日期历史记录

    Returns:
        [{"start": "2024-01-01", "end": "2024-01-31", "label": "自定义"}, ...]
    """
    history = _load_history()
    dates = history.get("dates", [])
    return dates[:limit]


def add_date_to_history(start_date: str, end_date: str, label: str = "自定义"):
    """添加日期范围到历史"""
    history = _load_history()

    if "dates" not in history:
        history["dates"] = []

    # 检查是否已存在
    new_entry = {"start": start_date, "end": end_date, "label": label}
    history["dates"] = [d for d in history["dates"]
                        if not (d["start"] == start_date and d["end"] == end_date)]
    history["dates"].insert(0, new_entry)

    # 限制数量
    history["dates"] = history["dates"][:20]

    _save_history(history)


# ============================================================
# 配置历史
# ============================================================

def get_last_market() -> str:
    """获取上次使用的市场"""
    history = _load_history()
    return history.get("last_market", "A-share")


def get_last_config() -> dict:
    """获取上次的配置"""
    history = _load_history()
    return history.get("last_config", {})


def save_last_config(config: dict):
    """保存配置"""
    history = _load_history()
    history["last_config"] = config
    _save_history(history)
