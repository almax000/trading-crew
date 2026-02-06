"""
A股交易日历工具

提供交易日判断、日期范围生成、沪深300成分股获取等功能。
使用 AKShare 获取真实交易日历数据。
"""

from datetime import datetime, timedelta
from typing import List, Optional
import pandas as pd

try:
    import akshare as ak
except ImportError:
    ak = None


# 缓存交易日历
_trading_days_cache: Optional[pd.DataFrame] = None


def get_trading_calendar() -> pd.DataFrame:
    """
    获取A股交易日历

    Returns:
        包含交易日期的 DataFrame
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
            print(f"获取交易日历失败: {e}")
            return pd.DataFrame()

    return _trading_days_cache


def is_trading_day(date: str) -> bool:
    """
    判断指定日期是否为交易日

    Args:
        date: 日期字符串 yyyy-mm-dd

    Returns:
        是否为交易日
    """
    calendar = get_trading_calendar()
    if calendar.empty:
        # 无法获取日历时，排除周末作为回退
        date_dt = datetime.strptime(date, "%Y-%m-%d")
        return date_dt.weekday() < 5

    date_dt = pd.to_datetime(date)
    return date_dt in calendar["trade_date"].values


def get_trading_days_in_range(
    start_date: str,
    end_date: str
) -> List[str]:
    """
    获取指定范围内的所有交易日

    Args:
        start_date: 开始日期 yyyy-mm-dd
        end_date: 结束日期 yyyy-mm-dd

    Returns:
        交易日列表 (yyyy-mm-dd 格式)
    """
    calendar = get_trading_calendar()
    if calendar.empty:
        # 回退到简单的工作日逻辑
        return _fallback_trading_days(start_date, end_date)

    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    mask = (calendar["trade_date"] >= start_dt) & (calendar["trade_date"] <= end_dt)
    trading_days = calendar[mask]["trade_date"].tolist()

    return [d.strftime("%Y-%m-%d") for d in trading_days]


def _fallback_trading_days(start_date: str, end_date: str) -> List[str]:
    """回退方案: 排除周末"""
    result = []
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= end:
        if current.weekday() < 5:  # 周一到周五
            result.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    return result


def get_next_trading_day(date: str) -> str:
    """
    获取下一个交易日

    Args:
        date: 当前日期 yyyy-mm-dd

    Returns:
        下一个交易日 yyyy-mm-dd
    """
    calendar = get_trading_calendar()
    date_dt = pd.to_datetime(date)

    if calendar.empty:
        # 回退逻辑: 跳过周末
        next_day = date_dt + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day.strftime("%Y-%m-%d")

    future_days = calendar[calendar["trade_date"] > date_dt]
    if future_days.empty:
        # 超出日历范围，使用简单逻辑
        next_day = date_dt + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day.strftime("%Y-%m-%d")

    return future_days.iloc[0]["trade_date"].strftime("%Y-%m-%d")


def get_previous_trading_day(date: str) -> str:
    """
    获取上一个交易日

    Args:
        date: 当前日期 yyyy-mm-dd

    Returns:
        上一个交易日 yyyy-mm-dd
    """
    calendar = get_trading_calendar()
    date_dt = pd.to_datetime(date)

    if calendar.empty:
        # 回退逻辑
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
    获取沪深300成分股列表

    Returns:
        股票代码列表 (如 ["600519", "000858", ...])
    """
    if ak is None:
        print("Warning: akshare not installed, returning sample stocks")
        # 返回部分常见成分股作为回退
        return [
            "600519",  # 贵州茅台
            "000858",  # 五粮液
            "600036",  # 招商银行
            "601318",  # 中国平安
            "000001",  # 平安银行
            "600276",  # 恒瑞医药
            "000333",  # 美的集团
            "002415",  # 海康威视
            "600900",  # 长江电力
            "601166",  # 兴业银行
        ]

    try:
        df = ak.index_stock_cons_csindex(symbol="000300")
        # 列名可能是 "成分券代码" 或其他
        code_col = None
        for col in ["成分券代码", "证券代码", "代码", "code"]:
            if col in df.columns:
                code_col = col
                break

        if code_col is None:
            print(f"Warning: 无法识别成分股代码列，列名: {df.columns.tolist()}")
            return []

        return df[code_col].tolist()

    except Exception as e:
        print(f"获取沪深300成分股失败: {e}")
        # 返回部分常见成分股作为回退
        return [
            "600519", "000858", "600036", "601318", "000001",
            "600276", "000333", "002415", "600900", "601166",
        ]


def get_zz500_constituents() -> List[str]:
    """
    获取中证500成分股列表

    Returns:
        股票代码列表
    """
    if ak is None:
        return []

    try:
        df = ak.index_stock_cons_csindex(symbol="000905")
        code_col = None
        for col in ["成分券代码", "证券代码", "代码", "code"]:
            if col in df.columns:
                code_col = col
                break

        if code_col is None:
            return []

        return df[code_col].tolist()

    except Exception as e:
        print(f"获取中证500成分股失败: {e}")
        return []


def get_trading_days_count(start_date: str, end_date: str) -> int:
    """
    获取指定范围内的交易日数量

    Args:
        start_date: 开始日期 yyyy-mm-dd
        end_date: 结束日期 yyyy-mm-dd

    Returns:
        交易日数量
    """
    return len(get_trading_days_in_range(start_date, end_date))
