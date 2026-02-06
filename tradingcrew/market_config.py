"""
多市场配置模块

支持 A股、美股、港股的配置管理
"""

from tradingcrew.default_config import DEFAULT_CONFIG


# ============================================================
# 市场定义
# ============================================================

MARKET_INFO = {
    "A-share": {
        "name": "A股",
        "name_en": "A-Share (China)",
        "currency": "CNY",
        "trading_hours": "09:30-11:30, 13:00-15:00",
        "timezone": "Asia/Shanghai",
        "code_format": "6位数字 (如 600519, 000001)",
        "code_example": ["600519", "000858", "300750"],
        "data_vendor": "akshare",
    },
    "US": {
        "name": "美股",
        "name_en": "US Stock",
        "currency": "USD",
        "trading_hours": "09:30-16:00 ET",
        "timezone": "America/New_York",
        "code_format": "字母代码 (如 AAPL, MSFT)",
        "code_example": ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"],
        "data_vendor": "yfinance",
    },
    "HK": {
        "name": "港股",
        "name_en": "HK Stock",
        "currency": "HKD",
        "trading_hours": "09:30-12:00, 13:00-16:00 HKT",
        "timezone": "Asia/Hong_Kong",
        "code_format": "数字.HK (如 0700.HK, 9988.HK)",
        "code_example": ["0700.HK", "9988.HK", "0005.HK"],
        "data_vendor": "yfinance",
    },
}


# ============================================================
# A股配置
# ============================================================

ASTOCK_CONFIG = DEFAULT_CONFIG.copy()
ASTOCK_CONFIG.update({
    "data_vendors": {
        "core_stock_apis": "akshare",
        "technical_indicators": "akshare",
        "fundamental_data": "akshare",
        "news_data": "akshare",
    },
    "market": "A-share",
    "currency": "CNY",
    "trading_hours": "09:30-15:00",
})


# ============================================================
# 美股配置
# ============================================================

USSTOCK_CONFIG = DEFAULT_CONFIG.copy()
USSTOCK_CONFIG.update({
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance,alpha_vantage",  # yfinance 优先，alpha_vantage 备用
        "news_data": "alpha_vantage,google",
    },
    "market": "US",
    "currency": "USD",
    "trading_hours": "09:30-16:00 ET",
})


# ============================================================
# 港股配置
# ============================================================

HKSTOCK_CONFIG = DEFAULT_CONFIG.copy()
HKSTOCK_CONFIG.update({
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "google",  # 港股新闻用 Google News
    },
    "market": "HK",
    "currency": "HKD",
    "trading_hours": "09:30-16:00 HKT",
})


# ============================================================
# 配置获取函数
# ============================================================

def get_market_config(
    market: str,
    llm_provider: str = None,
    deep_think_llm: str = None,
    quick_think_llm: str = None,
    max_debate_rounds: int = None,
    max_risk_discuss_rounds: int = None,
) -> dict:
    """
    获取指定市场的配置

    Args:
        market: 市场类型 ("A-share", "US", "HK")
        llm_provider: LLM 提供商
        deep_think_llm: 深度思考模型
        quick_think_llm: 快速思考模型
        max_debate_rounds: 辩论轮数
        max_risk_discuss_rounds: 风险讨论轮数

    Returns:
        配置字典
    """
    # 选择基础配置
    if market == "A-share":
        config = ASTOCK_CONFIG.copy()
    elif market == "US":
        config = USSTOCK_CONFIG.copy()
    elif market == "HK":
        config = HKSTOCK_CONFIG.copy()
    else:
        raise ValueError(f"不支持的市场: {market}")

    # 覆盖可选参数
    if llm_provider is not None:
        config["llm_provider"] = llm_provider
    if deep_think_llm is not None:
        config["deep_think_llm"] = deep_think_llm
    if quick_think_llm is not None:
        config["quick_think_llm"] = quick_think_llm
    if max_debate_rounds is not None:
        config["max_debate_rounds"] = max_debate_rounds
    if max_risk_discuss_rounds is not None:
        config["max_risk_discuss_rounds"] = max_risk_discuss_rounds

    return config


def get_openai_config(
    market: str = "US",
    deep_think_model: str = "o4-mini",
    quick_think_model: str = "gpt-4o-mini",
    max_debate_rounds: int = 2,
    max_risk_discuss_rounds: int = 2,
) -> dict:
    """
    获取使用 OpenAI API 的配置

    Args:
        market: 市场类型 ("A-share", "US", "HK")
        deep_think_model: 深度思考模型
        quick_think_model: 快速思考模型
        max_debate_rounds: 辩论轮数
        max_risk_discuss_rounds: 风险讨论轮数

    Returns:
        配置字典
    """
    config = get_market_config(market)
    config.update({
        "llm_provider": "openai",
        "deep_think_llm": deep_think_model,
        "quick_think_llm": quick_think_model,
        "max_debate_rounds": max_debate_rounds,
        "max_risk_discuss_rounds": max_risk_discuss_rounds,
    })
    return config


# ============================================================
# 模型预设
# ============================================================

MODEL_PRESETS = {
    "deepseek-v3": {
        "name": "DeepSeek V3",
        "description": "炒股大赛亚军，性价比高",
        "provider": "dashscope",
        "deep_think_model": "deepseek-v3",
        "quick_think_model": "deepseek-v3",
    },
    "qwen3-max": {
        "name": "Qwen3 Max",
        "description": "炒股大赛冠军，收益率最高",
        "provider": "dashscope",
        "deep_think_model": "qwen3-max",
        "quick_think_model": "qwen3-max",
    },
    "gpt-4o": {
        "name": "GPT-4o",
        "description": "OpenAI GPT-4o via OpenRouter",
        "provider": "openrouter",
        "deep_think_model": "openai/gpt-4o",
        "quick_think_model": "openai/gpt-4o-mini",
    },
    "claude-sonnet-4": {
        "name": "Claude Sonnet 4",
        "description": "Anthropic Claude Sonnet 4 via OpenRouter",
        "provider": "openrouter",
        "deep_think_model": "anthropic/claude-sonnet-4",
        "quick_think_model": "anthropic/claude-sonnet-4",
    },
    "deepseek/deepseek-chat-v3-0324": {
        "name": "DeepSeek V3 (OpenRouter)",
        "description": "DeepSeek V3 via OpenRouter",
        "provider": "openrouter",
        "deep_think_model": "deepseek/deepseek-chat-v3-0324",
        "quick_think_model": "deepseek/deepseek-chat-v3-0324",
    },
}


def get_dashscope_config(
    market: str = "A-share",
    model: str = "deepseek-v3",
    max_debate_rounds: int = 2,
    max_risk_discuss_rounds: int = 2,
) -> dict:
    """
    获取使用阿里云百炼 (DashScope) API 的配置

    支持的模型:
    - deepseek-v3: DeepSeek V3 (炒股大赛亚军)
    - qwen3-max: Qwen3 Max (炒股大赛冠军)

    Args:
        market: 市场类型 ("A-share", "US", "HK")
        model: 模型名称 ("deepseek-v3", "qwen3-max")
        max_debate_rounds: 辩论轮数
        max_risk_discuss_rounds: 风险讨论轮数

    Returns:
        配置字典
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()

    # 设置 DashScope API Key
    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    if dashscope_key:
        os.environ["OPENAI_API_KEY"] = dashscope_key

    # 获取模型预设
    preset = MODEL_PRESETS.get(model, MODEL_PRESETS["deepseek-v3"])

    config = get_market_config(market)
    config.update({
        "llm_provider": "dashscope",
        "backend_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "deep_think_llm": preset["deep_think_model"],
        "quick_think_llm": preset["quick_think_model"],
        "max_debate_rounds": max_debate_rounds,
        "max_risk_discuss_rounds": max_risk_discuss_rounds,
    })
    return config


def get_openrouter_config(
    market: str = "US",
    model: str = "gpt-4o",
    max_debate_rounds: int = 2,
    max_risk_discuss_rounds: int = 2,
) -> dict:
    """
    获取使用 OpenRouter API 的配置

    OpenRouter 是国际 LLM 聚合平台，支持 400+ 模型 (GPT, Claude, DeepSeek 等)，
    OpenAI 兼容 API，零加价。

    支持的模型预设:
    - gpt-4o: OpenAI GPT-4o
    - claude-sonnet-4: Anthropic Claude Sonnet 4
    - deepseek/deepseek-chat-v3-0324: DeepSeek V3

    Args:
        market: 市场类型 ("A-share", "US", "HK")
        model: 模型名称 (MODEL_PRESETS 中的 openrouter 模型)
        max_debate_rounds: 辩论轮数
        max_risk_discuss_rounds: 风险讨论轮数

    Returns:
        配置字典
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()

    # 设置 OpenRouter API Key
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        os.environ["OPENAI_API_KEY"] = openrouter_key

    # 获取模型预设
    preset = MODEL_PRESETS.get(model, MODEL_PRESETS["gpt-4o"])

    config = get_market_config(market)
    config.update({
        "llm_provider": "openrouter",
        "backend_url": "https://openrouter.ai/api/v1",
        "deep_think_llm": preset["deep_think_model"],
        "quick_think_llm": preset["quick_think_model"],
        "max_debate_rounds": max_debate_rounds,
        "max_risk_discuss_rounds": max_risk_discuss_rounds,
    })
    return config
