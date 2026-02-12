"""
A-share Trading Calendar Utilities

Provides trading day validation, date range generation, and CSI 300 constituent retrieval.
Uses AKShare for real trading calendar data.
"""

from datetime import datetime, timedelta
from typing import List, Optional
import pandas as pd

try:
    import akshare as ak
except ImportError:
    ak = None


# Cached trading calendar
_trading_days_cache: Optional[pd.DataFrame] = None


def get_trading_calendar() -> pd.DataFrame:
    """
    Get A-share trading calendar

    Returns:
        DataFrame containing trading dates
    """
    global _trading_days_cache

    if _trading_days_cache is None:
        if ak is None:
            print("Warning: akshare not installed, using fallback calendar")
            return pd.DataFrame()

        try:
            df = ak.tool_trade_date_hist_sina()
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            _trading_days_cache = df
        except Exception as e:
            print(f"Failed to fetch trading calendar: {e}")
            return pd.DataFrame()

    return _trading_days_cache


def is_trading_day(date: str) -> bool:
    """
    Check if the given date is a trading day

    Args:
        date: Date string yyyy-mm-dd

    Returns:
        Whether it is a trading day
    """
    calendar = get_trading_calendar()
    if calendar.empty:
        # Fallback: exclude weekends when calendar is unavailable
        date_dt = datetime.strptime(date, "%Y-%m-%d")
        return date_dt.weekday() < 5

    date_dt = pd.to_datetime(date)
    return date_dt in calendar["trade_date"].values


def get_trading_days_in_range(
    start_date: str,
    end_date: str
) -> List[str]:
    """
    Get all trading days within the specified range

    Args:
        start_date: Start date yyyy-mm-dd
        end_date: End date yyyy-mm-dd

    Returns:
        List of trading days (yyyy-mm-dd format)
    """
    calendar = get_trading_calendar()
    if calendar.empty:
        # Fallback to simple weekday logic
        return _fallback_trading_days(start_date, end_date)

    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    mask = (calendar["trade_date"] >= start_dt) & (calendar["trade_date"] <= end_dt)
    trading_days = calendar[mask]["trade_date"].tolist()

    return [d.strftime("%Y-%m-%d") for d in trading_days]


def _fallback_trading_days(start_date: str, end_date: str) -> List[str]:
    """Fallback: exclude weekends"""
    result = []
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= end:
        if current.weekday() < 5:  # Monday to Friday
            result.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    return result


def get_next_trading_day(date: str) -> str:
    """
    Get the next trading day

    Args:
        date: Current date yyyy-mm-dd

    Returns:
        Next trading day yyyy-mm-dd
    """
    calendar = get_trading_calendar()
    date_dt = pd.to_datetime(date)

    if calendar.empty:
        # Fallback: skip weekends
        next_day = date_dt + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day.strftime("%Y-%m-%d")

    future_days = calendar[calendar["trade_date"] > date_dt]
    if future_days.empty:
        # Beyond calendar range, use simple logic
        next_day = date_dt + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day.strftime("%Y-%m-%d")

    return future_days.iloc[0]["trade_date"].strftime("%Y-%m-%d")


def get_previous_trading_day(date: str) -> str:
    """
    Get the previous trading day

    Args:
        date: Current date yyyy-mm-dd

    Returns:
        Previous trading day yyyy-mm-dd
    """
    calendar = get_trading_calendar()
    date_dt = pd.to_datetime(date)

    if calendar.empty:
        # Fallback
        prev_day = date_dt - timedelta(days=1)
        while prev_day.weekday() >= 5:
            prev_day -= timedelta(days=1)
        return prev_day.strftime("%Y-%m-%d")

    past_days = calendar[calendar["trade_date"] < date_dt]
    if past_days.empty:
        prev_day = date_dt - timedelta(days=1)
        while prev_day.weekday() >= 5:
            prev_day -= timedelta(days=1)
        return prev_day.strftime("%Y-%m-%d")

    return past_days.iloc[-1]["trade_date"].strftime("%Y-%m-%d")


def get_hs300_constituents() -> List[str]:
    """
    Get CSI 300 index constituents

    Returns:
        List of stock codes (e.g. ["600519", "000858", ...])
    """
    if ak is None:
        print("Warning: akshare not installed, returning sample stocks")
        # Return common constituents as fallback
        return [
            "600519",  # Kweichow Moutai
            "000858",  # Wuliangye
            "600036",  # China Merchants Bank
            "601318",  # Ping An Insurance
            "000001",  # Ping An Bank
            "600276",  # Hengrui Medicine
            "000333",  # Midea Group
            "002415",  # Hikvision
            "600900",  # Yangtze Power
            "601166",  # Industrial Bank
        ]

    try:
        df = ak.index_stock_cons_csindex(symbol="000300")
        # Column name may vary
        code_col = None
        for col in ["\u6210\u5206\u5238\u4ee3\u7801", "\u8bc1\u5238\u4ee3\u7801", "\u4ee3\u7801", "code"]:
            if col in df.columns:
                code_col = col
                break

        if code_col is None:
            print(f"Warning: Cannot identify constituent code column, columns: {df.columns.tolist()}")
            return []

        return df[code_col].tolist()

    except Exception as e:
        print(f"Failed to fetch CSI 300 constituents: {e}")
        # Return common constituents as fallback
        return [
            "600519", "000858", "600036", "601318", "000001",
            "600276", "000333", "002415", "600900", "601166",
        ]


def get_zz500_constituents() -> List[str]:
    """
    Get CSI 500 index constituents

    Returns:
        List of stock codes
    """
    if ak is None:
        return []

    try:
        df = ak.index_stock_cons_csindex(symbol="000905")
        code_col = None
        for col in ["\u6210\u5206\u5238\u4ee3\u7801", "\u8bc1\u5238\u4ee3\u7801", "\u4ee3\u7801", "code"]:
            if col in df.columns:
                code_col = col
                break

        if code_col is None:
            return []

        return df[code_col].tolist()

    except Exception as e:
        print(f"Failed to fetch CSI 500 constituents: {e}")
        return []


def get_trading_days_count(start_date: str, end_date: str) -> int:
    """
    Get the number of trading days within the specified range

    Args:
        start_date: Start date yyyy-mm-dd
        end_date: End date yyyy-mm-dd

    Returns:
        Number of trading days
    """
    return len(get_trading_days_in_range(start_date, end_date))
