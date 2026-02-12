"""
TradingCrew Backtest Module

Provides backtesting functionality including:
- Trading calendar utilities
- Evaluation metrics calculation
- Backtest runner
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
    # Trading calendar
    "get_trading_days_in_range",
    "is_trading_day",
    "get_next_trading_day",
    "get_hs300_constituents",
    # Evaluation metrics
    "BacktestMetrics",
    "calculate_metrics",
    # Backtest runner
    "BacktestRunner",
    "BacktestResult",
    "TradeRecord",
]
