"""
Multi-market configuration module

Supports configuration management for A-share, US, and HK stock markets.
"""

from tradingcrew.default_config import DEFAULT_CONFIG


# ============================================================
# Market definitions
# ============================================================

MARKET_INFO = {
    "A-share": {
        "name": "A-Share",
        "name_en": "A-Share (China)",
        "currency": "CNY",
        "trading_hours": "09:30-11:30, 13:00-15:00",
        "timezone": "Asia/Shanghai",
        "code_format": "6-digit number (e.g. 600519, 000001)",
        "code_example": ["600519", "000858", "300750"],
        "data_vendor": "akshare",
    },
    "US": {
        "name": "US Stock",
        "name_en": "US Stock",
        "currency": "USD",
        "trading_hours": "09:30-16:00 ET",
        "timezone": "America/New_York",
        "code_format": "Letter ticker (e.g. AAPL, MSFT)",
        "code_example": ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"],
        "data_vendor": "yfinance",
    },
    "HK": {
        "name": "HK Stock",
        "name_en": "HK Stock",
        "currency": "HKD",
        "trading_hours": "09:30-12:00, 13:00-16:00 HKT",
        "timezone": "Asia/Hong_Kong",
        "code_format": "Number.HK (e.g. 0700.HK, 9988.HK)",
        "code_example": ["0700.HK", "9988.HK", "0005.HK"],
        "data_vendor": "yfinance",
    },
}


# ============================================================
# A-share configuration
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
# US stock configuration
# ============================================================

USSTOCK_CONFIG = DEFAULT_CONFIG.copy()
USSTOCK_CONFIG.update({
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance,alpha_vantage",  # yfinance primary, alpha_vantage fallback
        "news_data": "alpha_vantage,google",
    },
    "market": "US",
    "currency": "USD",
    "trading_hours": "09:30-16:00 ET",
})


# ============================================================
# HK stock configuration
# ============================================================

HKSTOCK_CONFIG = DEFAULT_CONFIG.copy()
HKSTOCK_CONFIG.update({
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "google",  # HK stock news via Google News
    },
    "market": "HK",
    "currency": "HKD",
    "trading_hours": "09:30-16:00 HKT",
})


# ============================================================
# Configuration getter functions
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
    Get configuration for the specified market

    Args:
        market: Market type ("A-share", "US", "HK")
        llm_provider: LLM provider
        deep_think_llm: Deep thinking model
        quick_think_llm: Quick thinking model
        max_debate_rounds: Number of debate rounds
        max_risk_discuss_rounds: Number of risk discussion rounds

    Returns:
        Configuration dictionary
    """
    # Select base config
    if market == "A-share":
        config = ASTOCK_CONFIG.copy()
    elif market == "US":
        config = USSTOCK_CONFIG.copy()
    elif market == "HK":
        config = HKSTOCK_CONFIG.copy()
    else:
        raise ValueError(f"Unsupported market: {market}")

    # Override optional parameters
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
    Get configuration using OpenAI API

    Args:
        market: Market type ("A-share", "US", "HK")
        deep_think_model: Deep thinking model
        quick_think_model: Quick thinking model
        max_debate_rounds: Number of debate rounds
        max_risk_discuss_rounds: Number of risk discussion rounds

    Returns:
        Configuration dictionary
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
# Model presets
# ============================================================

MODEL_PRESETS = {
    "deepseek-v3": {
        "name": "DeepSeek V3",
        "description": "High cost-effectiveness, strong trading performance",
        "provider": "dashscope",
        "deep_think_model": "deepseek-v3",
        "quick_think_model": "deepseek-v3",
    },
    "qwen3-max": {
        "name": "Qwen3 Max",
        "description": "Top trading competition performer, highest returns",
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
    Get configuration using Alibaba Cloud DashScope API

    Supported models:
    - deepseek-v3: DeepSeek V3
    - qwen3-max: Qwen3 Max

    Args:
        market: Market type ("A-share", "US", "HK")
        model: Model name ("deepseek-v3", "qwen3-max")
        max_debate_rounds: Number of debate rounds
        max_risk_discuss_rounds: Number of risk discussion rounds

    Returns:
        Configuration dictionary
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()

    # Set DashScope API Key
    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    if dashscope_key:
        os.environ["OPENAI_API_KEY"] = dashscope_key

    # Get model preset
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
    Get configuration using OpenRouter API

    OpenRouter is an international LLM aggregation platform supporting 400+ models
    (GPT, Claude, DeepSeek, etc.) with OpenAI-compatible API and zero markup.

    Supported model presets:
    - gpt-4o: OpenAI GPT-4o
    - claude-sonnet-4: Anthropic Claude Sonnet 4
    - deepseek/deepseek-chat-v3-0324: DeepSeek V3

    Args:
        market: Market type ("A-share", "US", "HK")
        model: Model name (OpenRouter models from MODEL_PRESETS)
        max_debate_rounds: Number of debate rounds
        max_risk_discuss_rounds: Number of risk discussion rounds

    Returns:
        Configuration dictionary
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()

    # Set OpenRouter API Key
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        os.environ["OPENAI_API_KEY"] = openrouter_key

    # Get model preset
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
