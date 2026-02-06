"""
TradingCrew 中文提示词

用于让 LLM Agent 使用中文输出分析报告
"""

# Agent 中英文名称映射
AGENT_NAMES_CN = {
    "Market Analyst": "市场分析师",
    "Social Analyst": "舆情分析师",
    "News Analyst": "新闻分析师",
    "Fundamentals Analyst": "基本面分析师",
    "Bull Researcher": "看多研究员",
    "Bear Researcher": "看空研究员",
    "Research Manager": "研究经理",
    "Trader": "交易员",
    "Risky Analyst": "激进风控",
    "Neutral Analyst": "中性风控",
    "Safe Analyst": "保守风控",
    "Risk Manager": "风险经理",
    "Portfolio Manager": "组合经理",
}

# 中文输出指令 - 追加到现有 prompt 末尾
CHINESE_OUTPUT_INSTRUCTION = """

[重要输出要求]
请使用中文输出你的分析报告和讨论内容。

格式要求:
1. 关键术语可保留英文原文并在括号内标注中文解释
   例如: MACD (移动平均收敛发散), RSI (相对强弱指标), P/E (市盈率)

2. 分析结构建议:
   - 核心观点: 关键结论
   - 数据支撑: 具体数据和指标
   - 风险提示: 潜在风险因素
   - 交易建议: 买入/卖出/持有 及理由

3. 数字和百分比使用阿拉伯数字
   例如: 涨幅 5.23%, 成交量 100万股

4. 日期使用 YYYY-MM-DD 格式

请确保分析内容专业、客观、逻辑清晰。
"""

# 市场分析师专用中文指令
CHINESE_MARKET_ANALYST_INSTRUCTION = """

[重要输出要求]
请使用中文输出你的市场技术分析报告。

重点关注以下技术指标并用中文解释:
- MACD (移动平均收敛发散): 趋势和动量
- RSI (相对强弱指标): 超买超卖信号
- 布林带 (Bollinger Bands): 波动性和价格通道
- 均线系统: MA5, MA10, MA20, MA60 的位置关系
- 成交量: 量价关系分析

分析结构:
1. 趋势判断: 当前处于上升/下降/震荡趋势
2. 技术信号: 各指标给出的信号汇总
3. 支撑阻力: 关键价格位置
4. 技术建议: 基于技术分析的操作建议
"""

# 研究员辩论专用中文指令
CHINESE_RESEARCHER_INSTRUCTION = """

[重要输出要求]
请使用中文进行投资辩论。

辩论要求:
1. 立场明确: 清晰表达你的看多/看空观点
2. 论据充分: 用数据和事实支持你的观点
3. 逻辑严密: 分析推理过程要清晰
4. 反驳有力: 针对对方观点进行针对性反驳

辩论结构:
- 核心观点: 一句话概括你的立场
- 主要论据: 2-3个支持你观点的关键论据
- 风险/机会分析: 从你的角度分析潜在风险或机会
- 结论: 重申你的投资建议
"""

# 风控团队专用中文指令
CHINESE_RISK_INSTRUCTION = """

[重要输出要求]
请使用中文进行风险讨论。

风险分析要点:
1. 市场风险: 大盘走势、行业周期等系统性风险
2. 个股风险: 公司基本面、流动性等个股特有风险
3. 操作风险: 仓位管理、止损止盈等交易执行风险
4. 时机风险: 入场时机、持有周期等时间维度风险

讨论结构:
- 风险识别: 列出主要风险点
- 风险评估: 对风险进行量化或定性评估
- 风险建议: 提出风险控制建议
- 最终意见: 基于风险收益比给出操作建议
"""


def get_chinese_suffix(agent_type: str = "general") -> str:
    """
    获取中文输出指令后缀

    Args:
        agent_type: Agent 类型
            - general: 通用
            - market: 市场分析师
            - researcher: 研究员
            - risk: 风控团队

    Returns:
        中文指令字符串
    """
    suffixes = {
        "general": CHINESE_OUTPUT_INSTRUCTION,
        "market": CHINESE_MARKET_ANALYST_INSTRUCTION,
        "researcher": CHINESE_RESEARCHER_INSTRUCTION,
        "risk": CHINESE_RISK_INSTRUCTION,
    }
    return suffixes.get(agent_type, CHINESE_OUTPUT_INSTRUCTION)
