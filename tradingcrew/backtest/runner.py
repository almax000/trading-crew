"""
Multi-market Backtest Runner

Executes multi-day trading decisions in batch and calculates returns.
Supports A-share, US, and HK stock backtesting.
"""

from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
import pandas as pd
import time
import json
import os

# A-share data source
try:
    import akshare as ak
except ImportError:
    ak = None

# International market data source
try:
    import yfinance as yf
except ImportError:
    yf = None

from .multi_market_calendar import get_trading_days_in_range, get_next_trading_day
from .metrics import calculate_metrics, BacktestMetrics


@dataclass
class TradeRecord:
    """Single trade record"""
    date: str
    symbol: str
    decision: str  # BUY, SELL, HOLD
    price_at_decision: float
    price_next_day: float
    return_pct: float
    full_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary (excluding full_state)"""
        return {
            "date": self.date,
            "symbol": self.symbol,
            "decision": self.decision,
            "price_at_decision": self.price_at_decision,
            "price_next_day": self.price_next_day,
            "return_pct": self.return_pct,
        }


@dataclass
class BacktestResult:
    """Backtest result"""
    symbol: str
    start_date: str
    end_date: str
    trades: List[TradeRecord]
    metrics: BacktestMetrics
    total_trading_days: int

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to DataFrame"""
        records = [t.to_dict() for t in self.trades]
        return pd.DataFrame(records)

    def save_to_csv(self, filepath: str):
        """Save trade records to CSV"""
        df = self.to_dataframe()
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        print(f"Trade records saved to: {filepath}")

    def save_to_json(self, filepath: str):
        """Save full results to JSON"""
        result = {
            "symbol": self.symbol,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_trading_days": self.total_trading_days,
            "metrics": self.metrics.to_dict(),
            "trades": [t.to_dict() for t in self.trades],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Backtest results saved to: {filepath}")


class BacktestRunner:
    """
    Multi-market Backtest Runner

    Iterates through each trading day to execute decisions and calculate returns.
    Supports A-share, US, and HK markets.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        selected_analysts: List[str] = None,
        enable_reflection: bool = True,
        api_call_delay: float = 1.0,
        debug: bool = False,
        save_states: bool = False,
    ):
        """
        Initialize backtest runner

        Args:
            config: TradingCrew configuration (should include "market" field)
            selected_analysts: Enabled analyst list (default all)
            enable_reflection: Whether to enable reflection mechanism
            api_call_delay: API call interval (seconds) to avoid rate limits
            debug: Debug mode
            save_states: Whether to save full state to TradeRecord
        """
        self.config = config
        self.market = config.get("market", "A-share")  # Default A-share
        self.selected_analysts = selected_analysts or ["market", "social", "news", "fundamentals"]
        self.enable_reflection = enable_reflection
        self.api_call_delay = api_call_delay
        self.debug = debug
        self.save_states = save_states

        # Lazy-initialize TradingCrewGraph
        self._graph = None

        # Price data cache
        self._price_cache: Dict[str, pd.DataFrame] = {}

    def _get_graph(self):
        """Lazy-initialize graph"""
        if self._graph is None:
            from tradingcrew.graph.trading_graph import TradingCrewGraph

            self._graph = TradingCrewGraph(
                selected_analysts=self.selected_analysts,
                debug=self.debug,
                config=self.config,
            )
        return self._graph

    def _get_price_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Get price data (with caching)

        Uses different data sources based on market type:
        - A-share: akshare
        - US/HK: yfinance
        """
        cache_key = f"{self.market}_{symbol}_{start_date}_{end_date}"

        if cache_key not in self._price_cache:
            if self.market == "A-share":
                df = self._get_ashare_price(symbol, start_date, end_date)
            else:
                df = self._get_yfinance_price(symbol, start_date, end_date)

            self._price_cache[cache_key] = df

        return self._price_cache[cache_key]

    def _get_ashare_price(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Get A-share price data (akshare)"""
        if ak is None:
            print("Error: akshare not installed for A-share data")
            return pd.DataFrame()

        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="qfq"
            )
            if not df.empty:
                df["\u65e5\u671f"] = pd.to_datetime(df["\u65e5\u671f"])
                df = df.set_index("\u65e5\u671f")
                # Standardize column names
                df = df.rename(columns={"\u6536\u76d8": "Close", "\u5f00\u76d8": "Open", "\u6700\u9ad8": "High", "\u6700\u4f4e": "Low"})
            return df
        except Exception as e:
            print(f"Failed to fetch A-share price data: {e}")
            return pd.DataFrame()

    def _get_yfinance_price(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Get US/HK stock price data (yfinance)"""
        if yf is None:
            print("Error: yfinance not installed for US/HK stock data")
            return pd.DataFrame()

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)
            if not df.empty:
                # yfinance DataFrame already has date index
                # Columns: Open, High, Low, Close, Volume, Dividends, Stock Splits
                pass
            return df
        except Exception as e:
            print(f"Failed to fetch {symbol} price data: {e}")
            return pd.DataFrame()

    def _get_close_price(self, symbol: str, date: str, price_df: pd.DataFrame) -> float:
        """Get closing price for the specified date"""
        try:
            date_dt = pd.to_datetime(date)
            # Remove timezone info for comparison
            if price_df.index.tz is not None:
                date_dt = date_dt.tz_localize(price_df.index.tz)

            if date_dt in price_df.index:
                return float(price_df.loc[date_dt, "Close"])
            # Try to find nearest trading day
            mask = price_df.index <= date_dt
            if mask.any():
                return float(price_df[mask].iloc[-1]["Close"])
        except Exception as e:
            if self.debug:
                print(f"Failed to get closing price for {date}: {e}")
        return 0.0

    def _calculate_single_return(
        self,
        decision: str,
        price_at_decision: float,
        price_next_day: float
    ) -> float:
        """
        Calculate single trade return

        Rules:
        - BUY: Profit if next day price rises
        - SELL: Profit if next day price falls (short logic)
        - HOLD: Zero return
        """
        if price_at_decision == 0:
            return 0.0

        price_change_pct = (price_next_day - price_at_decision) / price_at_decision * 100

        if decision == "BUY":
            return price_change_pct
        elif decision == "SELL":
            return -price_change_pct  # Short: profit when price drops
        else:  # HOLD
            return 0.0

    def _normalize_decision(self, decision: str) -> str:
        """Normalize decision string"""
        decision = decision.upper().strip()
        if "BUY" in decision:
            return "BUY"
        elif "SELL" in decision:
            return "SELL"
        else:
            return "HOLD"

    def _run_with_streaming(
        self,
        graph,
        symbol: str,
        trade_date: str,
        callback: Callable[[str, str, str, str], None],
    ):
        """
        Execute single-day analysis with streaming output

        Args:
            graph: TradingCrewGraph instance
            symbol: Stock code
            trade_date: Trading date
            callback: Streaming callback (symbol, date, agent_name, content)

        Returns:
            (final_state, decision) tuple
        """
        # Create initial state
        init_state = graph.propagator.create_initial_state(symbol, trade_date)
        args = graph.propagator.get_graph_args()

        # Track processed reports
        processed_reports = set()
        final_state = None

        # Stream execution
        for chunk in graph.graph.stream(init_state, **args):
            final_state = chunk

            # Extract agent updates and callback
            updates = self._extract_agent_updates(chunk, processed_reports)
            for agent_name, content in updates:
                callback(symbol, trade_date, agent_name, content)

        # Store current state for reflection
        graph.curr_state = final_state
        graph.ticker = symbol

        # Log state
        if hasattr(graph, '_log_state'):
            graph._log_state(trade_date, final_state)

        # Process signal to get decision
        decision = graph.process_signal(final_state.get("final_trade_decision", "HOLD"))

        return final_state, decision

    def _extract_agent_updates(
        self,
        chunk: Dict[str, Any],
        processed: set,
    ) -> List[tuple]:
        """
        Extract agent updates from streaming chunk

        Args:
            chunk: LangGraph streaming chunk
            processed: Set of processed reports (for dedup)

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
                    # Extract latest statement
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
                        latest = self._get_latest_statement(risk[analyst_key], analyst_key.split("_")[0].title())
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
        Extract the latest statement from history

        Args:
            history: Full history record
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

    def run(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        progress_callback: Callable[[int, int, str], None] = None,
        stream_callback: Callable[[str, str, str, str], None] = None,
    ) -> BacktestResult:
        """
        Execute backtest for a single stock

        Args:
            symbol: Stock code (e.g. "600519")
            start_date: Start date yyyy-mm-dd
            end_date: End date yyyy-mm-dd
            progress_callback: Progress callback (current, total, date)
            stream_callback: Streaming callback (symbol, date, agent_name, content)
                for real-time agent output display

        Returns:
            BacktestResult
        """
        # Get trading day list (by market)
        trading_days = get_trading_days_in_range(start_date, end_date, market=self.market)
        total_days = len(trading_days)

        market_name = {"A-share": "A-Share", "US": "US Stock", "HK": "HK Stock"}.get(self.market, self.market)

        print(f"\n{'='*60}")
        print(f"Starting backtest for {symbol} ({market_name})")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Trading days: {total_days}")
        print(f"{'='*60}\n")

        if total_days == 0:
            print("Warning: No trading days in the specified range")
            return BacktestResult(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                trades=[],
                metrics=BacktestMetrics(),
                total_trading_days=0,
            )

        # Preload price data (extend date range to get next day price)
        extended_end = pd.to_datetime(end_date) + pd.Timedelta(days=30)
        price_df = self._get_price_data(
            symbol,
            start_date,
            extended_end.strftime("%Y-%m-%d")
        )

        if price_df.empty:
            print(f"Warning: Unable to fetch price data for {symbol}")
            return BacktestResult(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                trades=[],
                metrics=BacktestMetrics(),
                total_trading_days=0,
            )

        # Get graph instance
        graph = self._get_graph()

        trades: List[TradeRecord] = []

        for idx, trade_date in enumerate(trading_days):
            try:
                print(f"[{idx+1}/{total_days}] {trade_date}", end=" ")

                if progress_callback:
                    progress_callback(idx + 1, total_days, trade_date)

                # Execute single-day decision
                if stream_callback:
                    # Streaming execution with real-time agent output callback
                    final_state, decision = self._run_with_streaming(
                        graph, symbol, trade_date, stream_callback
                    )
                else:
                    # Standard execution
                    final_state, decision = graph.propagate(symbol, trade_date)

                # Normalize decision
                decision = self._normalize_decision(decision)

                # Get prices
                price_at_decision = self._get_close_price(symbol, trade_date, price_df)
                next_day = get_next_trading_day(trade_date, market=self.market)
                price_next_day = self._get_close_price(symbol, next_day, price_df)

                # Calculate return
                return_pct = self._calculate_single_return(
                    decision, price_at_decision, price_next_day
                )

                # Record trade
                trade = TradeRecord(
                    date=trade_date,
                    symbol=symbol,
                    decision=decision,
                    price_at_decision=price_at_decision,
                    price_next_day=price_next_day,
                    return_pct=return_pct,
                    full_state=final_state if self.save_states else {},
                )
                trades.append(trade)

                # Print result
                print(f"| {decision:4s} | {price_at_decision:.2f} -> {price_next_day:.2f} | {return_pct:+.2f}%")

                # Reflection mechanism (after each trade)
                if self.enable_reflection and return_pct != 0:
                    try:
                        graph.reflect_and_remember(return_pct)
                    except Exception as e:
                        if self.debug:
                            print(f"  Reflection failed: {e}")

                # API call delay
                if self.api_call_delay > 0:
                    time.sleep(self.api_call_delay)

            except Exception as e:
                print(f"| Error: {e}")
                continue

        # Calculate evaluation metrics
        metrics = calculate_metrics(trades)

        result = BacktestResult(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            trades=trades,
            metrics=metrics,
            total_trading_days=total_days,
        )

        # Print summary
        print(f"\n{'='*60}")
        print(f"Backtest complete: {symbol}")
        print(f"Cumulative return: {metrics.cumulative_return:.2f}%")
        print(f"Win rate: {metrics.win_rate:.2f}%")
        print(f"Max drawdown: {metrics.max_drawdown:.2f}%")
        print(f"{'='*60}\n")

        return result

    def run_multiple(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        output_dir: str = None,
    ) -> Dict[str, BacktestResult]:
        """
        Batch backtest multiple stocks

        Args:
            symbols: List of stock codes
            start_date: Start date
            end_date: End date
            output_dir: Output directory (optional)

        Returns:
            Mapping of stock codes to backtest results
        """
        results = {}

        print(f"\n{'#'*60}")
        print(f"Batch backtest: {len(symbols)} stocks")
        print(f"Date range: {start_date} to {end_date}")
        print(f"{'#'*60}\n")

        for idx, symbol in enumerate(symbols):
            print(f"\n[{idx+1}/{len(symbols)}] Starting backtest for {symbol}")
            print("-" * 40)

            try:
                result = self.run(symbol, start_date, end_date)
                results[symbol] = result

                # Save individual result
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                    result.save_to_csv(os.path.join(output_dir, f"{symbol}_trades.csv"))

            except Exception as e:
                print(f"Backtest failed for {symbol}: {e}")
                continue

        # Print summary
        print(f"\n{'#'*60}")
        print("Batch Backtest Summary")
        print(f"{'#'*60}")
        print(f"{'Symbol':<10} {'Cum. Return':>12} {'Win Rate':>10} {'Max DD':>10}")
        print("-" * 44)

        for symbol, res in results.items():
            m = res.metrics
            print(f"{symbol:<10} {m.cumulative_return:>+11.2f}% {m.win_rate:>9.1f}% {m.max_drawdown:>9.2f}%")

        # Calculate portfolio statistics
        if results:
            avg_return = sum(r.metrics.cumulative_return for r in results.values()) / len(results)
            avg_win_rate = sum(r.metrics.win_rate for r in results.values()) / len(results)
            print("-" * 44)
            print(f"{'Average':<10} {avg_return:>+11.2f}% {avg_win_rate:>9.1f}%")

        return results
