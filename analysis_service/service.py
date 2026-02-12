"""
Analysis service wrapper

Wraps TradingCrewGraph and provides a streaming output interface.
"""

from typing import Dict, Any, List, Generator, AsyncGenerator
from datetime import datetime
import traceback
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Agent display name mapping
AGENT_DISPLAY_NAMES = {
    "Market Analyst": "Market Analyst",
    "Social Analyst": "Social Analyst",
    "News Analyst": "News Analyst",
    "Fundamentals Analyst": "Fundamentals Analyst",
    "Bull Researcher": "Bull Researcher",
    "Bear Researcher": "Bear Researcher",
    "Research Manager": "Research Manager",
    "Trader": "Trader",
    "Risky Analyst": "Risky Analyst",
    "Safe Analyst": "Safe Analyst",
    "Neutral Analyst": "Neutral Analyst",
    "Risk Manager": "Risk Manager",
    "Portfolio Manager": "Portfolio Manager",
}


class AnalysisService:
    """
    Analysis service

    Wraps TradingCrewGraph and provides streaming analysis capabilities.
    Prefers Alibaba Cloud DashScope API (if DASHSCOPE_API_KEY is configured).
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize analysis service

        Args:
            config: TradingCrew config, can override defaults
        """
        from dotenv import load_dotenv

        # Load .env file first
        load_dotenv()

        self.custom_config = config

        # Detect available APIs
        self.has_dashscope = bool(os.environ.get("DASHSCOPE_API_KEY"))
        self.has_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))

        # Lazy initialization
        self._graph = None
        self._current_market = None

    def _get_config(self, market: str, model: str = None) -> Dict[str, Any]:
        """
        Get config for specified market and model

        Args:
            market: Market type ("A-share", "US", "HK")
            model: Model name ("deepseek-v3", "qwen3-max", "gpt-4o", "claude-sonnet-4", etc.)
        """
        # Default to deepseek-v3
        if not model:
            model = "deepseek-v3"

        from tradingcrew.market_config import MODEL_PRESETS

        # Select config based on model preset provider
        preset = MODEL_PRESETS.get(model)
        if preset and preset["provider"] == "dashscope":
            from tradingcrew.market_config import get_dashscope_config
            config = get_dashscope_config(market=market, model=model)
        elif preset and preset["provider"] == "openrouter":
            from tradingcrew.market_config import get_openrouter_config
            config = get_openrouter_config(market=market, model=model)
        else:
            # Unknown model, use default
            from tradingcrew.market_config import get_dashscope_config
            config = get_dashscope_config(market=market, model="deepseek-v3")

        # Apply custom config
        if self.custom_config:
            config.update(self.custom_config)

        return config

    def _create_graph(self, market: str, selected_analysts: List[str] = None, model: str = None):
        """
        Create a new TradingCrewGraph instance

        Creates a new instance for each analysis to avoid ChromaDB collection conflicts during concurrency.

        Args:
            market: Market type (A-share, US, HK)
            selected_analysts: List of enabled analysts
            model: Model name ("deepseek-v3", "qwen3-max")
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
        Stream stock analysis

        Args:
            ticker: Stock ticker
            date: Analysis date (YYYY-MM-DD)
            market: Market type (A-share, US, HK)
            selected_analysts: List of enabled analysts
            model: Model name ("deepseek-v3", "qwen3-max")

        Yields:
            (agent_name, content) - Agent name and output content
            The last yield is ("__FINAL__", decision) for the final decision
        """
        try:
            # Create new graph instance per analysis to avoid concurrency conflicts
            graph = self._create_graph(market, selected_analysts, model)

            # Create initial state
            init_state = graph.propagator.create_initial_state(ticker, date)
            args = graph.propagator.get_graph_args()

            # Track processed reports
            processed_reports = set()
            final_state = None

            # Streaming execution
            for chunk in graph.graph.stream(init_state, **args):
                final_state = chunk

                # Extract agent updates and yield
                updates = self._extract_agent_updates(chunk, processed_reports)
                for agent_name, content in updates:
                    yield (agent_name, content)

            # Store current state
            graph.curr_state = final_state
            graph.ticker = ticker

            # Process signal to get decision
            decision = graph.process_signal(
                final_state.get("final_trade_decision", "HOLD") if final_state else "HOLD"
            )

            # Return final decision
            yield ("__FINAL__", decision)

        except Exception as e:
            error_msg = str(e).lower()
            full_error = f"Analysis error: {str(e)}\n{traceback.format_exc()}"

            # Check for API quota exhaustion
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

            # Check for timeout/network issues
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
        Extract agent updates from a streaming chunk

        Args:
            chunk: LangGraph streaming chunk
            processed: Set of processed reports (for deduplication)

        Returns:
            [(agent_name, content), ...] list
        """
        updates = []

        # Report field to agent name mapping
        report_mappings = {
            "market_report": "Market Analyst",
            "sentiment_report": "Social Analyst",
            "news_report": "News Analyst",
            "fundamentals_report": "Fundamentals Analyst",
            "investment_plan": "Research Manager",
            "trader_investment_plan": "Trader",
            "final_trade_decision": "Portfolio Manager",
        }

        # Check report fields
        for field, agent_name in report_mappings.items():
            if field in chunk and chunk[field] and field not in processed:
                content = chunk[field]
                if content.strip():
                    updates.append((agent_name, content))
                    processed.add(field)

        # Check investment debate state
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

        # Check risk debate state
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
        Extract the latest statement from debate history

        Args:
            history: Full debate history
            speaker_prefix: Speaker prefix (e.g. "Bull", "Bear")

        Returns:
            Latest statement content
        """
        if not history:
            return ""

        # Split by speaker
        statements = history.split(f"{speaker_prefix}")
        if len(statements) > 1:
            # Get the last statement
            last = statements[-1]
            # Clean prefix
            if last.startswith(" Analyst:") or last.startswith(" Researcher:"):
                last = last.split(":", 1)[-1].strip()
            return last.strip()

        return ""

    def get_agent_display_name(self, agent_name: str) -> str:
        """Get the display name for an agent"""
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
            ticker: Stock ticker
            date: Analysis date (YYYY-MM-DD)
            market: Market type (A-share, US, HK)
            selected_analysts: List of enabled analysts
            model: Model name ("deepseek-v3", "qwen3-max")

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
            full_error = f"Analysis error: {str(e)}\n{traceback.format_exc()}"

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
    """Get default analysis date (today or last trading day)"""
    return datetime.now().strftime("%Y-%m-%d")
