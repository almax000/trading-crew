#!/usr/bin/env python3
"""
TradingCrew 多市场回测 Textual TUI

使用 Textual 实现交互式 TUI，支持：
- 鼠标滚动查看报告
- 标签页切换不同 Agent 报告
- 按钮控制回测
- 多市场 (A股/美股/港股)
"""

import asyncio
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header,
    Footer,
    Button,
    Static,
    Label,
    TabbedContent,
    TabPane,
    ProgressBar,
    DataTable,
    Markdown,
    Rule,
    LoadingIndicator,
)
from textual.binding import Binding
from textual.reactive import reactive
from textual import work
from textual.worker import Worker, get_current_worker

from rich.text import Text


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

# Agent 分组
AGENT_GROUPS = {
    "分析团队": ["Market Analyst", "Social Analyst", "News Analyst", "Fundamentals Analyst"],
    "研究团队": ["Bull Researcher", "Bear Researcher", "Research Manager"],
    "交易": ["Trader"],
    "风控团队": ["Risky Analyst", "Neutral Analyst", "Safe Analyst", "Risk Manager"],
    "决策": ["Portfolio Manager"],
}


@dataclass
class BacktestConfig:
    """回测配置"""
    symbols: List[str] = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    market: str = "A-share"  # A-share, US, HK
    llm_provider: str = "dashscope"
    max_debate_rounds: int = 2
    analysts: List[str] = field(default_factory=lambda: ["market", "social", "news", "fundamentals"])


class AgentStatusWidget(Static):
    """Agent 状态显示组件"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.agent_status: Dict[str, str] = {
            agent: "pending"
            for agents in AGENT_GROUPS.values()
            for agent in agents
        }

    def update_status(self, agent_name: str, status: str):
        """更新 Agent 状态"""
        if agent_name in self.agent_status:
            self.agent_status[agent_name] = status
            self.refresh()

    def reset_all(self):
        """重置所有状态"""
        for agent in self.agent_status:
            self.agent_status[agent] = "pending"
        self.refresh()

    def render(self) -> Text:
        """渲染状态列表"""
        text = Text()

        status_icons = {
            "pending": ("  ", "dim"),
            "in_progress": ("→ ", "yellow bold"),
            "completed": ("✓ ", "green"),
            "error": ("✗ ", "red"),
        }

        for group_name, agents in AGENT_GROUPS.items():
            text.append(f"\n[{group_name}]\n", style="bold cyan")
            for agent in agents:
                status = self.agent_status.get(agent, "pending")
                icon, style = status_icons.get(status, ("  ", "dim"))
                agent_cn = AGENT_NAMES_CN.get(agent, agent)
                text.append(f"  {icon}", style=style)
                text.append(f"{agent_cn}\n", style=style)

        return text


class ReportPane(TabPane):
    """报告标签页面板"""

    def __init__(self, agent_name: str, agent_name_cn: str, **kwargs):
        super().__init__(agent_name_cn, id=f"tab-{agent_name.lower().replace(' ', '-')}", **kwargs)
        self.agent_name = agent_name
        self.agent_name_cn = agent_name_cn
        self.content = ""

    def compose(self) -> ComposeResult:
        with ScrollableContainer():
            yield Markdown("*等待分析...*", id=f"report-{self.agent_name.lower().replace(' ', '-')}")

    def update_content(self, content: str):
        """更新报告内容"""
        self.content = content
        try:
            md_widget = self.query_one(f"#report-{self.agent_name.lower().replace(' ', '-')}", Markdown)
            md_widget.update(content)
        except Exception:
            pass


class BacktestApp(App):
    """A股回测 Textual 应用"""

    CSS = """
    #header-panel {
        height: 3;
        background: $surface;
        padding: 0 1;
    }

    #body-panel {
        height: 1fr;
    }

    #status-panel {
        width: 24;
        background: $surface;
        border: solid $primary;
        padding: 0 1;
    }

    #main-panel {
        width: 1fr;
        background: $surface;
        border: solid $secondary;
    }

    #footer-panel {
        height: 3;
        background: $surface;
        padding: 0 1;
        align: center middle;
    }

    #progress-label {
        width: auto;
        padding: 0 2;
    }

    #metrics-label {
        width: auto;
        padding: 0 2;
    }

    Button {
        margin: 0 1;
    }

    TabbedContent {
        height: 100%;
    }

    TabPane {
        padding: 1;
    }

    ScrollableContainer {
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("s", "start_backtest", "开始"),
        Binding("x", "stop_backtest", "停止"),
        Binding("r", "reset", "重置"),
    ]

    # 响应式属性
    current_stock = reactive("")
    current_date = reactive("")
    stock_progress = reactive("")
    day_progress = reactive("")
    cumulative_return = reactive(0.0)
    total_trades = reactive(0)
    winning_trades = reactive(0)
    is_running = reactive(False)

    def __init__(self, config: Optional[BacktestConfig] = None, **kwargs):
        super().__init__(**kwargs)
        self.config = config or BacktestConfig()
        self.agent_reports: Dict[str, str] = {}
        self.backtest_worker: Optional[Worker] = None
        self.log_handler = None

    def compose(self) -> ComposeResult:
        """构建 UI 布局"""
        yield Header(show_clock=True)

        with Vertical():
            # 顶部进度信息
            with Horizontal(id="header-panel"):
                yield Label("股票: --  日期: --", id="progress-label")
                yield ProgressBar(total=100, show_eta=False, id="main-progress")

            # 中间主体区域
            with Horizontal(id="body-panel"):
                # 左侧 Agent 状态
                with ScrollableContainer(id="status-panel"):
                    yield Static("[bold cyan]Agent 状态[/bold cyan]")
                    yield AgentStatusWidget(id="agent-status")

                # 右侧主要内容区域 - 标签页
                with Container(id="main-panel"):
                    with TabbedContent(id="reports-tabs"):
                        # 分析团队标签页
                        yield ReportPane("Market Analyst", "市场分析师")
                        yield ReportPane("Social Analyst", "舆情分析师")
                        yield ReportPane("News Analyst", "新闻分析师")
                        yield ReportPane("Fundamentals Analyst", "基本面分析师")
                        # 研究团队标签页
                        yield ReportPane("Bull Researcher", "看多研究员")
                        yield ReportPane("Bear Researcher", "看空研究员")
                        yield ReportPane("Research Manager", "研究经理")
                        # 交易和风控
                        yield ReportPane("Trader", "交易员")
                        yield ReportPane("Risky Analyst", "激进风控")
                        yield ReportPane("Safe Analyst", "保守风控")
                        yield ReportPane("Neutral Analyst", "中性风控")
                        yield ReportPane("Risk Manager", "风险经理")
                        yield ReportPane("Portfolio Manager", "组合经理")

            # 底部控制区
            with Horizontal(id="footer-panel"):
                yield Button("开始回测", id="btn-start", variant="success")
                yield Button("停止", id="btn-stop", variant="error", disabled=True)
                yield Label("累计收益: 0.00%  交易: 0  胜率: 0.0%", id="metrics-label")

        yield Footer()

    def on_mount(self) -> None:
        """应用挂载时初始化"""
        market_names = {"A-share": "A股", "US": "美股", "HK": "港股"}
        market_name = market_names.get(self.config.market, self.config.market)
        self.title = f"TradingCrew {market_name}回测系统"
        self.sub_title = "Multi-Agent LLM Trading Framework"

    def watch_current_stock(self, value: str) -> None:
        """监听股票变化"""
        self._update_progress_label()

    def watch_current_date(self, value: str) -> None:
        """监听日期变化"""
        self._update_progress_label()

    def watch_cumulative_return(self, value: float) -> None:
        """监听收益变化"""
        self._update_metrics_label()

    def watch_total_trades(self, value: int) -> None:
        """监听交易次数变化"""
        self._update_metrics_label()

    def _update_progress_label(self) -> None:
        """更新进度标签"""
        label = self.query_one("#progress-label", Label)
        label.update(f"股票: {self.stock_progress} {self.current_stock}  |  日期: {self.day_progress} {self.current_date}")

    def _update_metrics_label(self) -> None:
        """更新指标标签"""
        label = self.query_one("#metrics-label", Label)
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        return_color = "green" if self.cumulative_return >= 0 else "red"
        label.update(f"累计收益: [{return_color}]{self.cumulative_return:+.2f}%[/{return_color}]  交易: {self.total_trades}  胜率: {win_rate:.1f}%")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击事件"""
        if event.button.id == "btn-start":
            self.action_start_backtest()
        elif event.button.id == "btn-stop":
            self.action_stop_backtest()

    def action_start_backtest(self) -> None:
        """开始回测"""
        if self.is_running:
            return

        # 检查配置
        if not self.config.symbols:
            self.notify("请先配置股票代码", severity="warning")
            return

        self.is_running = True
        self.query_one("#btn-start", Button).disabled = True
        self.query_one("#btn-stop", Button).disabled = False

        # 重置状态
        agent_status = self.query_one("#agent-status", AgentStatusWidget)
        agent_status.reset_all()

        # 启动后台任务
        self.run_backtest_async()

    def action_stop_backtest(self) -> None:
        """停止回测"""
        if self.backtest_worker:
            self.backtest_worker.cancel()
        self.is_running = False
        self.query_one("#btn-start", Button).disabled = False
        self.query_one("#btn-stop", Button).disabled = True
        self.notify("回测已停止", severity="warning")

    def action_reset(self) -> None:
        """重置界面"""
        agent_status = self.query_one("#agent-status", AgentStatusWidget)
        agent_status.reset_all()

        # 清空所有报告
        for agent_name in AGENT_NAMES_CN:
            self._update_report(agent_name, "*等待分析...*")

        self.cumulative_return = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.current_stock = ""
        self.current_date = ""

    @work(exclusive=True, thread=True)
    def run_backtest_async(self) -> None:
        """在后台线程运行回测"""
        from tradingcrew.market_config import (
            get_market_config,
            get_dashscope_config,
            get_openai_config,
        )
        from tradingcrew.backtest.runner import BacktestRunner
        from tradingcrew.backtest.multi_market_calendar import get_trading_days_in_range
        from cli.backtest_log_handler import BacktestLogHandler

        worker = get_current_worker()

        try:
            # 配置 (使用多市场配置)
            if self.config.llm_provider in ("dashscope", "deepseek"):
                run_config = get_dashscope_config(
                    market=self.config.market,
                    max_debate_rounds=self.config.max_debate_rounds,
                    max_risk_discuss_rounds=self.config.max_debate_rounds,
                )
            elif self.config.llm_provider == "openai":
                run_config = get_openai_config(
                    market=self.config.market,
                    max_debate_rounds=self.config.max_debate_rounds,
                    max_risk_discuss_rounds=self.config.max_debate_rounds,
                )
            else:
                run_config = get_market_config(self.config.market)

            run_config["use_chinese_output"] = True

            # 初始化日志
            self.log_handler = BacktestLogHandler()
            session_dir = self.log_handler.setup_session(
                self.config.symbols,
                self.config.start_date,
                self.config.end_date
            )

            # 创建回测执行器
            runner = BacktestRunner(
                config=run_config,
                selected_analysts=self.config.analysts,
                enable_reflection=True,
                api_call_delay=1.0,
                debug=False,
                save_states=True,
            )

            # 获取交易日 (根据市场)
            all_trading_days = get_trading_days_in_range(
                self.config.start_date,
                self.config.end_date,
                market=self.config.market
            )
            total_days = len(all_trading_days)

            results = {}

            for stock_idx, symbol in enumerate(self.config.symbols):
                if worker.is_cancelled:
                    break

                self.log_handler.start_stock(symbol)

                # 更新 UI (线程安全)
                self.call_from_thread(self._set_stock_progress, stock_idx + 1, len(self.config.symbols), symbol)

                def progress_callback(current: int, total: int, date: str):
                    if worker.is_cancelled:
                        return
                    self.log_handler.start_day(date)
                    self.call_from_thread(self._set_day_progress, current, total, date)
                    self.call_from_thread(self._reset_agent_status)

                def stream_callback(sym: str, date: str, agent: str, content: str):
                    if worker.is_cancelled:
                        return
                    # 更新报告
                    self.call_from_thread(self._update_report, agent, content)
                    # 更新状态
                    self.call_from_thread(self._set_agent_completed, agent)
                    # 保存到文件
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
                    self.log_handler.log_agent_message(agent, content)

                # 执行回测
                result = runner.run(
                    symbol=symbol,
                    start_date=self.config.start_date,
                    end_date=self.config.end_date,
                    progress_callback=progress_callback,
                    stream_callback=stream_callback,
                )

                results[symbol] = result

                # 更新统计
                self.call_from_thread(
                    self._update_metrics,
                    result.metrics.cumulative_return,
                    result.metrics.total_trades,
                    result.metrics.winning_trades
                )

                # 保存汇总
                self.log_handler.save_stock_summary(
                    symbol,
                    [t.to_dict() for t in result.trades],
                    result.metrics.to_dict(),
                )

            # 完成
            if self.log_handler:
                self.log_handler.save_final_summary(results)

            self.call_from_thread(self._on_backtest_complete, results)

        except Exception as e:
            self.call_from_thread(self.notify, f"回测错误: {e}", severity="error")
        finally:
            self.call_from_thread(self._on_backtest_finished)

    def _set_stock_progress(self, current: int, total: int, symbol: str) -> None:
        """设置股票进度"""
        self.stock_progress = f"[{current}/{total}]"
        self.current_stock = symbol

        # 更新进度条
        progress = self.query_one("#main-progress", ProgressBar)
        progress.update(total=total * 100, progress=current * 100)

    def _set_day_progress(self, current: int, total: int, date: str) -> None:
        """设置日期进度"""
        self.day_progress = f"[{current}/{total}]"
        self.current_date = date

    def _reset_agent_status(self) -> None:
        """重置 Agent 状态"""
        agent_status = self.query_one("#agent-status", AgentStatusWidget)
        agent_status.reset_all()
        # 设置第一个分析师为进行中
        if "market" in self.config.analysts:
            agent_status.update_status("Market Analyst", "in_progress")

    def _set_agent_completed(self, agent_name: str) -> None:
        """设置 Agent 完成状态"""
        agent_status = self.query_one("#agent-status", AgentStatusWidget)
        agent_status.update_status(agent_name, "completed")

        # 设置下一个 Agent 为进行中
        agent_order = [
            "Market Analyst", "Social Analyst", "News Analyst", "Fundamentals Analyst",
            "Bull Researcher", "Bear Researcher", "Research Manager",
            "Trader",
            "Risky Analyst", "Safe Analyst", "Neutral Analyst", "Risk Manager",
            "Portfolio Manager",
        ]
        try:
            idx = agent_order.index(agent_name)
            if idx + 1 < len(agent_order):
                next_agent = agent_order[idx + 1]
                agent_status.update_status(next_agent, "in_progress")
        except ValueError:
            pass

    def _update_report(self, agent_name: str, content: str) -> None:
        """更新报告内容"""
        tab_id = f"tab-{agent_name.lower().replace(' ', '-')}"
        try:
            tabs = self.query_one("#reports-tabs", TabbedContent)
            pane = tabs.query_one(f"#{tab_id}", ReportPane)
            pane.update_content(content)

            # 自动切换到当前标签
            tabs.active = tab_id
        except Exception:
            pass

    def _update_metrics(self, cumulative: float, trades: int, wins: int) -> None:
        """更新统计指标"""
        self.cumulative_return += cumulative
        self.total_trades += trades
        self.winning_trades += wins

    def _on_backtest_complete(self, results: Dict) -> None:
        """回测完成回调"""
        self.notify("回测完成!", severity="information")

    def _on_backtest_finished(self) -> None:
        """回测结束回调（无论成功或失败）"""
        self.is_running = False
        self.query_one("#btn-start", Button).disabled = False
        self.query_one("#btn-stop", Button).disabled = True


def run_textual_app(config: BacktestConfig) -> None:
    """运行 Textual TUI 应用"""
    app = BacktestApp(config=config)
    app.run()


def main():
    """主入口 - 配置并启动 TUI"""
    from cli.backtest_utils import (
        select_market,
        get_stock_codes,
        get_backtest_date_range,
        select_llm_config,
        select_analysts,
        MARKET_INFO,
    )
    from rich.console import Console

    console = Console()

    # 显示欢迎信息
    console.print("\n[bold cyan]TradingCrew 多市场回测系统 - 交互式 TUI[/bold cyan]")
    console.print("[dim]支持: A股 / 美股 / 港股[/dim]\n")

    try:
        # 1. 选择市场
        market = select_market()
        if not market:
            console.print("[yellow]已取消[/yellow]")
            return

        # 2. 获取股票代码
        stocks = get_stock_codes(market=market)
        if not stocks:
            console.print("[yellow]已取消[/yellow]")
            return

        # 3. 获取日期范围
        start_date, end_date = get_backtest_date_range()
        if not start_date or not end_date:
            console.print("[yellow]已取消[/yellow]")
            return

        # 4. 选择 LLM 配置
        llm_config = select_llm_config()
        if not llm_config:
            console.print("[yellow]已取消[/yellow]")
            return

        # 5. 选择分析师
        analysts = select_analysts()
        if not analysts:
            analysts = ["market"]

        # 创建配置
        config = BacktestConfig(
            symbols=stocks,
            start_date=start_date,
            end_date=end_date,
            market=market,
            llm_provider=llm_config.get("llm_provider", "dashscope"),
            max_debate_rounds=llm_config.get("max_debate_rounds", 2),
            analysts=analysts,
        )

        market_name = MARKET_INFO.get(market, {}).get("name", market)
        console.print(f"\n[dim]启动交互式 TUI ({market_name})...[/dim]\n")

        # 启动 Textual 应用
        run_textual_app(config)

    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断[/yellow]")
    except Exception as e:
        console.print(f"\n[red]错误: {e}[/red]")
        raise


if __name__ == "__main__":
    main()
