"""
多市场回测执行器

批量执行多日交易决策并计算收益。
支持 A股、美股、港股回测。
"""

from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
import pandas as pd
import time
import json
import os

# A股数据源
try:
    import akshare as ak
except ImportError:
    ak = None

# 国际市场数据源
try:
    import yfinance as yf
except ImportError:
    yf = None

from .multi_market_calendar import get_trading_days_in_range, get_next_trading_day
from .metrics import calculate_metrics, BacktestMetrics


@dataclass
class TradeRecord:
    """单次交易记录"""
    date: str
    symbol: str
    decision: str  # BUY, SELL, HOLD
    price_at_decision: float
    price_next_day: float
    return_pct: float
    full_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典 (不包含 full_state)"""
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
    """回测结果"""
    symbol: str
    start_date: str
    end_date: str
    trades: List[TradeRecord]
    metrics: BacktestMetrics
    total_trading_days: int

    def to_dataframe(self) -> pd.DataFrame:
        """转换为 DataFrame"""
        records = [t.to_dict() for t in self.trades]
        return pd.DataFrame(records)

    def save_to_csv(self, filepath: str):
        """保存交易记录到 CSV"""
        df = self.to_dataframe()
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        print(f"交易记录已保存到: {filepath}")

    def save_to_json(self, filepath: str):
        """保存完整结果到 JSON"""
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
        print(f"回测结果已保存到: {filepath}")


class BacktestRunner:
    """
    多市场回测执行器

    循环执行每个交易日的决策，并计算收益。
    支持 A股、美股、港股市场。
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
        初始化回测执行器

        Args:
            config: TradingCrew 配置 (应包含 "market" 字段)
            selected_analysts: 启用的分析师列表 (默认全部)
            enable_reflection: 是否启用反思机制
            api_call_delay: API调用间隔(秒)，避免频率限制
            debug: 调试模式
            save_states: 是否保存完整状态到 TradeRecord
        """
        self.config = config
        self.market = config.get("market", "A-share")  # 默认 A股
        self.selected_analysts = selected_analysts or ["market", "social", "news", "fundamentals"]
        self.enable_reflection = enable_reflection
        self.api_call_delay = api_call_delay
        self.debug = debug
        self.save_states = save_states

        # 延迟初始化 TradingCrewGraph
        self._graph = None

        # 价格数据缓存
        self._price_cache: Dict[str, pd.DataFrame] = {}

    def _get_graph(self):
        """延迟初始化图"""
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
        获取价格数据 (带缓存)

        根据市场类型使用不同的数据源：
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
        """获取 A 股价格数据 (akshare)"""
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
                df["日期"] = pd.to_datetime(df["日期"])
                df = df.set_index("日期")
                # 标准化列名
                df = df.rename(columns={"收盘": "Close", "开盘": "Open", "最高": "High", "最低": "Low"})
            return df
        except Exception as e:
            print(f"获取 A 股价格数据失败: {e}")
            return pd.DataFrame()

    def _get_yfinance_price(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取美股/港股价格数据 (yfinance)"""
        if yf is None:
            print("Error: yfinance not installed for US/HK stock data")
            return pd.DataFrame()

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)
            if not df.empty:
                # yfinance 返回的 DataFrame 已经是日期索引
                # 列名: Open, High, Low, Close, Volume, Dividends, Stock Splits
                pass
            return df
        except Exception as e:
            print(f"获取 {symbol} 价格数据失败: {e}")
            return pd.DataFrame()

    def _get_close_price(self, symbol: str, date: str, price_df: pd.DataFrame) -> float:
        """获取指定日期的收盘价"""
        try:
            date_dt = pd.to_datetime(date)
            # 移除时区信息进行比较
            if price_df.index.tz is not None:
                date_dt = date_dt.tz_localize(price_df.index.tz)

            if date_dt in price_df.index:
                return float(price_df.loc[date_dt, "Close"])
            # 尝试找最近的交易日
            mask = price_df.index <= date_dt
            if mask.any():
                return float(price_df[mask].iloc[-1]["Close"])
        except Exception as e:
            if self.debug:
                print(f"获取 {date} 收盘价失败: {e}")
        return 0.0

    def _calculate_single_return(
        self,
        decision: str,
        price_at_decision: float,
        price_next_day: float
    ) -> float:
        """
        计算单次交易收益率

        规则:
        - BUY: 如果下一日价格上涨则盈利
        - SELL: 如果下一日价格下跌则盈利 (做空逻辑)
        - HOLD: 收益为0
        """
        if price_at_decision == 0:
            return 0.0

        price_change_pct = (price_next_day - price_at_decision) / price_at_decision * 100

        if decision == "BUY":
            return price_change_pct
        elif decision == "SELL":
            return -price_change_pct  # 做空: 价格跌则盈利
        else:  # HOLD
            return 0.0

    def _normalize_decision(self, decision: str) -> str:
        """标准化决策字符串"""
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
        使用流式输出执行单日分析

        Args:
            graph: TradingCrewGraph 实例
            symbol: 股票代码
            trade_date: 交易日期
            callback: 流式回调 (symbol, date, agent_name, content)

        Returns:
            (final_state, decision) 元组
        """
        # 创建初始状态
        init_state = graph.propagator.create_initial_state(symbol, trade_date)
        args = graph.propagator.get_graph_args()

        # 跟踪已处理的报告
        processed_reports = set()
        final_state = None

        # 流式执行
        for chunk in graph.graph.stream(init_state, **args):
            final_state = chunk

            # 提取 Agent 更新并回调
            updates = self._extract_agent_updates(chunk, processed_reports)
            for agent_name, content in updates:
                callback(symbol, trade_date, agent_name, content)

        # 存储当前状态用于反思
        graph.curr_state = final_state
        graph.ticker = symbol

        # 记录日志
        if hasattr(graph, '_log_state'):
            graph._log_state(trade_date, final_state)

        # 处理信号获取决策
        decision = graph.process_signal(final_state.get("final_trade_decision", "HOLD"))

        return final_state, decision

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
                    # 提取最新发言
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

    def run(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        progress_callback: Callable[[int, int, str], None] = None,
        stream_callback: Callable[[str, str, str, str], None] = None,
    ) -> BacktestResult:
        """
        执行单只股票的回测

        Args:
            symbol: 股票代码 (如 "600519")
            start_date: 开始日期 yyyy-mm-dd
            end_date: 结束日期 yyyy-mm-dd
            progress_callback: 进度回调函数 (current, total, date)
            stream_callback: 流式回调函数 (symbol, date, agent_name, content)
                用于实时显示 Agent 输出

        Returns:
            BacktestResult 回测结果
        """
        # 获取交易日列表 (根据市场)
        trading_days = get_trading_days_in_range(start_date, end_date, market=self.market)
        total_days = len(trading_days)

        market_name = {"A-share": "A股", "US": "美股", "HK": "港股"}.get(self.market, self.market)

        print(f"\n{'='*60}")
        print(f"开始回测 {symbol} ({market_name})")
        print(f"日期范围: {start_date} 到 {end_date}")
        print(f"交易日数: {total_days}")
        print(f"{'='*60}\n")

        if total_days == 0:
            print("警告: 指定范围内没有交易日")
            return BacktestResult(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                trades=[],
                metrics=BacktestMetrics(),
                total_trading_days=0,
            )

        # 预加载价格数据 (扩展日期范围以获取下一日价格)
        extended_end = pd.to_datetime(end_date) + pd.Timedelta(days=30)
        price_df = self._get_price_data(
            symbol,
            start_date,
            extended_end.strftime("%Y-%m-%d")
        )

        if price_df.empty:
            print(f"警告: 无法获取 {symbol} 的价格数据")
            return BacktestResult(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                trades=[],
                metrics=BacktestMetrics(),
                total_trading_days=0,
            )

        # 获取图实例
        graph = self._get_graph()

        trades: List[TradeRecord] = []

        for idx, trade_date in enumerate(trading_days):
            try:
                print(f"[{idx+1}/{total_days}] {trade_date}", end=" ")

                if progress_callback:
                    progress_callback(idx + 1, total_days, trade_date)

                # 执行单日决策
                if stream_callback:
                    # 流式执行，实时回调 Agent 输出
                    final_state, decision = self._run_with_streaming(
                        graph, symbol, trade_date, stream_callback
                    )
                else:
                    # 标准执行
                    final_state, decision = graph.propagate(symbol, trade_date)

                # 标准化决策
                decision = self._normalize_decision(decision)

                # 获取价格
                price_at_decision = self._get_close_price(symbol, trade_date, price_df)
                next_day = get_next_trading_day(trade_date, market=self.market)
                price_next_day = self._get_close_price(symbol, next_day, price_df)

                # 计算收益
                return_pct = self._calculate_single_return(
                    decision, price_at_decision, price_next_day
                )

                # 记录交易
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

                # 打印结果
                emoji = "📈" if return_pct > 0 else ("📉" if return_pct < 0 else "➖")
                print(f"| {decision:4s} | {price_at_decision:.2f} -> {price_next_day:.2f} | {return_pct:+.2f}% {emoji}")

                # 反思机制 (每笔交易后)
                if self.enable_reflection and return_pct != 0:
                    try:
                        graph.reflect_and_remember(return_pct)
                    except Exception as e:
                        if self.debug:
                            print(f"  反思失败: {e}")

                # API调用延迟
                if self.api_call_delay > 0:
                    time.sleep(self.api_call_delay)

            except Exception as e:
                print(f"| 错误: {e}")
                continue

        # 计算评估指标
        metrics = calculate_metrics(trades)

        result = BacktestResult(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            trades=trades,
            metrics=metrics,
            total_trading_days=total_days,
        )

        # 打印汇总
        print(f"\n{'='*60}")
        print(f"回测完成: {symbol}")
        print(f"累计收益: {metrics.cumulative_return:.2f}%")
        print(f"胜率: {metrics.win_rate:.2f}%")
        print(f"最大回撤: {metrics.max_drawdown:.2f}%")
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
        批量回测多只股票

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            output_dir: 输出目录 (可选)

        Returns:
            股票代码到回测结果的映射
        """
        results = {}

        print(f"\n{'#'*60}")
        print(f"批量回测: {len(symbols)} 只股票")
        print(f"日期范围: {start_date} 到 {end_date}")
        print(f"{'#'*60}\n")

        for idx, symbol in enumerate(symbols):
            print(f"\n[{idx+1}/{len(symbols)}] 开始回测 {symbol}")
            print("-" * 40)

            try:
                result = self.run(symbol, start_date, end_date)
                results[symbol] = result

                # 保存单个结果
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                    result.save_to_csv(os.path.join(output_dir, f"{symbol}_trades.csv"))

            except Exception as e:
                print(f"回测 {symbol} 失败: {e}")
                continue

        # 打印汇总
        print(f"\n{'#'*60}")
        print("批量回测汇总")
        print(f"{'#'*60}")
        print(f"{'股票代码':<10} {'累计收益':>10} {'胜率':>8} {'最大回撤':>10}")
        print("-" * 40)

        for symbol, res in results.items():
            m = res.metrics
            print(f"{symbol:<10} {m.cumulative_return:>+10.2f}% {m.win_rate:>7.1f}% {m.max_drawdown:>10.2f}%")

        # 计算组合统计
        if results:
            avg_return = sum(r.metrics.cumulative_return for r in results.values()) / len(results)
            avg_win_rate = sum(r.metrics.win_rate for r in results.values()) / len(results)
            print("-" * 40)
            print(f"{'平均':<10} {avg_return:>+10.2f}% {avg_win_rate:>7.1f}%")

        return results
