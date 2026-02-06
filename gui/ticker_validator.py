"""
股票代码验证模块

提供股票代码格式验证和名称查询功能。
支持 A股、港股、美股。
"""

import re
from typing import Tuple


def validate_a_share_code(code: str) -> bool:
    """
    验证 A 股代码格式

    规则:
    - 6位数字
    - 上海: 600xxx, 601xxx, 603xxx, 605xxx, 688xxx (科创板)
    - 深圳: 000xxx, 001xxx, 002xxx (中小板), 300xxx (创业板)
    """
    code = code.strip()
    if not re.match(r"^\d{6}$", code):
        return False

    prefix = code[:3]
    valid_prefixes = ["600", "601", "603", "605", "688", "000", "001", "002", "300"]
    return prefix in valid_prefixes


def validate_us_stock_code(code: str) -> bool:
    """
    验证美股代码格式

    规则:
    - 1-5 个大写字母
    - 可选: 带 . 的类别标识 (如 BRK.B, BRK-B)
    """
    code = code.strip().upper()
    # 标准股票代码: 1-5 个字母
    if re.match(r"^[A-Z]{1,5}$", code):
        return True
    # 带类别的代码: 如 BRK.B, BRK-B
    if re.match(r"^[A-Z]{1,4}[.\-][A-Z]$", code):
        return True
    return False


def validate_hk_stock_code(code: str) -> bool:
    """
    验证港股代码格式

    规则:
    - 4-5 位数字 + .HK 后缀
    - 例如: 0700.HK, 9988.HK, 00005.HK
    """
    code = code.strip().upper()
    # 标准格式: 数字.HK
    if re.match(r"^\d{4,5}\.HK$", code):
        return True
    # 也接受纯数字 (自动补 .HK)
    if re.match(r"^\d{1,5}$", code):
        return True
    return False


def normalize_ticker(code: str, market: str) -> str:
    """
    标准化股票代码

    Args:
        code: 原始代码
        market: 市场类型

    Returns:
        标准化后的代码
    """
    code = code.strip()

    if market == "US":
        return code.upper()
    elif market == "HK":
        code = code.upper()
        # 去除 .HK 后缀以便处理
        clean_code = code.replace(".HK", "")
        # 补齐前导零 (如 700 -> 0700)
        if len(clean_code) < 4:
            clean_code = clean_code.zfill(4)
        return f"{clean_code}.HK"
    else:
        # A股保持原样
        return code


def get_stock_name_a_share(ticker: str) -> Tuple[bool, str]:
    """
    获取 A 股股票名称

    Args:
        ticker: A股代码 (6位数字)

    Returns:
        (success, name_or_error)
    """
    try:
        import akshare as ak
        info = ak.stock_individual_info_em(symbol=ticker)
        name = info[info['item'] == '股票简称']['value'].values[0]
        return True, name
    except ImportError:
        # akshare 未安装，返回通用成功
        return True, ""
    except Exception as e:
        return False, f"未找到该股票: {ticker}"


def get_stock_name_hk(ticker: str) -> Tuple[bool, str]:
    """
    获取港股股票名称

    Args:
        ticker: 港股代码 (如 0700.HK)

    Returns:
        (success, name_or_error)
    """
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        name = info.get("longName") or info.get("shortName") or ""
        if name:
            return True, name
        return True, ""  # 可能没有名称但代码有效
    except ImportError:
        return True, ""
    except Exception as e:
        return False, f"未找到该股票: {ticker}"


def get_stock_name_us(ticker: str) -> Tuple[bool, str]:
    """
    获取美股股票名称

    Args:
        ticker: 美股代码 (如 AAPL)

    Returns:
        (success, name_or_error)
    """
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        name = info.get("longName") or info.get("shortName") or ""
        if name:
            return True, name
        return True, ""  # 可能没有名称但代码有效
    except ImportError:
        return True, ""
    except Exception as e:
        return False, f"未找到该股票: {ticker}"


def validate_and_get_name(ticker: str, market: str) -> Tuple[bool, str, str]:
    """
    验证股票代码并获取名称

    Args:
        ticker: 股票代码
        market: 市场类型 (A-share, US, HK)

    Returns:
        (is_valid, normalized_ticker, stock_name_or_error)
    """
    ticker = ticker.strip()

    if not ticker:
        return False, "", "请输入股票代码"

    # 格式验证
    if market == "A-share":
        if not validate_a_share_code(ticker):
            return False, "", "A股代码应为6位数字（如 600519、000001）"
        normalized = normalize_ticker(ticker, market)
        success, name = get_stock_name_a_share(normalized)
        if success:
            return True, normalized, name
        return False, "", name

    elif market == "US":
        if not validate_us_stock_code(ticker):
            return False, "", "美股代码应为1-5位字母（如 AAPL、TSLA）"
        normalized = normalize_ticker(ticker, market)
        success, name = get_stock_name_us(normalized)
        if success:
            return True, normalized, name
        return False, "", name

    elif market == "HK":
        if not validate_hk_stock_code(ticker):
            return False, "", "港股代码应为4-5位数字（如 0700、9988）"
        normalized = normalize_ticker(ticker, market)
        success, name = get_stock_name_hk(normalized)
        if success:
            return True, normalized, name
        return False, "", name

    return False, "", f"不支持的市场类型: {market}"


def validate_ticker_format(ticker: str, market: str) -> Tuple[bool, str, str]:
    """
    仅验证股票代码格式（不查询名称，速度快）

    Args:
        ticker: 股票代码
        market: 市场类型 (A-share, US, HK)

    Returns:
        (is_valid, normalized_ticker, error_message)
    """
    ticker = ticker.strip()

    if not ticker:
        return False, "", "请输入股票代码"

    if market == "A-share":
        if not validate_a_share_code(ticker):
            return False, "", "A股代码应为6位数字（如 600519、000001）"
        return True, normalize_ticker(ticker, market), ""

    elif market == "US":
        if not validate_us_stock_code(ticker):
            return False, "", "美股代码应为1-5位字母（如 AAPL、TSLA）"
        return True, normalize_ticker(ticker, market), ""

    elif market == "HK":
        if not validate_hk_stock_code(ticker):
            return False, "", "港股代码应为4-5位数字（如 0700、9988）"
        return True, normalize_ticker(ticker, market), ""

    return False, "", f"不支持的市场类型: {market}"
