#!/usr/bin/env python3
"""
TradingCrew 多市场回测 TUI 主程序

使用 Rich 提供美观的终端界面，支持：
- 多市场 (A股、美股、港股)
- 多股票代码输入
- 实时流式显示 Agent 对话
- 同步保存到文件
"""

import sys
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.markdown import Markdown
from rich import box

from cli.backtest_display import (
    BacktestMessageBuffer,
    AgentStatusPanel,
    AgentConversationPanel,
    BacktestProgressPanel,
    DecisionPanel,
    MetricsPanel,
    create_backtest_layout,
    AGENT_NAMES_CN,
)
from cli.backtest_utils import (
    select_market,
    get_stock_codes,
    get_backtest_date_range,
    select_llm_config,
    select_analysts,
    select_output_mode,
    confirm_backtest_settings,
    MARKET_INFO,
)
from cli.backtest_log_handler import BacktestLogHandler


console = Console()


class BacktestTUI:
    """多市场回测 TUI 应用"""

    def __init__(self, verbose_output: bool = True, market: str = "A-share"):
        """
        初始化 TUI 应用

        Args:
            verbose_output: 是否显示完整输出 (True=完整输出, False=简洁面板)
            market: 市场类型 ("A-share", "US", "HK")
        """
        self.console = Console()
        self.message_buffer = BacktestMessageBuffer()
        self.progress_panel = BacktestProgressPanel()
        self.metrics_panel = MetricsPanel()
        self.log_handler: Optional[BacktestLogHandler] = None
        self.verbose_output = verbose_output
        self.market = market

        # 当前回测状态
        self.current_symbol: str = ""
        self.current_date: str = ""
        self.cumulative_return: float = 0.0
        self.total_trades: int = 0
        self.winning_trades: int = 0

    def create_layout(self) -> Layout:
        """创建 TUI 布局"""
        return create_backtest_layout()

    def update_layout(self, layout: Layout):
        """更新布局内容"""
        # Header - 进度信息
        layout["header"].update(self.progress_panel.render())

        # Status - Agent 状态
        status_panel = AgentStatusPanel(self.message_buffer)
        layout["status"].update(status_panel.render())

        # Conversation - Agent 对话
        conv_panel = AgentConversationPanel(self.message_buffer, max_display=8)
        layout["conversation"].update(conv_panel.render())

        # Decision - 当前决策
        decision_panel = DecisionPanel(self.message_buffer)
        layout["decision"].update(decision_panel.render())

        # Footer - 统计指标
        layout["footer"].update(self.metrics_panel.render())

    def _print_agent_output(self, agent_name: str, content: str):
        """打印完整的 Agent 输出"""
        agent_name_cn = AGENT_NAMES_CN.get(agent_name, agent_name)
        timestamp = datetime.now().strftime("%H:%M:%S")

        # 根据 Agent 类型选择颜色
        if agent_name in ["Market Analyst", "Social Analyst", "News Analyst", "Fundamentals Analyst"]:
            color = "cyan"
        elif agent_name in ["Bull Researcher", "Bear Researcher", "Research Manager"]:
            color = "green"
        elif agent_name == "Trader":
            color = "yellow"
        elif agent_name in ["Risky Analyst", "Neutral Analyst", "Safe Analyst", "Risk Manager"]:
            color = "magenta"
        else:
            color = "blue"

        # 打印分隔线和标题
        self.console.print()
        self.console.rule(f"[bold {color}][{timestamp}] {agent_name_cn}[/bold {color}]", style=color)
        self.console.print()

        # 打印完整内容 (尝试解析为 Markdown)
        try:
            self.console.print(Markdown(content))
        except Exception:
            self.console.print(content)

        self.console.print()

    def stream_callback(self, symbol: str, date: str, agent_name: str, content: str):
        """
        流式回调函数 - 接收 Agent 输出

        Args:
            symbol: 股票代码
            date: 交易日期
            agent_name: Agent 英文名称
            content: 输出内容
        """
        # 更新消息缓冲
        self.message_buffer.add_message(agent_name, content)

        # 更新 Agent 状态为完成
        self.message_buffer.update_agent_status(agent_name, "completed")

        # 如果是最终决策，提取决策
        if agent_name == "Portfolio Manager":
            decision = self._extract_decision(content)
            self.message_buffer.set_decision(decision)

        # 写入日志文件
        if self.log_handler:
            self.log_handler.log_agent_message(agent_name, content)

    def _extract_decision(self, content: str) -> str:
        """从最终决策内容中提取决策"""
        content_upper = content.upper()
        if "BUY" in content_upper or "买入" in content:
            return "买入 (BUY)"
        elif "SELL" in content_upper or "卖出" in content:
            return "卖出 (SELL)"
        else:
            return "持有 (HOLD)"

    def run_backtest(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        config: dict,
        analysts: List[str],
    ) -> Dict:
        """
        执行回测

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            config: LLM 配置
            analysts: 选中的分析师

        Returns:
            回测结果字典
        """
        from tradingcrew.market_config import (
            get_market_config,
            get_dashscope_config,
            get_openai_config,
        )
        from tradingcrew.backtest.runner import BacktestRunner
        from tradingcrew.backtest.multi_market_calendar import get_trading_days_in_range

        # 根据选择获取配置
        llm_provider = config.get("llm_provider", "dashscope")

        if llm_provider in ("dashscope", "deepseek"):
            run_config = get_dashscope_config(
                market=self.market,
                max_debate_rounds=config.get("max_debate_rounds", 2),
                max_risk_discuss_rounds=config.get("max_risk_discuss_rounds", 2),
            )
        elif llm_provider == "openai":
            run_config = get_openai_config(
                market=self.market,
                max_debate_rounds=config.get("max_debate_rounds", 2),
                max_risk_discuss_rounds=config.get("max_risk_discuss_rounds", 2),
            )
        else:
            run_config = get_market_config(self.market)
            run_config.update(config)

        # 添加中文输出配置
        run_config["use_chinese_output"] = True

        # 初始化日志处理器
        self.log_handler = BacktestLogHandler()
        session_dir = self.log_handler.setup_session(symbols, start_date, end_date)
        console.print(f"\n[dim]日志目录: {session_dir}[/dim]\n")

        # 创建回测执行器
        runner = BacktestRunner(
            config=run_config,
            selected_analysts=analysts,
            enable_reflection=True,
            api_call_delay=1.0,
            debug=False,
            save_states=True,
        )

        results = {}

        # 获取总交易日数用于进度显示
        all_trading_days = get_trading_days_in_range(start_date, end_date, market=self.market)
        total_days = len(all_trading_days)

        # 根据 verbose_output 选择显示模式
        if self.verbose_output:
            # 完整输出模式：顺序打印每个 Agent 的完整内容
            results = self._run_verbose_mode(
                runner, symbols, start_date, end_date, analysts, total_days
            )
        else:
            # 简洁面板模式：使用 Rich Live 更新面板
            results = self._run_panel_mode(
                runner, symbols, start_date, end_date, analysts, total_days
            )

        return results

    def _run_verbose_mode(
        self,
        runner,
        symbols: List[str],
        start_date: str,
        end_date: str,
        analysts: List[str],
        total_days: int,
    ) -> Dict:
        """完整输出模式：打印每个 Agent 的完整内容"""
        results = {}

        for stock_idx, symbol in enumerate(symbols):
            self.current_symbol = symbol
            self.log_handler.start_stock(symbol)

            # 打印股票标题
            self.console.print()
            self.console.print(Panel(
                f"[bold]股票: {symbol}[/bold]  ({stock_idx + 1}/{len(symbols)})",
                title="开始分析",
                border_style="blue",
            ))

            try:
                # 定义进度回调
                def progress_callback(current: int, total: int, date: str):
                    self.current_date = date
                    self.log_handler.start_day(date)

                    # 打印日期标题
                    self.console.print()
                    self.console.print(Panel(
                        f"[bold yellow]日期: {date}[/bold yellow]  ({current}/{total})",
                        border_style="yellow",
                    ))

                # 定义流式回调 - 打印完整内容
                def stream_callback(sym: str, date: str, agent: str, content: str):
                    # 打印完整的 Agent 输出
                    self._print_agent_output(agent, content)

                    # 保存报告
                    report_map = {
                        "Market Analyst": "market_report",
                        "Social Analyst": "sentiment_report",
                        "News Analyst": "news_report",
                        "Fundamentals Analyst": "fundamentals_report",
                        "Research Manager": "investment_plan",
                        "Trader": "trader_investment_plan",
                        "Portfolio Manager": "final_trade_decision",
                    }
                    if agent in report_map:
                        self.log_handler.save_report(report_map[agent], content)

                    # 写入日志文件
                    self.log_handler.log_agent_message(agent, content)

                # 执行回测
                result = runner.run(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    progress_callback=progress_callback,
                    stream_callback=stream_callback,
                )

                results[symbol] = result

                # 更新统计指标
                self.cumulative_return += result.metrics.cumulative_return
                self.total_trades += result.metrics.total_trades
                self.winning_trades += result.metrics.winning_trades

                # 打印股票汇总
                win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
                return_color = "green" if result.metrics.cumulative_return >= 0 else "red"
                self.console.print()
                self.console.print(Panel(
                    f"[bold]股票 {symbol} 分析完成[/bold]\n"
                    f"收益: [{return_color}]{result.metrics.cumulative_return:+.2f}%[/{return_color}]  "
                    f"交易: {result.metrics.total_trades}  "
                    f"胜率: {result.metrics.win_rate:.1f}%",
                    border_style="green",
                ))

                # 保存股票汇总
                self.log_handler.save_stock_summary(
                    symbol,
                    [t.to_dict() for t in result.trades],
                    result.metrics.to_dict(),
                )

            except Exception as e:
                self.console.print(f"[red]回测 {symbol} 失败: {e}[/red]")
                continue

        # 保存最终汇总
        if self.log_handler:
            self.log_handler.save_final_summary(results)

        return results

    def _run_panel_mode(
        self,
        runner,
        symbols: List[str],
        start_date: str,
        end_date: str,
        analysts: List[str],
        total_days: int,
    ) -> Dict:
        """简洁面板模式：使用 Rich Live 更新面板"""
        results = {}
        layout = self.create_layout()

        with Live(layout, console=self.console, refresh_per_second=4) as live:
            for stock_idx, symbol in enumerate(symbols):
                self.current_symbol = symbol
                self.log_handler.start_stock(symbol)

                # 更新进度
                self.progress_panel.update(
                    stock_idx=stock_idx + 1,
                    total_stocks=len(symbols),
                    stock=symbol,
                )

                # 重置消息缓冲
                self.message_buffer.reset_for_new_day()
                self.update_layout(layout)

                try:
                    # 定义进度回调
                    def progress_callback(current: int, total: int, date: str):
                        self.current_date = date
                        self.log_handler.start_day(date)

                        # 更新进度面板
                        self.progress_panel.update(
                            day_idx=current,
                            total_days=total,
                            date=date,
                        )

                        # 重置当日 Agent 状态
                        self.message_buffer.reset_for_new_day()

                        # 设置第一个 Agent 为进行中
                        if "market" in analysts:
                            self.message_buffer.update_agent_status("Market Analyst", "in_progress")

                        self.update_layout(layout)

                    # 定义流式回调
                    def stream_callback(sym: str, date: str, agent: str, content: str):
                        self.stream_callback(sym, date, agent, content)

                        # 保存报告
                        report_map = {
                            "Market Analyst": "market_report",
                            "Social Analyst": "sentiment_report",
                            "News Analyst": "news_report",
                            "Fundamentals Analyst": "fundamentals_report",
                            "Research Manager": "investment_plan",
                            "Trader": "trader_investment_plan",
                            "Portfolio Manager": "final_trade_decision",
                        }
                        if agent in report_map:
                            self.log_handler.save_report(report_map[agent], content)

                        # 设置下一个 Agent 为进行中
                        agent_order = [
                            "Market Analyst", "Social Analyst", "News Analyst", "Fundamentals Analyst",
                            "Bull Researcher", "Bear Researcher", "Research Manager",
                            "Trader",
                            "Risky Analyst", "Safe Analyst", "Neutral Analyst", "Risk Manager",
                            "Portfolio Manager",
                        ]
                        try:
                            idx = agent_order.index(agent)
                            if idx + 1 < len(agent_order):
                                next_agent = agent_order[idx + 1]
                                self.message_buffer.update_agent_status(next_agent, "in_progress")
                        except ValueError:
                            pass

                        self.update_layout(layout)

                    # 执行回测
                    result = runner.run(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        progress_callback=progress_callback,
                        stream_callback=stream_callback,
                    )

                    results[symbol] = result

                    # 更新统计指标
                    self.cumulative_return += result.metrics.cumulative_return
                    self.total_trades += result.metrics.total_trades
                    self.winning_trades += result.metrics.winning_trades

                    win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

                    self.metrics_panel.update(
                        cumulative_return=self.cumulative_return,
                        win_rate=win_rate,
                        total_trades=self.total_trades,
                        winning_trades=self.winning_trades,
                    )

                    # 保存股票汇总
                    self.log_handler.save_stock_summary(
                        symbol,
                        [t.to_dict() for t in result.trades],
                        result.metrics.to_dict(),
                    )

                    self.update_layout(layout)

                except Exception as e:
                    console.print(f"[red]回测 {symbol} 失败: {e}[/red]")
                    continue

        # 保存最终汇总
        if self.log_handler:
            self.log_handler.save_final_summary(results)

        return results

    def display_final_report(self, results: Dict):
        """显示最终报告"""
        console.print("\n")
        console.print(Panel(
            "[bold cyan]回测完成[/bold cyan]",
            border_style="green",
        ))

        # 汇总表格
        from rich.table import Table

        table = Table(
            title="回测结果汇总",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )

        table.add_column("股票代码", style="cyan", justify="center")
        table.add_column("累计收益", justify="right")
        table.add_column("胜率", justify="right")
        table.add_column("最大回撤", justify="right")
        table.add_column("交易次数", justify="center")

        for symbol, result in results.items():
            m = result.metrics
            return_color = "green" if m.cumulative_return >= 0 else "red"
            return_str = f"[{return_color}]{m.cumulative_return:+.2f}%[/{return_color}]"

            table.add_row(
                symbol,
                return_str,
                f"{m.win_rate:.1f}%",
                f"{m.max_drawdown:.2f}%",
                str(m.total_trades),
            )

        console.print(table)

        # 输出目录
        if self.log_handler:
            console.print(f"\n[dim]详细日志已保存到: {self.log_handler.get_session_dir()}[/dim]")


def show_welcome():
    """显示欢迎界面"""
    welcome_text = """
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║   ████████╗██████╗  █████╗ ██████╗ ██╗███╗   ██╗ ██████╗       ║
║   ╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║██╔════╝       ║
║      ██║   ██████╔╝███████║██║  ██║██║██╔██╗ ██║██║  ███╗      ║
║      ██║   ██╔══██╗██╔══██║██║  ██║██║██║╚██╗██║██║   ██║      ║
║      ██║   ██║  ██║██║  ██║██████╔╝██║██║ ╚████║╚██████╔╝      ║
║      ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝       ║
║                ██████╗██████╗ ███████╗██╗    ██╗               ║
║               ██╔════╝██╔══██╗██╔════╝██║    ██║               ║
║               ██║     ██████╔╝█████╗  ██║ █╗ ██║               ║
║               ██║     ██╔══██╗██╔══╝  ██║███╗██║               ║
║               ╚██████╗██║  ██║███████╗╚███╔███╔╝               ║
║                ╚═════╝╚═╝  ╚═╝╚══════╝ ╚══╝╚══╝                ║
║                                                                ║
║              多市场智能回测系统 v2.0                             ║
║         Multi-Agent LLM Trading Framework                      ║
║                                                                ║
║      支持: 🇨🇳 A股  🇺🇸 美股  🇭🇰 港股                             ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
"""
    console.print(welcome_text, style="bold cyan")


def select_tui_mode() -> str:
    """
    选择 TUI 模式

    Returns:
        "interactive" - 交互式 TUI (鼠标支持)
        "classic" - 经典流式输出
    """
    import questionary
    from cli.backtest_utils import QUESTIONARY_STYLE

    mode = questionary.select(
        "选择界面模式:",
        choices=[
            questionary.Choice(
                "🖱️ 交互式 TUI (鼠标支持, 标签页切换)",
                value="interactive"
            ),
            questionary.Choice(
                "📜 经典模式 (流式输出, 适合查看完整报告)",
                value="classic"
            ),
        ],
        style=QUESTIONARY_STYLE,
    ).ask()

    return mode or "classic"


def main():
    """主入口"""
    show_welcome()

    try:
        # 1. 选择市场
        market = select_market()
        if not market:
            console.print("[yellow]已取消回测[/yellow]")
            return

        # 2. 获取股票代码 (根据市场验证格式)
        stocks = get_stock_codes(market=market)
        if not stocks:
            console.print("[yellow]已取消回测[/yellow]")
            return

        # 3. 获取日期范围
        start_date, end_date = get_backtest_date_range()
        if not start_date or not end_date:
            console.print("[yellow]已取消回测[/yellow]")
            return

        # 4. 选择 LLM 配置
        llm_config = select_llm_config()
        if not llm_config:
            console.print("[yellow]已取消回测[/yellow]")
            return

        # 5. 选择分析师
        analysts = select_analysts()
        if not analysts:
            analysts = ["market"]

        # 6. 选择输出模式
        verbose_output = select_output_mode()

        # 7. 确认设置 (包含市场信息)
        if not confirm_backtest_settings(stocks, start_date, end_date, llm_config, analysts, market=market):
            console.print("[yellow]已取消回测[/yellow]")
            return

        # 8. 执行回测
        tui = BacktestTUI(verbose_output=verbose_output, market=market)
        results = tui.run_backtest(
            symbols=stocks,
            start_date=start_date,
            end_date=end_date,
            config=llm_config,
            analysts=analysts,
        )

        # 9. 显示最终报告
        if results:
            tui.display_final_report(results)

    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]错误: {e}[/red]")
        raise


if __name__ == "__main__":
    main()
