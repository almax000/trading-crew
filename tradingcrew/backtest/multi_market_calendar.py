"""
Multi-market Trading Calendar Utilities

Supports trading calendar functions for A-share, US, and HK markets.
- A-share: Uses AKShare
- US/HK: Uses exchange_calendars or pandas_market_calendars
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict
import pandas as pd

# A-share data source
try:
    import akshare as ak
except ImportError:
    ak = None

# International market data source
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


# Market code mapping
MARKET_CALENDAR_CODES = {
    "A-share": "XSHG",  # Shanghai Stock Exchange (exchange_calendars)
    "US": "XNYS",       # New York Stock Exchange
    "HK": "XHKG",       # Hong Kong Stock Exchange
}

# pandas_market_calendars codes
MCAL_CODES = {
    "A-share": "SSE",   # Shanghai Stock Exchange
    "US": "NYSE",       # New York Stock Exchange
    "HK": "HKEX",       # Hong Kong Exchange
}


# Cache
_calendar_cache: Dict[str, pd.DataFrame] = {}


def get_trading_calendar(market: str = "A-share") -> pd.DataFrame:
    """
    Get trading calendar for the specified market

    Args:
        market: Market type ("A-share", "US", "HK")

    Returns:
        DataFrame containing trading dates
    """
    global _calendar_cache

    cache_key = market
    if cache_key in _calendar_cache:
        return _calendar_cache[cache_key]

    if market == "A-share":
        # A-share uses akshare
        df = _get_ashare_calendar()
    else:
        # US/HK uses international calendar library
        df = _get_international_calendar(market)

    if not df.empty:
        _calendar_cache[cache_key] = df

    return df


def _get_ashare_calendar() -> pd.DataFrame:
    """Get A-share trading calendar"""
    if ak is None:
        print("Warning: akshare not installed, using fallback calendar for A-share")
        return pd.DataFrame()

    try:
        df = ak.tool_trade_date_hist_sina()
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        return df
    except Exception as e:
        print(f"Failed to fetch A-share trading calendar: {e}")
        return pd.DataFrame()


def _get_international_calendar(market: str) -> pd.DataFrame:
    """Get international market trading calendar"""
    # Get 5-year range calendar
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
            print(f"exchange_calendars failed to fetch {market} calendar: {e}")

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
            print(f"pandas_market_calendars failed to fetch {market} calendar: {e}")

    print(f"Warning: Unable to fetch {market} trading calendar, using fallback")
    return pd.DataFrame()


def is_trading_day(date: str, market: str = "A-share") -> bool:
    """
    Check if the given date is a trading day

    Args:
        date: Date string yyyy-mm-dd
        market: Market type ("A-share", "US", "HK")

    Returns:
        Whether it is a trading day
    """
    calendar = get_trading_calendar(market)
    if calendar.empty:
        # Fallback: exclude weekends when calendar is unavailable
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
    Get all trading days within the specified range

    Args:
        start_date: Start date yyyy-mm-dd
        end_date: End date yyyy-mm-dd
        market: Market type ("A-share", "US", "HK")

    Returns:
        List of trading days (yyyy-mm-dd format)
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
    """Fallback: exclude weekends"""
    result = []
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= end:
        if current.weekday() < 5:  # Monday to Friday
            result.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    return result


def get_next_trading_day(date: str, market: str = "A-share") -> str:
    """
    Get the next trading day

    Args:
        date: Current date yyyy-mm-dd
        market: Market type ("A-share", "US", "HK")

    Returns:
        Next trading day yyyy-mm-dd
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
    Get the previous trading day

    Args:
        date: Current date yyyy-mm-dd
        market: Market type ("A-share", "US", "HK")

    Returns:
        Previous trading day yyyy-mm-dd
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
    Get the number of trading days within the specified range

    Args:
        start_date: Start date yyyy-mm-dd
        end_date: End date yyyy-mm-dd
        market: Market type ("A-share", "US", "HK")

    Returns:
        Number of trading days
    """
    return len(get_trading_days_in_range(start_date, end_date, market))


# ============================================================
# Index constituent functions (by market)
# ============================================================

def get_index_constituents(market: str = "A-share", index_name: str = None) -> List[str]:
    """
    Get index constituent list

    Args:
        market: Market type ("A-share", "US", "HK")
        index_name: Index name (optional)
            - A-share: "hs300", "zz500"
            - US: "sp500", "nasdaq100", "djia"
            - HK: "hsi" (Hang Seng Index)

    Returns:
        List of stock codes
    """
    if market == "A-share":
        if index_name == "zz500":
            return _get_zz500_constituents()
        return _get_hs300_constituents()  # Default CSI 300
    elif market == "US":
        if index_name == "nasdaq100":
            return _get_nasdaq100_constituents()
        if index_name == "djia":
            return _get_djia_constituents()
        return _get_sp500_constituents()  # Default S&P 500
    elif market == "HK":
        return _get_hsi_constituents()
    else:
        return []


def _get_hs300_constituents() -> List[str]:
    """Get CSI 300 constituents"""
    if ak is None:
        return [
            "600519", "000858", "600036", "601318", "000001",
            "600276", "000333", "002415", "600900", "601166",
        ]

    try:
        df = ak.index_stock_cons_csindex(symbol="000300")
        code_col = None
        for col in ["\u6210\u5206\u5238\u4ee3\u7801", "\u8bc1\u5238\u4ee3\u7801", "\u4ee3\u7801", "code"]:
            if col in df.columns:
                code_col = col
                break
        if code_col:
            return df[code_col].tolist()
    except Exception as e:
        print(f"Failed to fetch CSI 300 constituents: {e}")

    return ["600519", "000858", "600036", "601318", "000001"]


def _get_zz500_constituents() -> List[str]:
    """Get CSI 500 constituents"""
    if ak is None:
        return []

    try:
        df = ak.index_stock_cons_csindex(symbol="000905")
        code_col = None
        for col in ["\u6210\u5206\u5238\u4ee3\u7801", "\u8bc1\u5238\u4ee3\u7801", "\u4ee3\u7801", "code"]:
            if col in df.columns:
                code_col = col
                break
        if code_col:
            return df[code_col].tolist()
    except Exception as e:
        print(f"Failed to fetch CSI 500 constituents: {e}")

    return []


def _get_sp500_constituents() -> List[str]:
    """Get S&P 500 constituents"""
    return [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "BRK-B", "UNH", "JNJ",
        "JPM", "V", "XOM", "PG", "MA",
        "HD", "CVX", "MRK", "LLY", "ABBV",
    ]


def _get_nasdaq100_constituents() -> List[str]:
    """Get NASDAQ 100 constituents"""
    return [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "AVGO", "COST", "ADBE",
        "PEP", "CSCO", "NFLX", "AMD", "INTC",
        "CMCSA", "TMUS", "TXN", "QCOM", "AMGN",
    ]


def _get_djia_constituents() -> List[str]:
    """Get Dow Jones Industrial Average constituents"""
    return [
        "AAPL", "MSFT", "JPM", "V", "UNH",
        "HD", "JNJ", "WMT", "PG", "CVX",
        "MRK", "DIS", "KO", "CSCO", "VZ",
        "IBM", "AXP", "CAT", "GS", "MMM",
        "NKE", "MCD", "BA", "HON", "TRV",
        "DOW", "AMGN", "WBA", "CRM", "INTC",
    ]


def _get_hsi_constituents() -> List[str]:
    """Get Hang Seng Index constituents"""
    return [
        "0700.HK",  # Tencent
        "9988.HK",  # Alibaba
        "0005.HK",  # HSBC
        "0941.HK",  # China Mobile
        "1299.HK",  # AIA Group
        "0388.HK",  # HKEX
        "0883.HK",  # CNOOC
        "0939.HK",  # CCB
        "1398.HK",  # ICBC
        "2318.HK",  # Ping An
        "0027.HK",  # Galaxy Entertainment
        "0011.HK",  # Hang Seng Bank
        "0016.HK",  # Sun Hung Kai Properties
        "0001.HK",  # CK Hutchison
        "0002.HK",  # CLP Holdings
    ]
