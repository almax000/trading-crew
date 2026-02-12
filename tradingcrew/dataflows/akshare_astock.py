"""
AKShare A-share data adapter

Provides A-share data retrieval functions compatible with existing yfinance/alpha_vantage interfaces.
Uses AKShare as data source, supporting:
- Daily OHLCV data (stock_zh_a_hist)
- Technical indicators (via stockstats)
- A-share news (stock_news_em)
- Company fundamentals (stock_individual_info_em)
"""

from typing import Annotated
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import os

try:
    import akshare as ak
except ImportError:
    ak = None
    print("Warning: akshare not installed. Run: pip install akshare")

try:
    from stockstats import wrap
except ImportError:
    wrap = None
    print("Warning: stockstats not installed. Run: pip install stockstats")

from .config import get_config


# === Technical indicator descriptions (consistent with y_finance.py) ===
INDICATOR_DESCRIPTIONS = {
    "close_50_sma": "50 SMA: Medium-term trend indicator. Used to identify trend direction and dynamic support/resistance levels. Lags price; combine with faster indicators to confirm signals.",
    "close_200_sma": "200 SMA: Long-term trend benchmark. Used to confirm overall market trend and identify golden/death cross patterns. Reacts slowly; best for strategic trend confirmation.",
    "close_10_ema": "10 EMA: Short-term responsive moving average. Captures quick momentum shifts and potential entry points. Prone to noise in choppy markets; filter with longer-period averages.",
    "macd": "MACD: Calculates momentum via EMA differences. Watch for crossovers and divergence as trend change signals. Confirm with other indicators in low-volatility or sideways markets.",
    "macds": "MACD Signal: EMA smoothing of the MACD line. Crossovers with the MACD line can trigger trade signals. Should be part of a broader strategy to avoid false positives.",
    "macdh": "MACD Histogram: Difference between MACD line and signal line. Visualizes momentum strength and detects divergence early. Can be volatile; complement with additional filters.",
    "rsi": "RSI: Momentum indicator measuring overbought/oversold conditions. Use 70/30 thresholds and watch for divergence signals. In strong trends, RSI may remain extreme; cross-check with trend analysis.",
    "boll": "Bollinger Middle: 20-day SMA serving as Bollinger Band baseline. Acts as a dynamic benchmark for price movement. Combine with upper/lower bands to identify breakouts or reversals.",
    "boll_ub": "Bollinger Upper Band: Middle band + 2 standard deviations. Signals potential overbought conditions and breakout zones. In strong trends, price may ride the band; confirm with other tools.",
    "boll_lb": "Bollinger Lower Band: Middle band - 2 standard deviations. Indicates potential oversold conditions. Combine with other analysis to avoid false reversal signals.",
    "atr": "ATR: Average True Range measuring volatility. Used for setting stop-loss levels and adjusting position sizes based on market volatility. A reactive measure; use as part of broader risk management.",
    "vwma": "VWMA: Volume-Weighted Moving Average. Confirms trends by integrating price and volume data. Watch for volume anomalies that may skew results; combine with other volume analysis.",
    "mfi": "MFI: Money Flow Index. Similar to RSI but incorporates volume, measuring buying/selling pressure. Overbought/oversold thresholds at 80/20."
}


# === Core stock data ===
def get_stock_data(
    symbol: Annotated[str, "A-share stock code, e.g. '600519' or '000001'"],
    start_date: Annotated[str, "Start date yyyy-mm-dd"],
    end_date: Annotated[str, "End date yyyy-mm-dd"],
) -> str:
    """
    Get A-share daily OHLCV data

    Args:
        symbol: Stock code, e.g. "600519" or "000001"
        start_date: Start date yyyy-mm-dd
        end_date: End date yyyy-mm-dd

    Returns:
        CSV-formatted stock data string
    """
    if ak is None:
        return "Error: akshare not installed. Run: pip install akshare"

    # Convert date format yyyy-mm-dd -> yyyymmdd
    start_fmt = start_date.replace("-", "")
    end_fmt = end_date.replace("-", "")

    try:
        # Call AKShare API
        # adjust="qfq" forward-adjusted, "hfq" backward-adjusted, "" unadjusted
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_fmt,
            end_date=end_fmt,
            adjust="qfq"  # Forward-adjusted
        )

        if df.empty:
            return f"No data found for stock {symbol} from {start_date} to {end_date}"

        # Rename columns to match existing format
        column_mapping = {
            "\u65e5\u671f": "Date",
            "\u5f00\u76d8": "Open",
            "\u6536\u76d8": "Close",
            "\u6700\u9ad8": "High",
            "\u6700\u4f4e": "Low",
            "\u6210\u4ea4\u91cf": "Volume",
            "\u6210\u4ea4\u989d": "Amount",
            "\u6da8\u8dcc\u5e45": "Change_Pct",
            "\u6362\u624b\u7387": "Turnover"
        }
        df = df.rename(columns=column_mapping)

        # Select key columns
        cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        available_cols = [c for c in cols if c in df.columns]
        df = df[available_cols]

        # Convert to CSV
        csv_string = df.to_csv(index=False)

        header = f"# A-share data {symbol} from {start_date} to {end_date}\n"
        header += f"# Total records: {len(df)}\n"
        header += f"# Retrieved at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        return f"Error fetching data for stock {symbol}: {str(e)}"


# === Technical indicators ===
def get_indicators(
    symbol: Annotated[str, "A-share stock code"],
    indicator: Annotated[str, "Technical indicator name, e.g. macd, rsi, boll"],
    curr_date: Annotated[str, "Current date yyyy-mm-dd"],
    look_back_days: Annotated[int, "Lookback days"] = 30,
) -> str:
    """
    Get A-share technical indicators

    Uses stockstats library for calculation, consistent with existing yfinance implementation.
    Supported indicators: close_50_sma, close_200_sma, close_10_ema, macd, macds,
                macdh, rsi, boll, boll_ub, boll_lb, atr, vwma, mfi
    """
    if ak is None:
        return "Error: akshare not installed"
    if wrap is None:
        return "Error: stockstats not installed"

    if indicator not in INDICATOR_DESCRIPTIONS:
        return f"Unsupported indicator {indicator}, available: {list(INDICATOR_DESCRIPTIONS.keys())}"

    try:
        # Fetch enough historical data for indicator calculation
        curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        # Need extra data for long-period indicators like 200SMA
        data_start = curr_date_dt - relativedelta(days=look_back_days + 300)

        start_fmt = data_start.strftime("%Y%m%d")
        end_fmt = curr_date_dt.strftime("%Y%m%d")

        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_fmt,
            end_date=end_fmt,
            adjust="qfq"
        )

        if df.empty:
            return f"No data found for stock {symbol}"

        # Rename columns for stockstats compatibility
        df = df.rename(columns={
            "\u65e5\u671f": "date",
            "\u5f00\u76d8": "open",
            "\u6536\u76d8": "close",
            "\u6700\u9ad8": "high",
            "\u6700\u4f4e": "low",
            "\u6210\u4ea4\u91cf": "volume"
        })

        # Ensure date column exists and is properly formatted
        if "date" not in df.columns:
            return f"Data format error: missing date column"

        df["date"] = pd.to_datetime(df["date"])

        # Save date column for later filtering
        dates = df["date"].copy()

        # Set date as index to prevent stockstats from parsing 'date' column name
        df = df.set_index("date")

        # Calculate indicator using stockstats
        stock_df = wrap(df)

        # Trigger indicator calculation
        try:
            _ = stock_df[indicator]
        except Exception as e:
            return f"Error calculating indicator {indicator}: {str(e)}"

        # Reset index and convert to regular DataFrame to avoid stockstats intercepting column access
        result_df = pd.DataFrame(stock_df.reset_index())

        # Filter to specified date range
        before = curr_date_dt - relativedelta(days=look_back_days)
        mask = (result_df["date"] >= before) & (result_df["date"] <= curr_date_dt)
        result_df = result_df[mask].copy()

        if result_df.empty:
            return f"No data found within the specified date range"

        # Build output string
        ind_string = ""
        for _, row in result_df.iterrows():
            date_str = row["date"].strftime("%Y-%m-%d")
            value = row[indicator] if indicator in row else None
            if pd.isna(value) or value is None:
                ind_string += f"{date_str}: N/A\n"
            else:
                ind_string += f"{date_str}: {value:.4f}\n"

        result = f"## {indicator} from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
        result += ind_string + "\n\n"
        result += INDICATOR_DESCRIPTIONS.get(indicator, "")

        return result

    except Exception as e:
        return f"Error fetching indicator {indicator}: {str(e)}"


# === News data ===
def get_news(
    ticker: Annotated[str, "A-share stock code"],
    start_date: Annotated[str, "Start date yyyy-mm-dd"],
    end_date: Annotated[str, "End date yyyy-mm-dd"],
) -> str:
    """
    Get A-share stock news

    Uses East Money stock news API
    """
    if ak is None:
        return "Error: akshare not installed"

    try:
        # Use East Money stock news API
        news_df = ak.stock_news_em(symbol=ticker)

        if news_df.empty:
            return f"No news found for stock {ticker}"

        news_str = f"## {ticker} related news ({start_date} to {end_date}):\n\n"

        # Limit number of news items
        for idx, row in news_df.head(10).iterrows():
            title = row.get("\u65b0\u95fb\u6807\u9898", row.get("title", "Untitled"))
            content = str(row.get("\u65b0\u95fb\u5185\u5bb9", row.get("content", "")))[:300]
            source = row.get("\u6587\u7ae0\u6765\u6e90", row.get("source", "Unknown"))
            pub_time = row.get("\u53d1\u5e03\u65f6\u95f4", row.get("publish_time", ""))

            news_str += f"### {title}\n"
            news_str += f"Source: {source} | Time: {pub_time}\n"
            news_str += f"{content}...\n\n"

        return news_str

    except Exception as e:
        return f"Error fetching news: {str(e)}"


# === Global news ===
def get_global_news(
    curr_date: Annotated[str, "Current date yyyy-mm-dd"],
    look_back_days: Annotated[int, "Lookback days"] = 7,
    limit: Annotated[int, "News count limit"] = 5,
) -> str:
    """Get global/macro financial news"""
    if ak is None:
        return "Error: akshare not installed"

    try:
        # Use East Money global financial news
        news_df = ak.stock_info_global_em()

        if news_df.empty:
            return "No global news found"

        news_str = f"## Global financial headlines (as of {curr_date}):\n\n"

        for idx, row in news_df.head(limit).iterrows():
            title = row.get("\u6807\u9898", row.get("title", ""))
            content = str(row.get("\u5185\u5bb9", row.get("content", "")))[:400]

            news_str += f"### {title}\n{content}...\n\n"

        return news_str

    except Exception as e:
        return f"Error fetching global news: {str(e)}"


# === Company fundamentals ===
def get_fundamentals(
    ticker: Annotated[str, "A-share stock code"],
    curr_date: Annotated[str, "Current date yyyy-mm-dd"] = None,
) -> str:
    """Get company fundamentals data"""
    if ak is None:
        return "Error: akshare not installed"

    try:
        # Use AKShare to get company overview
        info_df = ak.stock_individual_info_em(symbol=ticker)

        if info_df.empty:
            return f"No fundamentals data found for stock {ticker}"

        result = f"## {ticker} company overview:\n\n"
        for _, row in info_df.iterrows():
            item = row.get("item", row.get("\u9879\u76ee", ""))
            value = row.get("value", row.get("\u503c", ""))
            result += f"- {item}: {value}\n"

        return result

    except Exception as e:
        return f"Error fetching fundamentals data: {str(e)}"


# === Financial statements (simplified implementation) ===
def get_balance_sheet(
    ticker: Annotated[str, "A-share stock code"],
    freq: Annotated[str, "Frequency: quarterly or annual"] = "quarterly",
    curr_date: Annotated[str, "Current date"] = None,
) -> str:
    """Get balance sheet"""
    if ak is None:
        return "Error: akshare not installed"

    try:
        df = ak.stock_balance_sheet_by_report_em(symbol=ticker)
        if df.empty:
            return f"No balance sheet found for stock {ticker}"

        # Get most recent periods
        result = f"## {ticker} balance sheet (recent data):\n\n"
        result += df.head(5).to_string()
        return result
    except Exception as e:
        return f"Error fetching balance sheet: {str(e)}"


def get_cashflow(
    ticker: Annotated[str, "A-share stock code"],
    freq: Annotated[str, "Frequency: quarterly or annual"] = "quarterly",
    curr_date: Annotated[str, "Current date"] = None,
) -> str:
    """Get cash flow statement"""
    if ak is None:
        return "Error: akshare not installed"

    try:
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=ticker)
        if df.empty:
            return f"No cash flow statement found for stock {ticker}"

        result = f"## {ticker} cash flow statement (recent data):\n\n"
        result += df.head(5).to_string()
        return result
    except Exception as e:
        return f"Error fetching cash flow statement: {str(e)}"


def get_income_statement(
    ticker: Annotated[str, "A-share stock code"],
    freq: Annotated[str, "Frequency: quarterly or annual"] = "quarterly",
    curr_date: Annotated[str, "Current date"] = None,
) -> str:
    """Get income statement"""
    if ak is None:
        return "Error: akshare not installed"

    try:
        df = ak.stock_profit_sheet_by_report_em(symbol=ticker)
        if df.empty:
            return f"No income statement found for stock {ticker}"

        result = f"## {ticker} income statement (recent data):\n\n"
        result += df.head(5).to_string()
        return result
    except Exception as e:
        return f"Error fetching income statement: {str(e)}"


# === Insider transactions (A-share: major shareholder changes) ===
def get_insider_transactions(
    ticker: Annotated[str, "A-share stock code"],
    curr_date: Annotated[str, "Current date"] = None,
) -> str:
    """Get major shareholder transaction data"""
    if ak is None:
        return "Error: akshare not installed"

    try:
        # Stock pledge data as a proxy for insider transactions
        df = ak.stock_gpzy_pledge_ratio_em()
        # Filter for specific stock
        if "\u80a1\u7968\u4ee3\u7801" in df.columns:
            df = df[df["\u80a1\u7968\u4ee3\u7801"] == ticker]
        elif "\u4ee3\u7801" in df.columns:
            df = df[df["\u4ee3\u7801"] == ticker]

        if df.empty:
            return f"No shareholder transaction data found for stock {ticker}"

        result = f"## {ticker} shareholder pledge status:\n\n"
        result += df.head(10).to_string()
        return result

    except Exception as e:
        return f"Error fetching shareholder transaction data: {str(e)}"


def get_insider_sentiment(
    ticker: Annotated[str, "A-share stock code"],
    curr_date: Annotated[str, "Current date"] = None,
) -> str:
    """Get insider sentiment (not directly supported for A-shares)"""
    return f"Insider sentiment indicators are not directly available for A-shares. Use major shareholder changes and stock pledge ratios as indirect measures (stock: {ticker})"
