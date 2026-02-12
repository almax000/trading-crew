"""
TradingCrew prompt instructions

Instructions for LLM Agents to output analysis reports.
"""

# Agent name mapping
AGENT_NAMES_CN = {
    "Market Analyst": "Market Analyst",
    "Social Analyst": "Social Analyst",
    "News Analyst": "News Analyst",
    "Fundamentals Analyst": "Fundamentals Analyst",
    "Bull Researcher": "Bull Researcher",
    "Bear Researcher": "Bear Researcher",
    "Research Manager": "Research Manager",
    "Trader": "Trader",
    "Risky Analyst": "Risky Analyst",
    "Neutral Analyst": "Neutral Analyst",
    "Safe Analyst": "Safe Analyst",
    "Risk Manager": "Risk Manager",
    "Portfolio Manager": "Portfolio Manager",
}

# Output instruction - appended to existing prompts
CHINESE_OUTPUT_INSTRUCTION = """

[Important Output Requirements]
Please output your analysis report and discussion content in a professional manner.

Format requirements:
1. Use proper financial terminology with explanations where needed
   Example: MACD (Moving Average Convergence Divergence), RSI (Relative Strength Index), P/E (Price-to-Earnings Ratio)

2. Recommended analysis structure:
   - Core View: Key conclusions
   - Data Support: Specific data and indicators
   - Risk Alerts: Potential risk factors
   - Trading Recommendation: Buy/Sell/Hold with rationale

3. Use standard number and percentage formats
   Example: gain of 5.23%, volume of 1M shares

4. Use YYYY-MM-DD date format

Ensure the analysis is professional, objective, and logically coherent.
"""

# Market analyst specific instruction
CHINESE_MARKET_ANALYST_INSTRUCTION = """

[Important Output Requirements]
Please output your market technical analysis report professionally.

Focus on the following technical indicators:
- MACD (Moving Average Convergence Divergence): Trend and momentum
- RSI (Relative Strength Index): Overbought/oversold signals
- Bollinger Bands: Volatility and price channels
- Moving Average System: MA5, MA10, MA20, MA60 relative positions
- Volume: Price-volume relationship analysis

Analysis structure:
1. Trend Assessment: Current uptrend/downtrend/sideways trend
2. Technical Signals: Summary of signals from each indicator
3. Support & Resistance: Key price levels
4. Technical Recommendation: Trading recommendation based on technical analysis
"""

# Researcher debate instruction
CHINESE_RESEARCHER_INSTRUCTION = """

[Important Output Requirements]
Please conduct the investment debate professionally.

Debate requirements:
1. Clear Position: Clearly express your bullish/bearish view
2. Sufficient Evidence: Support your view with data and facts
3. Sound Logic: Make your reasoning process clear
4. Strong Rebuttals: Provide targeted counterarguments to opposing views

Debate structure:
- Core View: One-sentence summary of your position
- Key Arguments: 2-3 key arguments supporting your view
- Risk/Opportunity Analysis: Analyze potential risks or opportunities from your perspective
- Conclusion: Restate your investment recommendation
"""

# Risk team instruction
CHINESE_RISK_INSTRUCTION = """

[Important Output Requirements]
Please conduct the risk discussion professionally.

Risk analysis focus areas:
1. Market Risk: Systemic risks such as market trends, industry cycles
2. Stock-Specific Risk: Company fundamentals, liquidity, and other stock-specific risks
3. Execution Risk: Position sizing, stop-loss/take-profit, and trade execution risks
4. Timing Risk: Entry timing, holding period, and time-related risks

Discussion structure:
- Risk Identification: List major risk factors
- Risk Assessment: Quantitative or qualitative risk evaluation
- Risk Recommendations: Propose risk control measures
- Final Opinion: Provide trading recommendation based on risk-reward ratio
"""


def get_chinese_suffix(agent_type: str = "general") -> str:
    """
    Get the output instruction suffix

    Args:
        agent_type: Agent type
            - general: General
            - market: Market analyst
            - researcher: Researcher
            - risk: Risk team

    Returns:
        Instruction string
    """
    suffixes = {
        "general": CHINESE_OUTPUT_INSTRUCTION,
        "market": CHINESE_MARKET_ANALYST_INSTRUCTION,
        "researcher": CHINESE_RESEARCHER_INSTRUCTION,
        "risk": CHINESE_RISK_INSTRUCTION,
    }
    return suffixes.get(agent_type, CHINESE_OUTPUT_INSTRUCTION)
