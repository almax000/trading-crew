# TradingCrew/graph/trading_graph.py

import os
from pathlib import Path
import json
from datetime import date
from typing import Dict, Any, Tuple, List, Optional

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

from langgraph.prebuilt import ToolNode

from tradingcrew.agents import *
from tradingcrew.default_config import DEFAULT_CONFIG
# ChromaDB memory disabled for concurrency performance
# from tradingcrew.agents.utils.memory import FinancialSituationMemory
from tradingcrew.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)
from tradingcrew.dataflows.config import set_config

# Import the new abstract tool methods from agent_utils
from tradingcrew.agents.utils.agent_utils import (
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_insider_sentiment,
    get_insider_transactions,
    get_global_news
)

from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor


class TradingCrewGraph:
    """Main class that orchestrates the trading agents framework."""

    def __init__(
        self,
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config: Dict[str, Any] = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
        """
        self.debug = debug
        self.config = config or DEFAULT_CONFIG

        # Update the interface's config
        set_config(self.config)

        # Create necessary directories
        os.makedirs(
            os.path.join(self.config["project_dir"], "dataflows/data_cache"),
            exist_ok=True,
        )

        # Initialize LLMs with streaming enabled
        # Set longer timeout (5 minutes) for cross-border network latency
        llm_timeout = self.config.get("llm_timeout", 300)

        if self.config["llm_provider"].lower() in ["openai", "ollama", "openrouter", "dashscope"]:
            self.deep_thinking_llm = ChatOpenAI(
                model=self.config["deep_think_llm"],
                base_url=self.config["backend_url"],
                streaming=True,
                request_timeout=llm_timeout,
            )
            self.quick_thinking_llm = ChatOpenAI(
                model=self.config["quick_think_llm"],
                base_url=self.config["backend_url"],
                streaming=True,
                request_timeout=llm_timeout,
            )
        elif self.config["llm_provider"].lower() == "anthropic":
            self.deep_thinking_llm = ChatAnthropic(
                model=self.config["deep_think_llm"],
                base_url=self.config["backend_url"],
                streaming=True,
                timeout=llm_timeout,
            )
            self.quick_thinking_llm = ChatAnthropic(
                model=self.config["quick_think_llm"],
                base_url=self.config["backend_url"],
                streaming=True,
                timeout=llm_timeout,
            )
        elif self.config["llm_provider"].lower() == "google":
            self.deep_thinking_llm = ChatGoogleGenerativeAI(
                model=self.config["deep_think_llm"],
                timeout=llm_timeout,
            )
            self.quick_thinking_llm = ChatGoogleGenerativeAI(
                model=self.config["quick_think_llm"],
                timeout=llm_timeout,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.config['llm_provider']}")
        
        # ChromaDB memory disabled for concurrency performance
        # Each session would create separate ChromaDB instances causing lock contention
        # self.bull_memory = FinancialSituationMemory("bull_memory", self.config)
        # self.bear_memory = FinancialSituationMemory("bear_memory", self.config)
        # self.trader_memory = FinancialSituationMemory("trader_memory", self.config)
        # self.invest_judge_memory = FinancialSituationMemory("invest_judge_memory", self.config)
        # self.risk_manager_memory = FinancialSituationMemory("risk_manager_memory", self.config)

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        self.conditional_logic = ConditionalLogic()
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            None,  # bull_memory disabled
            None,  # bear_memory disabled
            None,  # trader_memory disabled
            None,  # invest_judge_memory disabled
            None,  # risk_manager_memory disabled
            self.conditional_logic,
        )

        self.propagator = Propagator()
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Set up the graph
        self.graph = self.graph_setup.setup_graph(selected_analysts)

    def _create_tool_nodes(self) -> Dict[str, ToolNode]:
        """Create tool nodes for different data sources using abstract methods."""
        return {
            "market": ToolNode(
                [
                    # Core stock data tools
                    get_stock_data,
                    # Technical indicators
                    get_indicators,
                ]
            ),
            "social": ToolNode(
                [
                    # News tools for social media analysis
                    get_news,
                ]
            ),
            "news": ToolNode(
                [
                    # News and insider information
                    get_news,
                    get_global_news,
                    get_insider_sentiment,
                    get_insider_transactions,
                ]
            ),
            "fundamentals": ToolNode(
                [
                    # Fundamental analysis tools
                    get_fundamentals,
                    get_balance_sheet,
                    get_cashflow,
                    get_income_statement,
                ]
            ),
        }

    def propagate(self, company_name, trade_date):
        """Run the trading agents graph for a company on a specific date."""

        self.ticker = company_name

        # Initialize state
        init_agent_state = self.propagator.create_initial_state(
            company_name, trade_date
        )
        args = self.propagator.get_graph_args()

        if self.debug:
            # Debug mode with tracing
            trace = []
            for chunk in self.graph.stream(init_agent_state, **args):
                if len(chunk["messages"]) == 0:
                    pass
                else:
                    chunk["messages"][-1].pretty_print()
                    trace.append(chunk)

            final_state = trace[-1]
        else:
            # Standard mode without tracing
            final_state = self.graph.invoke(init_agent_state, **args)

        # Store current state for reflection
        self.curr_state = final_state

        # Log state
        self._log_state(trade_date, final_state)

        # Return decision and processed signal
        return final_state, self.process_signal(final_state["final_trade_decision"])

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "market_report": final_state["market_report"],
            "sentiment_report": final_state["sentiment_report"],
            "news_report": final_state["news_report"],
            "fundamentals_report": final_state["fundamentals_report"],
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"][
                    "current_response"
                ],
                "judge_decision": final_state["investment_debate_state"][
                    "judge_decision"
                ],
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "risky_history": final_state["risk_debate_state"]["risky_history"],
                "safe_history": final_state["risk_debate_state"]["safe_history"],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
        }

        # Save to file
        directory = Path(f"eval_results/{self.ticker}/TradingCrewStrategy_logs/")
        directory.mkdir(parents=True, exist_ok=True)

        with open(
            f"eval_results/{self.ticker}/TradingCrewStrategy_logs/full_states_log_{trade_date}.json",
            "w",
        ) as f:
            json.dump(self.log_states_dict, f, indent=4)

    def reflect_and_remember(self, returns_losses):
        """Reflect on decisions and update memory based on returns.

        Note: Memory is currently disabled for concurrency performance.
        This method is a no-op until memory is re-enabled.
        """
        # Memory disabled - skip reflection
        pass
        # self.reflector.reflect_bull_researcher(
        #     self.curr_state, returns_losses, self.bull_memory
        # )
        # self.reflector.reflect_bear_researcher(
        #     self.curr_state, returns_losses, self.bear_memory
        # )
        # self.reflector.reflect_trader(
        #     self.curr_state, returns_losses, self.trader_memory
        # )
        # self.reflector.reflect_invest_judge(
        #     self.curr_state, returns_losses, self.invest_judge_memory
        # )
        # self.reflector.reflect_risk_manager(
        #     self.curr_state, returns_losses, self.risk_manager_memory
        # )

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal)

    async def propagate_streaming(self, company_name, trade_date):
        """
        Run the trading agents graph with token-level streaming.

        Yields:
            (event_type, node_name, content) tuples:
            - ("node_start", node_name, None): Node started processing
            - ("token", node_name, token): Token from LLM response
            - ("node_end", node_name, full_content): Node finished, with full content
        """
        self.ticker = company_name

        # Initialize state
        init_agent_state = self.propagator.create_initial_state(
            company_name, trade_date
        )
        args = self.propagator.get_graph_args()
        # Remove stream_mode from args since we use a different mode for token streaming
        config = args.get("config", {})

        current_node = None
        accumulated_tokens = {}
        final_decision = "HOLD"

        # Use astream with messages mode for token-level streaming
        async for event in self.graph.astream(init_agent_state, stream_mode="messages", config=config):
            # event is a tuple: (message_chunk, metadata)
            if isinstance(event, tuple) and len(event) == 2:
                chunk, metadata = event

                # Get node name from metadata
                node_name = metadata.get("langgraph_node", "")

                # Track node transitions
                if node_name and node_name != current_node:
                    # If we had a previous node, emit node_end
                    if current_node and current_node in accumulated_tokens:
                        yield ("node_end", current_node, accumulated_tokens[current_node])

                        # If this was portfolio_manager, extract decision from content
                        if current_node == "portfolio_manager":
                            final_decision = self.process_signal(accumulated_tokens[current_node])

                    # Emit node_start for new node
                    current_node = node_name
                    if node_name not in accumulated_tokens:
                        accumulated_tokens[node_name] = ""
                        yield ("node_start", node_name, None)

                # Extract token content from chunk
                if hasattr(chunk, 'content') and chunk.content:
                    token = chunk.content
                    if current_node:
                        accumulated_tokens[current_node] += token
                        yield ("token", current_node, token)

        # Emit final node_end if needed
        if current_node and current_node in accumulated_tokens:
            yield ("node_end", current_node, accumulated_tokens[current_node])

            # If this was portfolio_manager, extract decision
            if current_node == "portfolio_manager":
                final_decision = self.process_signal(accumulated_tokens[current_node])

        yield ("complete", None, final_decision)
