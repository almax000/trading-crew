"""
TradingCrew 回测模块

提供 A 股回测功能，包括:
- 交易日历工具
- 评估指标计算
- 回测执行器
"""

from .trading_calendar import (
    get_trading_days_in_range,
    is_trading_day,
    get_next_trading_day,
    get_hs300_constituents,
)
from .metrics import BacktestMetrics, calculate_metrics
from .runner import BacktestRunner, BacktestResult, TradeRecord

__all__ = [
    # 交易日历
    "get_trading_days_in_range",
    "is_trading_day",
    "get_next_trading_day",
    "get_hs300_constituents",
    # 评估指标
    "BacktestMetrics",
    "calculate_metrics",
    # 回测执行器
    "BacktestRunner",
    "BacktestResult",
    "TradeRecord",
]
