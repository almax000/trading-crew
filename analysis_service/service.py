"""
分析服务封装

封装 TradingCrewGraph，提供流式输出接口。
"""

from typing import Dict, Any, List, Generator, AsyncGenerator
from datetime import datetime
import traceback
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Agent 显示名称映射
AGENT_DISPLAY_NAMES = {
    "Market Analyst": "市场分析师",
    "Social Analyst": "舆情分析师",
    "News Analyst": "新闻分析师",
    "Fundamentals Analyst": "基本面分析师",
    "Bull Researcher": "看多研究员",
    "Bear Researcher": "看空研究员",
    "Research Manager": "研究主管",
    "Trader": "交易员",
    "Risky Analyst": "激进风控",
    "Safe Analyst": "保守风控",
    "Neutral Analyst": "中性风控",
    "Risk Manager": "风控主管",
    "Portfolio Manager": "组合经理",
}


class AnalysisService:
    """
    分析服务

    封装 TradingCrewGraph，提供流式分析功能。
    优先使用阿里云百炼 API（如果配置了 DASHSCOPE_API_KEY）。
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化分析服务

        Args:
            config: TradingCrew 配置，可覆盖默认配置
        """
        from dotenv import load_dotenv

        # 先加载 .env 文件
        load_dotenv()

        self.custom_config = config

        # 检测可用的 API
        self.has_dashscope = bool(os.environ.get("DASHSCOPE_API_KEY"))
        self.has_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))

        # 延迟初始化
        self._graph = None
        self._current_market = None

    def _get_config(self, market: str, model: str = None) -> Dict[str, Any]:
        """
        获取指定市场和模型的配置

        Args:
            market: 市场类型 ("A-share", "US", "HK")
            model: 模型名称 ("deepseek-v3", "qwen3-max", "gpt-4o", "claude-sonnet-4", etc.)
        """
        # 默认使用 deepseek-v3
        if not model:
            model = "deepseek-v3"

        from tradingcrew.market_config import MODEL_PRESETS

        # 根据模型预设的 provider 选择配置
        preset = MODEL_PRESETS.get(model)
        if preset and preset["provider"] == "dashscope":
            from tradingcrew.market_config import get_dashscope_config
            config = get_dashscope_config(market=market, model=model)
        elif preset and preset["provider"] == "openrouter":
            from tradingcrew.market_config import get_openrouter_config
            config = get_openrouter_config(market=market, model=model)
        else:
            # 未知模型，使用默认
            from tradingcrew.market_config import get_dashscope_config
            config = get_dashscope_config(market=market, model="deepseek-v3")

        # 应用自定义配置
        if self.custom_config:
            config.update(self.custom_config)

        return config

    def _create_graph(self, market: str, selected_analysts: List[str] = None, model: str = None):
        """
        创建新的 TradingCrewGraph 实例

        每次分析都创建新实例，避免并发时 ChromaDB collection 冲突。

        Args:
            market: 市场类型 (A-share, US, HK)
            selected_analysts: 启用的分析师列表
            model: 模型名称 ("deepseek-v3", "qwen3-max")
        """
        from tradingcrew.graph.trading_graph import TradingCrewGraph

        config = self._get_config(market, model)

        return TradingCrewGraph(
            selected_analysts=selected_analysts or ["market", "social", "news", "fundamentals"],
            debug=False,
            config=config,
        )

    def analyze_stream(
        self,
        ticker: str,
        date: str,
        market: str = "A-share",
        selected_analysts: List[str] = None,
        model: str = None,
    ) -> Generator[tuple, None, None]:
        """
        流式分析股票

        Args:
            ticker: 股票代码
            date: 分析日期 (YYYY-MM-DD)
            market: 市场类型 (A-share, US, HK)
            selected_analysts: 启用的分析师列表
            model: 模型名称 ("deepseek-v3", "qwen3-max")

        Yields:
            (agent_name, content) - Agent名称和输出内容
            最后一个 yield 为 ("__FINAL__", decision) 表示最终决策
        """
        try:
            # 每次分析创建新的 graph 实例，避免并发冲突
            graph = self._create_graph(market, selected_analysts, model)

            # 创建初始状态
            init_state = graph.propagator.create_initial_state(ticker, date)
            args = graph.propagator.get_graph_args()

            # 跟踪已处理的报告
            processed_reports = set()
            final_state = None

            # 流式执行
            for chunk in graph.graph.stream(init_state, **args):
                final_state = chunk

                # 提取 Agent 更新并 yield
                updates = self._extract_agent_updates(chunk, processed_reports)
                for agent_name, content in updates:
                    yield (agent_name, content)

            # 存储当前状态
            graph.curr_state = final_state
            graph.ticker = ticker

            # 处理信号获取决策
            decision = graph.process_signal(
                final_state.get("final_trade_decision", "HOLD") if final_state else "HOLD"
            )

            # 返回最终决策
            yield ("__FINAL__", decision)

        except Exception as e:
            error_msg = str(e).lower()
            full_error = f"分析出错: {str(e)}\n{traceback.format_exc()}"

            # 检测 API 余额不足
            if any(kw in error_msg for kw in [
                "insufficient_quota",
                "insufficient_balance",
                "quota exceeded",
                "rate limit",
                "billing",
                "payment required",
                "account_deactivated",
            ]):
                yield ("__QUOTA_ERROR__", full_error)

            # 检测超时/网络问题
            elif any(kw in error_msg for kw in [
                "timeout",
                "timed out",
                "connection",
                "reset by peer",
                "connection refused",
                "network",
                "unreachable",
                "ssl",
                "certificate",
            ]):
                yield ("__TIMEOUT_ERROR__", full_error)

            else:
                yield ("__ERROR__", full_error)

    def _extract_agent_updates(
        self,
        chunk: Dict[str, Any],
        processed: set,
    ) -> List[tuple]:
        """
        从流式 chunk 中提取 Agent 更新

        Args:
            chunk: LangGraph 流式 chunk
            processed: 已处理的报告集合 (用于去重)

        Returns:
            [(agent_name, content), ...] 列表
        """
        updates = []

        # 报告字段到 Agent 名称的映射
        report_mappings = {
            "market_report": "Market Analyst",
            "sentiment_report": "Social Analyst",
            "news_report": "News Analyst",
            "fundamentals_report": "Fundamentals Analyst",
            "investment_plan": "Research Manager",
            "trader_investment_plan": "Trader",
            "final_trade_decision": "Portfolio Manager",
        }

        # 检查报告字段
        for field, agent_name in report_mappings.items():
            if field in chunk and chunk[field] and field not in processed:
                content = chunk[field]
                if content.strip():
                    updates.append((agent_name, content))
                    processed.add(field)

        # 检查投资辩论状态
        if "investment_debate_state" in chunk:
            debate = chunk["investment_debate_state"]

            # Bull Researcher
            bull_key = "bull_history"
            if bull_key in debate and debate[bull_key]:
                cache_key = f"bull_{len(debate[bull_key])}"
                if cache_key not in processed:
                    latest = self._get_latest_statement(debate[bull_key], "Bull")
                    if latest:
                        updates.append(("Bull Researcher", latest))
                        processed.add(cache_key)

            # Bear Researcher
            bear_key = "bear_history"
            if bear_key in debate and debate[bear_key]:
                cache_key = f"bear_{len(debate[bear_key])}"
                if cache_key not in processed:
                    latest = self._get_latest_statement(debate[bear_key], "Bear")
                    if latest:
                        updates.append(("Bear Researcher", latest))
                        processed.add(cache_key)

            # Judge Decision
            judge_key = "judge_decision"
            if judge_key in debate and debate[judge_key] and "judge_decision" not in processed:
                updates.append(("Research Manager", debate[judge_key]))
                processed.add("judge_decision")

        # 检查风险辩论状态
        if "risk_debate_state" in chunk:
            risk = chunk["risk_debate_state"]

            for analyst_key, agent_name in [
                ("risky_history", "Risky Analyst"),
                ("safe_history", "Safe Analyst"),
                ("neutral_history", "Neutral Analyst"),
            ]:
                if analyst_key in risk and risk[analyst_key]:
                    cache_key = f"{analyst_key}_{len(risk[analyst_key])}"
                    if cache_key not in processed:
                        latest = self._get_latest_statement(
                            risk[analyst_key],
                            analyst_key.split("_")[0].title()
                        )
                        if latest:
                            updates.append((agent_name, latest))
                            processed.add(cache_key)

            # Risk Judge Decision
            if "judge_decision" in risk and risk["judge_decision"] and "risk_judge_decision" not in processed:
                updates.append(("Risk Manager", risk["judge_decision"]))
                processed.add("risk_judge_decision")

        return updates

    def _get_latest_statement(self, history: str, speaker_prefix: str) -> str:
        """
        从历史记录中提取最新发言

        Args:
            history: 完整历史记录
            speaker_prefix: 发言者前缀 (如 "Bull", "Bear")

        Returns:
            最新发言内容
        """
        if not history:
            return ""

        # 按发言者分割
        statements = history.split(f"{speaker_prefix}")
        if len(statements) > 1:
            # 获取最后一个发言
            last = statements[-1]
            # 清理前缀
            if last.startswith(" Analyst:") or last.startswith(" Researcher:"):
                last = last.split(":", 1)[-1].strip()
            return last.strip()

        return ""

    def get_agent_display_name(self, agent_name: str) -> str:
        """获取 Agent 的中文显示名称"""
        return AGENT_DISPLAY_NAMES.get(agent_name, agent_name)

    async def analyze_stream_tokens(
        self,
        ticker: str,
        date: str,
        market: str = "A-share",
        selected_analysts: List[str] = None,
        model: str = None,
    ) -> AsyncGenerator[tuple, None]:
        """
        Token-level streaming analysis (async generator).

        Args:
            ticker: 股票代码
            date: 分析日期 (YYYY-MM-DD)
            market: 市场类型 (A-share, US, HK)
            selected_analysts: 启用的分析师列表
            model: 模型名称 ("deepseek-v3", "qwen3-max")

        Yields:
            (event_type, agent_name, content) tuples:
            - ("node_start", agent_name, None): Agent started
            - ("token", agent_name, token): Token from LLM
            - ("node_end", agent_name, full_content): Agent finished
            - ("complete", None, decision): Analysis complete
            - ("error", None, error_msg): Error occurred
        """
        # Node name to agent name mapping
        node_to_agent = {
            "market_analyst": "Market Analyst",
            "social_analyst": "Social Analyst",
            "news_analyst": "News Analyst",
            "fundamentals_analyst": "Fundamentals Analyst",
            "bull_researcher": "Bull Researcher",
            "bear_researcher": "Bear Researcher",
            "research_manager": "Research Manager",
            "invest_judge": "Research Manager",
            "trader": "Trader",
            "risky_debator": "Risky Analyst",
            "safe_debator": "Safe Analyst",
            "neutral_debator": "Neutral Analyst",
            "risk_manager": "Risk Manager",
            "risk_judge": "Risk Manager",
            "portfolio_manager": "Portfolio Manager",
        }

        try:
            # Create graph for this analysis
            graph = self._create_graph(market, selected_analysts, model)

            # Use the new streaming method
            async for event_type, node_name, content in graph.propagate_streaming(ticker, date):
                # Map node name to agent name
                agent_name = node_to_agent.get(node_name, node_name) if node_name else None

                if event_type == "complete":
                    yield ("complete", None, content)
                elif event_type == "node_start":
                    yield ("node_start", agent_name, None)
                elif event_type == "token":
                    yield ("token", agent_name, content)
                elif event_type == "node_end":
                    yield ("node_end", agent_name, content)

        except Exception as e:
            error_msg = str(e).lower()
            full_error = f"分析出错: {str(e)}\n{traceback.format_exc()}"

            # Check API quota issues
            if any(kw in error_msg for kw in [
                "insufficient_quota", "insufficient_balance", "quota exceeded",
                "rate limit", "billing", "payment required", "account_deactivated",
            ]):
                yield ("quota_error", None, full_error)
            # Check timeout/network issues
            elif any(kw in error_msg for kw in [
                "timeout", "timed out", "connection", "reset by peer",
                "connection refused", "network", "unreachable", "ssl", "certificate",
            ]):
                yield ("timeout_error", None, full_error)
            else:
                yield ("error", None, full_error)


def get_default_date() -> str:
    """获取默认分析日期 (今天或上一个交易日)"""
    return datetime.now().strftime("%Y-%m-%d")
