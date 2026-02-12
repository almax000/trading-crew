"""
A-share backtest configuration presets

Provides default configurations optimized for the A-share market, using AKShare as data source.
"""

from tradingcrew.default_config import DEFAULT_CONFIG


# A-share specific configuration
ASTOCK_CONFIG = DEFAULT_CONFIG.copy()

# Update data vendors to AKShare
ASTOCK_CONFIG.update({
    # Data vendor configuration - all using akshare
    "data_vendors": {
        "core_stock_apis": "akshare",
        "technical_indicators": "akshare",
        "fundamental_data": "akshare",
        "news_data": "akshare",
    },

    # A-share specific settings
    "market": "A-share",
    "currency": "CNY",
    "trading_hours": "09:30-15:00",
})


def get_astock_config(
    llm_provider: str = None,
    deep_think_llm: str = None,
    quick_think_llm: str = None,
    max_debate_rounds: int = None,
    max_risk_discuss_rounds: int = None,
) -> dict:
    """
    Get customized A-share configuration

    Args:
        llm_provider: LLM provider (openai, anthropic, google, ollama, openrouter)
        deep_think_llm: Deep thinking model (for research manager and risk manager)
        quick_think_llm: Quick thinking model (for analysts, researchers, trader)
        max_debate_rounds: Research team debate rounds
        max_risk_discuss_rounds: Risk team discussion rounds

    Returns:
        Configuration dictionary
    """
    config = ASTOCK_CONFIG.copy()

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


# Fast backtest config (fewer debate rounds for speed)
ASTOCK_FAST_CONFIG = get_astock_config(
    max_debate_rounds=1,
    max_risk_discuss_rounds=1,
)

# Deep backtest config (more debate rounds for better decisions)
ASTOCK_DEEP_CONFIG = get_astock_config(
    max_debate_rounds=3,
    max_risk_discuss_rounds=2,
)


def get_ollama_config(
    model: str = "qwen2:7b",
    ollama_url: str = "http://localhost:11434/v1",
    max_debate_rounds: int = 1,
    max_risk_discuss_rounds: int = 1,
) -> dict:
    """
    Get A-share configuration using local Ollama

    Args:
        model: Ollama model name (e.g. qwen2:7b, llama3.1:7b)
        ollama_url: Ollama API URL
        max_debate_rounds: Research team debate rounds
        max_risk_discuss_rounds: Risk team discussion rounds

    Returns:
        Configuration dictionary
    """
    config = ASTOCK_CONFIG.copy()
    config.update({
        "llm_provider": "ollama",
        "backend_url": ollama_url,
        "deep_think_llm": model,
        "quick_think_llm": model,
        "max_debate_rounds": max_debate_rounds,
        "max_risk_discuss_rounds": max_risk_discuss_rounds,
    })
    return config


# Ollama local deployment config (using Qwen2.5 7B, 32k context window)
ASTOCK_OLLAMA_CONFIG = get_ollama_config(
    model="qwen2.5-32k",
    max_debate_rounds=1,
    max_risk_discuss_rounds=1,
)
