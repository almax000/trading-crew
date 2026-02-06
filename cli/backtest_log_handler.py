"""
TradingCrew A股回测文件日志处理器

同步保存 Agent 对话和回测结果到文件
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import asdict

from cli.backtest_display import AGENT_NAMES_CN


class BacktestLogHandler:
    """
    回测日志处理器

    目录结构:
    results/backtest_YYYYMMDD_HHMMSS/
        session.log              # 完整会话日志
        600519/
            2024-01-15/
                conversation.md  # Agent 对话 (Markdown)
                decision.json    # 决策和状态
                reports/
                    market_report.md
                    sentiment_report.md
                    news_report.md
                    fundamentals_report.md
                    investment_plan.md
                    trader_plan.md
                    final_decision.md
            summary.json         # 该股票汇总
        summary.json             # 整体汇总
        metrics.csv              # 所有股票指标
    """

    def __init__(self, output_dir: str = "results"):
        self.base_dir = Path(output_dir)
        self.session_dir: Optional[Path] = None
        self.session_log: Optional[Path] = None
        self.current_stock: Optional[str] = None
        self.current_date: Optional[str] = None

    def setup_session(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
    ) -> Path:
        """
        初始化会话目录

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            会话目录路径
        """
        # 创建会话目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.base_dir / f"backtest_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # 创建会话日志
        self.session_log = self.session_dir / "session.log"

        # 写入会话信息
        self._write_session_header(symbols, start_date, end_date)

        # 为每只股票创建目录
        for symbol in symbols:
            (self.session_dir / symbol).mkdir(exist_ok=True)

        return self.session_dir

    def _write_session_header(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
    ):
        """写入会话头信息"""
        header = f"""
{'='*60}
TradingCrew A股回测会话
{'='*60}
开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
股票列表: {', '.join(symbols)}
日期范围: {start_date} 至 {end_date}
{'='*60}

"""
        with open(self.session_log, "w", encoding="utf-8") as f:
            f.write(header)

    def start_stock(self, symbol: str):
        """开始处理新股票"""
        self.current_stock = symbol
        self._log(f"\n{'='*40}\n开始分析: {symbol}\n{'='*40}\n")

    def start_day(self, date: str):
        """开始处理新交易日"""
        self.current_date = date

        # 创建日期目录
        day_dir = self.session_dir / self.current_stock / date
        day_dir.mkdir(parents=True, exist_ok=True)

        # 创建 reports 子目录
        (day_dir / "reports").mkdir(exist_ok=True)

        # 初始化对话文件
        conversation_file = day_dir / "conversation.md"
        with open(conversation_file, "w", encoding="utf-8") as f:
            f.write(f"# {self.current_stock} - {date} Agent 对话记录\n\n")

        self._log(f"\n--- {date} ---\n")

    def log_agent_message(
        self,
        agent_name: str,
        content: str,
        msg_type: str = "report",
    ):
        """
        记录 Agent 消息

        Args:
            agent_name: Agent 英文名称
            content: 消息内容
            msg_type: 消息类型 (report, debate, decision)
        """
        if not self.current_stock or not self.current_date:
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        agent_cn = AGENT_NAMES_CN.get(agent_name, agent_name)

        # 写入会话日志
        log_line = f"[{timestamp}] [{agent_cn}] {content[:100]}...\n"
        self._log(log_line)

        # 写入对话文件
        day_dir = self.session_dir / self.current_stock / self.current_date
        conversation_file = day_dir / "conversation.md"

        with open(conversation_file, "a", encoding="utf-8") as f:
            f.write(f"## [{timestamp}] {agent_cn}\n\n")
            f.write(f"{content}\n\n")
            f.write("---\n\n")

    def save_report(self, report_name: str, content: str):
        """
        保存单独的报告文件

        Args:
            report_name: 报告名称 (如 market_report, sentiment_report)
            content: 报告内容
        """
        if not self.current_stock or not self.current_date:
            return

        # 报告文件名映射
        file_names = {
            "market_report": "market_report.md",
            "sentiment_report": "sentiment_report.md",
            "news_report": "news_report.md",
            "fundamentals_report": "fundamentals_report.md",
            "investment_plan": "investment_plan.md",
            "trader_investment_plan": "trader_plan.md",
            "final_trade_decision": "final_decision.md",
        }

        file_name = file_names.get(report_name, f"{report_name}.md")
        day_dir = self.session_dir / self.current_stock / self.current_date
        report_file = day_dir / "reports" / file_name

        # 报告标题映射
        titles = {
            "market_report": "市场分析报告",
            "sentiment_report": "舆情分析报告",
            "news_report": "新闻分析报告",
            "fundamentals_report": "基本面分析报告",
            "investment_plan": "研究团队投资计划",
            "trader_investment_plan": "交易员投资计划",
            "final_trade_decision": "最终交易决策",
        }

        title = titles.get(report_name, report_name)

        with open(report_file, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(f"**股票**: {self.current_stock}\n")
            f.write(f"**日期**: {self.current_date}\n")
            f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            f.write(content)

    def save_daily_state(self, state: Dict[str, Any], decision: str):
        """
        保存每日完整状态

        Args:
            state: LangGraph 最终状态
            decision: 最终决策 (BUY/SELL/HOLD)
        """
        if not self.current_stock or not self.current_date:
            return

        day_dir = self.session_dir / self.current_stock / self.current_date
        decision_file = day_dir / "decision.json"

        # 提取关键信息
        data = {
            "symbol": self.current_stock,
            "date": self.current_date,
            "decision": decision,
            "timestamp": datetime.now().isoformat(),
            "reports": {
                "market_report": state.get("market_report", ""),
                "sentiment_report": state.get("sentiment_report", ""),
                "news_report": state.get("news_report", ""),
                "fundamentals_report": state.get("fundamentals_report", ""),
            },
            "investment_plan": state.get("investment_plan", ""),
            "trader_investment_plan": state.get("trader_investment_plan", ""),
            "final_trade_decision": state.get("final_trade_decision", ""),
        }

        # 处理辩论状态
        if "investment_debate_state" in state:
            debate = state["investment_debate_state"]
            data["investment_debate"] = {
                "bull_history": debate.get("bull_history", ""),
                "bear_history": debate.get("bear_history", ""),
                "judge_decision": debate.get("judge_decision", ""),
            }

        if "risk_debate_state" in state:
            risk = state["risk_debate_state"]
            data["risk_debate"] = {
                "risky_history": risk.get("risky_history", ""),
                "safe_history": risk.get("safe_history", ""),
                "neutral_history": risk.get("neutral_history", ""),
                "judge_decision": risk.get("judge_decision", ""),
            }

        with open(decision_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_stock_summary(
        self,
        symbol: str,
        trades: List[Dict],
        metrics: Dict[str, float],
    ):
        """
        保存单只股票汇总

        Args:
            symbol: 股票代码
            trades: 交易记录列表
            metrics: 评估指标
        """
        stock_dir = self.session_dir / symbol
        summary_file = stock_dir / "summary.json"

        data = {
            "symbol": symbol,
            "total_trades": len(trades),
            "metrics": metrics,
            "trades": trades,
            "generated_at": datetime.now().isoformat(),
        }

        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_final_summary(
        self,
        results: Dict[str, Any],
    ):
        """
        保存最终汇总

        Args:
            results: 所有股票的回测结果
        """
        if not self.session_dir:
            return

        # 保存 JSON 汇总
        summary_file = self.session_dir / "summary.json"

        summary = {
            "generated_at": datetime.now().isoformat(),
            "total_stocks": len(results),
            "results": {},
        }

        for symbol, result in results.items():
            if hasattr(result, "metrics"):
                summary["results"][symbol] = {
                    "cumulative_return": result.metrics.cumulative_return,
                    "win_rate": result.metrics.win_rate,
                    "max_drawdown": result.metrics.max_drawdown,
                    "total_trades": result.metrics.total_trades,
                    "sharpe_ratio": result.metrics.sharpe_ratio,
                }

        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        # 保存 CSV 指标表
        self._save_metrics_csv(results)

        # 写入会话结束信息
        self._write_session_footer(results)

    def _save_metrics_csv(self, results: Dict[str, Any]):
        """保存指标 CSV 文件"""
        csv_file = self.session_dir / "metrics.csv"

        headers = [
            "股票代码",
            "累计收益(%)",
            "胜率(%)",
            "最大回撤(%)",
            "夏普比率",
            "总交易次数",
            "盈利次数",
            "亏损次数",
        ]

        with open(csv_file, "w", encoding="utf-8") as f:
            f.write(",".join(headers) + "\n")

            for symbol, result in results.items():
                if hasattr(result, "metrics"):
                    m = result.metrics
                    row = [
                        symbol,
                        f"{m.cumulative_return:.2f}",
                        f"{m.win_rate:.2f}",
                        f"{m.max_drawdown:.2f}",
                        f"{m.sharpe_ratio:.4f}",
                        str(m.total_trades),
                        str(m.winning_trades),
                        str(m.losing_trades),
                    ]
                    f.write(",".join(row) + "\n")

    def _write_session_footer(self, results: Dict[str, Any]):
        """写入会话结束信息"""
        footer = f"""
{'='*60}
回测完成
{'='*60}
结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
总股票数: {len(results)}

结果汇总:
"""
        for symbol, result in results.items():
            if hasattr(result, "metrics"):
                m = result.metrics
                footer += f"  {symbol}: 收益 {m.cumulative_return:+.2f}% | 胜率 {m.win_rate:.1f}%\n"

        footer += f"\n{'='*60}\n"

        with open(self.session_log, "a", encoding="utf-8") as f:
            f.write(footer)

    def _log(self, message: str):
        """写入会话日志"""
        if self.session_log:
            with open(self.session_log, "a", encoding="utf-8") as f:
                f.write(message)

    def get_session_dir(self) -> Optional[Path]:
        """获取当前会话目录"""
        return self.session_dir
