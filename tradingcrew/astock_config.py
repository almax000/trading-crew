"""
A股回测配置预设

提供针对 A股市场优化的默认配置，使用 AKShare 作为数据源。
"""

from tradingcrew.default_config import DEFAULT_CONFIG


# A股专用配置
ASTOCK_CONFIG = DEFAULT_CONFIG.copy()

# 更新数据供应商为 AKShare
ASTOCK_CONFIG.update({
    # 数据供应商配置 - 全部使用 akshare
    "data_vendors": {
        "core_stock_apis": "akshare",
        "technical_indicators": "akshare",
        "fundamental_data": "akshare",
        "news_data": "akshare",
    },

    # A股特有配置
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
    获取自定义的 A股配置

    Args:
        llm_provider: LLM 提供商 (openai, anthropic, google, ollama, openrouter)
        deep_think_llm: 深度思考模型 (用于研究经理和风险经理)
        quick_think_llm: 快速思考模型 (用于分析师、研究员、交易员)
        max_debate_rounds: 研究团队辩论轮数
        max_risk_discuss_rounds: 风险团队讨论轮数

    Returns:
        配置字典
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


# 快速回测配置 (减少辩论轮数以加快速度)
ASTOCK_FAST_CONFIG = get_astock_config(
    max_debate_rounds=1,
    max_risk_discuss_rounds=1,
)

# 深度回测配置 (更多辩论轮数以提高决策质量)
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
    获取使用本地 Ollama 的 A股配置

    Args:
        model: Ollama 模型名称 (如 qwen2:7b, llama3.1:7b)
        ollama_url: Ollama API 地址
        max_debate_rounds: 研究团队辩论轮数
        max_risk_discuss_rounds: 风险团队讨论轮数

    Returns:
        配置字典
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


# Ollama 本地部署配置 (使用 Qwen2.5 7B，32k 上下文窗口)
ASTOCK_OLLAMA_CONFIG = get_ollama_config(
    model="qwen2.5-32k",
    max_debate_rounds=1,
    max_risk_discuss_rounds=1,
)


