"""
多市场交易日历工具

支持 A股、美股、港股的交易日历功能。
- A股: 使用 AKShare
- 美股/港股: 使用 exchange_calendars 或 pandas_market_calendars
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict
import pandas as pd

# A股数据源
try:
    import akshare as ak
except ImportError:
    ak = None

# 国际市场数据源
try:
    import exchange_calendars as xcals
    XCALS_AVAILABLE = True
except ImportError:
    try:
        import pandas_market_calendars as mcal
        XCALS_AVAILABLE = False
        MCAL_AVAILABLE = True
    except ImportError:
        XCALS_AVAILABLE = False
        MCAL_AVAILABLE = False


# 市场代码映射
MARKET_CALENDAR_CODES = {
    "A-share": "XSHG",  # 上海证券交易所 (exchange_calendars)
    "US": "XNYS",       # 纽约证券交易所
    "HK": "XHKG",       # 香港证券交易所
}

# pandas_market_calendars 使用的代码
MCAL_CODES = {
    "A-share": "SSE",   # Shanghai Stock Exchange
    "US": "NYSE",       # New York Stock Exchange
    "HK": "HKEX",       # Hong Kong Exchange
}


# 缓存
_calendar_cache: Dict[str, pd.DataFrame] = {}


def get_trading_calendar(market: str = "A-share") -> pd.DataFrame:
    """
    获取指定市场的交易日历

    Args:
        market: 市场类型 ("A-share", "US", "HK")

    Returns:
        包含交易日期的 DataFrame
    """
    global _calendar_cache

    cache_key = market
    if cache_key in _calendar_cache:
        return _calendar_cache[cache_key]

    if market == "A-share":
        # A股使用 akshare
        df = _get_ashare_calendar()
    else:
        # 美股/港股使用国际日历库
        df = _get_international_calendar(market)

    if not df.empty:
        _calendar_cache[cache_key] = df

    return df


def _get_ashare_calendar() -> pd.DataFrame:
    """获取 A 股交易日历"""
    if ak is None:
        print("Warning: akshare not installed, using fallback calendar for A-share")
        return pd.DataFrame()

    try:
        df = ak.tool_trade_date_hist_sina()
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        return df
    except Exception as e:
        print(f"获取 A 股交易日历失败: {e}")
        return pd.DataFrame()


def _get_international_calendar(market: str) -> pd.DataFrame:
    """获取国际市场交易日历"""
    # 获取 5 年范围的日历
    start_year = datetime.now().year - 3
    end_year = datetime.now().year + 2

    if XCALS_AVAILABLE:
        try:
            cal_code = MARKET_CALENDAR_CODES.get(market, "XNYS")
            cal = xcals.get_calendar(cal_code)
            sessions = cal.sessions_in_range(
                f"{start_year}-01-01",
                f"{end_year}-12-31"
            )
            df = pd.DataFrame({"trade_date": sessions})
            return df
        except Exception as e:
            print(f"exchange_calendars 获取 {market} 日历失败: {e}")

    if MCAL_AVAILABLE:
        try:
            cal_code = MCAL_CODES.get(market, "NYSE")
            cal = mcal.get_calendar(cal_code)
            schedule = cal.schedule(
                start_date=f"{start_year}-01-01",
                end_date=f"{end_year}-12-31"
            )
            df = pd.DataFrame({"trade_date": schedule.index})
            return df
        except Exception as e:
            print(f"pandas_market_calendars 获取 {market} 日历失败: {e}")

    print(f"Warning: 无法获取 {market} 交易日历，使用回退方案")
    return pd.DataFrame()


def is_trading_day(date: str, market: str = "A-share") -> bool:
    """
    判断指定日期是否为交易日

    Args:
        date: 日期字符串 yyyy-mm-dd
        market: 市场类型 ("A-share", "US", "HK")

    Returns:
        是否为交易日
    """
    calendar = get_trading_calendar(market)
    if calendar.empty:
        # 无法获取日历时，排除周末作为回退
        date_dt = datetime.strptime(date, "%Y-%m-%d")
        return date_dt.weekday() < 5

    date_dt = pd.to_datetime(date)
    return date_dt in calendar["trade_date"].values


def get_trading_days_in_range(
    start_date: str,
    end_date: str,
    market: str = "A-share"
) -> List[str]:
    """
    获取指定范围内的所有交易日

    Args:
        start_date: 开始日期 yyyy-mm-dd
        end_date: 结束日期 yyyy-mm-dd
        market: 市场类型 ("A-share", "US", "HK")

    Returns:
        交易日列表 (yyyy-mm-dd 格式)
    """
    calendar = get_trading_calendar(market)
    if calendar.empty:
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


def get_next_trading_day(date: str, market: str = "A-share") -> str:
    """
    获取下一个交易日

    Args:
        date: 当前日期 yyyy-mm-dd
        market: 市场类型 ("A-share", "US", "HK")

    Returns:
        下一个交易日 yyyy-mm-dd
    """
    calendar = get_trading_calendar(market)
    date_dt = pd.to_datetime(date)

    if calendar.empty:
        next_day = date_dt + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day.strftime("%Y-%m-%d")

    future_days = calendar[calendar["trade_date"] > date_dt]
    if future_days.empty:
        next_day = date_dt + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day.strftime("%Y-%m-%d")

    return future_days.iloc[0]["trade_date"].strftime("%Y-%m-%d")


def get_previous_trading_day(date: str, market: str = "A-share") -> str:
    """
    获取上一个交易日

    Args:
        date: 当前日期 yyyy-mm-dd
        market: 市场类型 ("A-share", "US", "HK")

    Returns:
        上一个交易日 yyyy-mm-dd
    """
    calendar = get_trading_calendar(market)
    date_dt = pd.to_datetime(date)

    if calendar.empty:
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


def get_trading_days_count(
    start_date: str,
    end_date: str,
    market: str = "A-share"
) -> int:
    """
    获取指定范围内的交易日数量

    Args:
        start_date: 开始日期 yyyy-mm-dd
        end_date: 结束日期 yyyy-mm-dd
        market: 市场类型 ("A-share", "US", "HK")

    Returns:
        交易日数量
    """
    return len(get_trading_days_in_range(start_date, end_date, market))


# ============================================================
# 指数成分股函数 (按市场)
# ============================================================

def get_index_constituents(market: str = "A-share", index_name: str = None) -> List[str]:
    """
    获取指数成分股列表

    Args:
        market: 市场类型 ("A-share", "US", "HK")
        index_name: 指数名称 (可选)
            - A-share: "hs300", "zz500"
            - US: "sp500", "nasdaq100", "djia"
            - HK: "hsi" (恒生指数)

    Returns:
        股票代码列表
    """
    if market == "A-share":
        if index_name == "zz500":
            return _get_zz500_constituents()
        return _get_hs300_constituents()  # 默认沪深300
    elif market == "US":
        if index_name == "nasdaq100":
            return _get_nasdaq100_constituents()
        if index_name == "djia":
            return _get_djia_constituents()
        return _get_sp500_constituents()  # 默认 S&P 500
    elif market == "HK":
        return _get_hsi_constituents()
    else:
        return []


def _get_hs300_constituents() -> List[str]:
    """获取沪深300成分股"""
    if ak is None:
        return [
            "600519", "000858", "600036", "601318", "000001",
            "600276", "000333", "002415", "600900", "601166",
        ]

    try:
        df = ak.index_stock_cons_csindex(symbol="000300")
        code_col = None
        for col in ["成分券代码", "证券代码", "代码", "code"]:
            if col in df.columns:
                code_col = col
                break
        if code_col:
            return df[code_col].tolist()
    except Exception as e:
        print(f"获取沪深300成分股失败: {e}")

    return ["600519", "000858", "600036", "601318", "000001"]


def _get_zz500_constituents() -> List[str]:
    """获取中证500成分股"""
    if ak is None:
        return []

    try:
        df = ak.index_stock_cons_csindex(symbol="000905")
        code_col = None
        for col in ["成分券代码", "证券代码", "代码", "code"]:
            if col in df.columns:
                code_col = col
                break
        if code_col:
            return df[code_col].tolist()
    except Exception as e:
        print(f"获取中证500成分股失败: {e}")

    return []


def _get_sp500_constituents() -> List[str]:
    """获取 S&P 500 成分股"""
    # 常见的 S&P 500 成分股
    return [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "BRK-B", "UNH", "JNJ",
        "JPM", "V", "XOM", "PG", "MA",
        "HD", "CVX", "MRK", "LLY", "ABBV",
    ]


def _get_nasdaq100_constituents() -> List[str]:
    """获取 NASDAQ 100 成分股"""
    return [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "AVGO", "COST", "ADBE",
        "PEP", "CSCO", "NFLX", "AMD", "INTC",
        "CMCSA", "TMUS", "TXN", "QCOM", "AMGN",
    ]


def _get_djia_constituents() -> List[str]:
    """获取道琼斯工业平均指数成分股"""
    return [
        "AAPL", "MSFT", "JPM", "V", "UNH",
        "HD", "JNJ", "WMT", "PG", "CVX",
        "MRK", "DIS", "KO", "CSCO", "VZ",
        "IBM", "AXP", "CAT", "GS", "MMM",
        "NKE", "MCD", "BA", "HON", "TRV",
        "DOW", "AMGN", "WBA", "CRM", "INTC",
    ]


def _get_hsi_constituents() -> List[str]:
    """获取恒生指数成分股"""
    return [
        "0700.HK",  # 腾讯控股
        "9988.HK",  # 阿里巴巴
        "0005.HK",  # 汇丰控股
        "0941.HK",  # 中国移动
        "1299.HK",  # 友邦保险
        "0388.HK",  # 香港交易所
        "0883.HK",  # 中国海洋石油
        "0939.HK",  # 建设银行
        "1398.HK",  # 工商银行
        "2318.HK",  # 中国平安
        "0027.HK",  # 银河娱乐
        "0011.HK",  # 恒生银行
        "0016.HK",  # 新鸿基地产
        "0001.HK",  # 长和
        "0002.HK",  # 中电控股
    ]
