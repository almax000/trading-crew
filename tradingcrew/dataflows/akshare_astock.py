"""
AKShare A股数据适配器

提供与现有 yfinance/alpha_vantage 接口兼容的 A股数据获取函数。
使用 AKShare 作为数据源，支持:
- 日线 OHLCV 数据 (stock_zh_a_hist)
- 技术指标 (基于 stockstats)
- A股新闻 (stock_news_em)
- 公司基本面 (stock_individual_info_em)
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


# === 技术指标描述 (与 y_finance.py 保持一致) ===
INDICATOR_DESCRIPTIONS = {
    "close_50_sma": "50 SMA: 中期趋势指标。用于识别趋势方向和动态支撑/阻力位。滞后于价格，需结合快速指标确认信号。",
    "close_200_sma": "200 SMA: 长期趋势基准。用于确认整体市场趋势和识别金叉/死叉形态。反应较慢，适合战略性趋势确认。",
    "close_10_ema": "10 EMA: 短期响应均线。捕捉快速动量变化和潜在入场点。在震荡市场中容易产生噪音，需配合长周期均线过滤。",
    "macd": "MACD: 通过EMA差异计算动量。观察交叉和背离作为趋势变化信号。在低波动或横盘市场中需其他指标确认。",
    "macds": "MACD Signal: MACD线的EMA平滑。与MACD线的交叉可触发交易信号。应作为更广泛策略的一部分，避免假阳性。",
    "macdh": "MACD Histogram: MACD线与信号线的差值。可视化动量强度并提前发现背离。波动较大，需配合其他过滤器。",
    "rsi": "RSI: 衡量超买/超卖状态的动量指标。使用70/30阈值并观察背离信号。强趋势中RSI可能持续极端，需配合趋势分析。",
    "boll": "布林带中轨: 20日SMA作为布林带基准。作为价格运动的动态基准。需结合上下轨有效识别突破或反转。",
    "boll_ub": "布林带上轨: 中轨+2标准差。信号潜在超买条件和突破区域。强趋势中价格可能沿轨道运行，需其他工具确认。",
    "boll_lb": "布林带下轨: 中轨-2标准差。指示潜在超卖条件。需配合其他分析避免假反转信号。",
    "atr": "ATR: 平均真实波幅，衡量波动性。用于设置止损位和根据市场波动调整仓位。反应性指标，应作为更广泛风险管理策略的一部分。",
    "vwma": "VWMA: 成交量加权移动平均。通过整合价格与成交量数据确认趋势。注意成交量异常可能扭曲结果，需结合其他成交量分析。",
    "mfi": "MFI: 资金流量指标。类似RSI但考虑成交量，衡量买卖压力。超买/超卖阈值为80/20。"
}


# === 核心股票数据 ===
def get_stock_data(
    symbol: Annotated[str, "A股代码，如 '600519' 或 '000001'"],
    start_date: Annotated[str, "开始日期 yyyy-mm-dd"],
    end_date: Annotated[str, "结束日期 yyyy-mm-dd"],
) -> str:
    """
    获取A股日线OHLCV数据

    Args:
        symbol: 股票代码，如 "600519" 或 "000001"
        start_date: 开始日期 yyyy-mm-dd
        end_date: 结束日期 yyyy-mm-dd

    Returns:
        CSV格式的股票数据字符串
    """
    if ak is None:
        return "Error: akshare not installed. Run: pip install akshare"

    # 转换日期格式 yyyy-mm-dd -> yyyymmdd
    start_fmt = start_date.replace("-", "")
    end_fmt = end_date.replace("-", "")

    try:
        # 调用 AKShare API
        # adjust="qfq" 前复权, "hfq" 后复权, "" 不复权
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_fmt,
            end_date=end_fmt,
            adjust="qfq"  # 前复权
        )

        if df.empty:
            return f"未找到股票 {symbol} 在 {start_date} 到 {end_date} 期间的数据"

        # 重命名列以匹配现有格式
        column_mapping = {
            "日期": "Date",
            "开盘": "Open",
            "收盘": "Close",
            "最高": "High",
            "最低": "Low",
            "成交量": "Volume",
            "成交额": "Amount",
            "涨跌幅": "Change_Pct",
            "换手率": "Turnover"
        }
        df = df.rename(columns=column_mapping)

        # 选择关键列
        cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        available_cols = [c for c in cols if c in df.columns]
        df = df[available_cols]

        # 转换为CSV
        csv_string = df.to_csv(index=False)

        header = f"# A股数据 {symbol} 从 {start_date} 到 {end_date}\n"
        header += f"# 总记录数: {len(df)}\n"
        header += f"# 获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        return f"获取股票 {symbol} 数据时出错: {str(e)}"


# === 技术指标 ===
def get_indicators(
    symbol: Annotated[str, "A股代码"],
    indicator: Annotated[str, "技术指标名称，如 macd, rsi, boll 等"],
    curr_date: Annotated[str, "当前日期 yyyy-mm-dd"],
    look_back_days: Annotated[int, "回溯天数"] = 30,
) -> str:
    """
    获取A股技术指标

    使用 stockstats 库计算技术指标，与现有 yfinance 实现保持一致。
    支持的指标: close_50_sma, close_200_sma, close_10_ema, macd, macds,
                macdh, rsi, boll, boll_ub, boll_lb, atr, vwma, mfi
    """
    if ak is None:
        return "Error: akshare not installed"
    if wrap is None:
        return "Error: stockstats not installed"

    if indicator not in INDICATOR_DESCRIPTIONS:
        return f"不支持的指标 {indicator}，可选: {list(INDICATOR_DESCRIPTIONS.keys())}"

    try:
        # 获取足够长的历史数据用于计算指标
        curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        # 需要额外数据来计算长周期指标如200SMA
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
            return f"未找到股票 {symbol} 的数据"

        # 重命名列以兼容 stockstats
        df = df.rename(columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume"
        })

        # 确保日期列存在且格式正确
        if "date" not in df.columns:
            return f"数据格式错误: 缺少日期列"

        df["date"] = pd.to_datetime(df["date"])

        # 保存日期列用于后续过滤
        dates = df["date"].copy()

        # 将日期设为索引，避免 stockstats 尝试解析 'date' 列名
        df = df.set_index("date")

        # 使用 stockstats 计算指标
        stock_df = wrap(df)

        # 触发指标计算
        try:
            _ = stock_df[indicator]
        except Exception as e:
            return f"计算指标 {indicator} 时出错: {str(e)}"

        # 重置索引并转换为普通 DataFrame，避免 stockstats 拦截列访问
        result_df = pd.DataFrame(stock_df.reset_index())

        # 过滤到指定日期范围
        before = curr_date_dt - relativedelta(days=look_back_days)
        mask = (result_df["date"] >= before) & (result_df["date"] <= curr_date_dt)
        result_df = result_df[mask].copy()

        if result_df.empty:
            return f"在指定日期范围内未找到数据"

        # 构建输出字符串
        ind_string = ""
        for _, row in result_df.iterrows():
            date_str = row["date"].strftime("%Y-%m-%d")
            value = row[indicator] if indicator in row else None
            if pd.isna(value) or value is None:
                ind_string += f"{date_str}: N/A\n"
            else:
                ind_string += f"{date_str}: {value:.4f}\n"

        result = f"## {indicator} 从 {before.strftime('%Y-%m-%d')} 到 {curr_date}:\n\n"
        result += ind_string + "\n\n"
        result += INDICATOR_DESCRIPTIONS.get(indicator, "")

        return result

    except Exception as e:
        return f"获取指标 {indicator} 时出错: {str(e)}"


# === 新闻数据 ===
def get_news(
    ticker: Annotated[str, "A股代码"],
    start_date: Annotated[str, "开始日期 yyyy-mm-dd"],
    end_date: Annotated[str, "结束日期 yyyy-mm-dd"],
) -> str:
    """
    获取A股个股新闻

    使用东方财富个股新闻接口
    """
    if ak is None:
        return "Error: akshare not installed"

    try:
        # 使用东方财富个股新闻接口
        news_df = ak.stock_news_em(symbol=ticker)

        if news_df.empty:
            return f"未找到股票 {ticker} 的新闻"

        news_str = f"## {ticker} 相关新闻 ({start_date} 到 {end_date}):\n\n"

        # 限制新闻数量
        for idx, row in news_df.head(10).iterrows():
            title = row.get("新闻标题", row.get("title", "无标题"))
            content = str(row.get("新闻内容", row.get("content", "")))[:300]
            source = row.get("文章来源", row.get("source", "未知来源"))
            pub_time = row.get("发布时间", row.get("publish_time", ""))

            news_str += f"### {title}\n"
            news_str += f"来源: {source} | 时间: {pub_time}\n"
            news_str += f"{content}...\n\n"

        return news_str

    except Exception as e:
        return f"获取新闻时出错: {str(e)}"


# === 全局新闻 ===
def get_global_news(
    curr_date: Annotated[str, "当前日期 yyyy-mm-dd"],
    look_back_days: Annotated[int, "回溯天数"] = 7,
    limit: Annotated[int, "新闻条数限制"] = 5,
) -> str:
    """获取全球/宏观财经新闻"""
    if ak is None:
        return "Error: akshare not installed"

    try:
        # 使用东方财富财经快讯
        news_df = ak.stock_info_global_em()

        if news_df.empty:
            return "未找到全球新闻"

        news_str = f"## 全球财经要闻 (截至 {curr_date}):\n\n"

        for idx, row in news_df.head(limit).iterrows():
            title = row.get("标题", row.get("title", ""))
            content = str(row.get("内容", row.get("content", "")))[:400]

            news_str += f"### {title}\n{content}...\n\n"

        return news_str

    except Exception as e:
        return f"获取全球新闻时出错: {str(e)}"


# === 公司基本面 ===
def get_fundamentals(
    ticker: Annotated[str, "A股代码"],
    curr_date: Annotated[str, "当前日期 yyyy-mm-dd"] = None,
) -> str:
    """获取公司基本面数据"""
    if ak is None:
        return "Error: akshare not installed"

    try:
        # 使用 AKShare 获取公司概况
        info_df = ak.stock_individual_info_em(symbol=ticker)

        if info_df.empty:
            return f"未找到股票 {ticker} 的基本面数据"

        result = f"## {ticker} 公司概况:\n\n"
        for _, row in info_df.iterrows():
            item = row.get("item", row.get("项目", ""))
            value = row.get("value", row.get("值", ""))
            result += f"- {item}: {value}\n"

        return result

    except Exception as e:
        return f"获取基本面数据时出错: {str(e)}"


# === 财务报表 (简化实现) ===
def get_balance_sheet(
    ticker: Annotated[str, "A股代码"],
    freq: Annotated[str, "频率: quarterly 或 annual"] = "quarterly",
    curr_date: Annotated[str, "当前日期"] = None,
) -> str:
    """获取资产负债表"""
    if ak is None:
        return "Error: akshare not installed"

    try:
        df = ak.stock_balance_sheet_by_report_em(symbol=ticker)
        if df.empty:
            return f"未找到股票 {ticker} 的资产负债表"

        # 取最近几期数据
        result = f"## {ticker} 资产负债表 (最近数据):\n\n"
        result += df.head(5).to_string()
        return result
    except Exception as e:
        return f"获取资产负债表时出错: {str(e)}"


def get_cashflow(
    ticker: Annotated[str, "A股代码"],
    freq: Annotated[str, "频率: quarterly 或 annual"] = "quarterly",
    curr_date: Annotated[str, "当前日期"] = None,
) -> str:
    """获取现金流量表"""
    if ak is None:
        return "Error: akshare not installed"

    try:
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=ticker)
        if df.empty:
            return f"未找到股票 {ticker} 的现金流量表"

        result = f"## {ticker} 现金流量表 (最近数据):\n\n"
        result += df.head(5).to_string()
        return result
    except Exception as e:
        return f"获取现金流量表时出错: {str(e)}"


def get_income_statement(
    ticker: Annotated[str, "A股代码"],
    freq: Annotated[str, "频率: quarterly 或 annual"] = "quarterly",
    curr_date: Annotated[str, "当前日期"] = None,
) -> str:
    """获取利润表"""
    if ak is None:
        return "Error: akshare not installed"

    try:
        df = ak.stock_profit_sheet_by_report_em(symbol=ticker)
        if df.empty:
            return f"未找到股票 {ticker} 的利润表"

        result = f"## {ticker} 利润表 (最近数据):\n\n"
        result += df.head(5).to_string()
        return result
    except Exception as e:
        return f"获取利润表时出错: {str(e)}"


# === 内部交易 (A股: 大股东增减持) ===
def get_insider_transactions(
    ticker: Annotated[str, "A股代码"],
    curr_date: Annotated[str, "当前日期"] = None,
) -> str:
    """获取大股东增减持信息"""
    if ak is None:
        return "Error: akshare not installed"

    try:
        # 股票质押信息作为内部交易的替代
        df = ak.stock_gpzy_pledge_ratio_em()
        # 筛选特定股票
        if "股票代码" in df.columns:
            df = df[df["股票代码"] == ticker]
        elif "代码" in df.columns:
            df = df[df["代码"] == ticker]

        if df.empty:
            return f"未找到股票 {ticker} 的大股东交易数据"

        result = f"## {ticker} 股东质押情况:\n\n"
        result += df.head(10).to_string()
        return result

    except Exception as e:
        return f"获取大股东交易数据时出错: {str(e)}"


def get_insider_sentiment(
    ticker: Annotated[str, "A股代码"],
    curr_date: Annotated[str, "当前日期"] = None,
) -> str:
    """获取内部人情绪 (A股不直接支持)"""
    return f"A股暂不支持内部人情绪指标。可通过大股东增减持、股票质押率等间接判断 (股票: {ticker})"
