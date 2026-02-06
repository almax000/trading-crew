"""
TradingCrew A股回测 TUI 显示组件

提供 Rich UI 组件用于显示回测进度、Agent 对话和统计指标
"""

from typing import Dict, List, Optional, Deque
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
from rich.layout import Layout
from rich.spinner import Spinner
from rich import box


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

# Agent 状态图标
STATUS_ICONS = {
    "pending": "  ",
    "in_progress": "→ ",
    "completed": "✓ ",
    "error": "✗ ",
}

# Agent 状态颜色
STATUS_COLORS = {
    "pending": "dim",
    "in_progress": "yellow",
    "completed": "green",
    "error": "red",
}


@dataclass
class AgentMessage:
    """Agent 消息记录"""
    timestamp: str
    agent_name: str
    agent_name_cn: str
    content: str
    msg_type: str = "report"  # report, debate, decision


class BacktestMessageBuffer:
    """回测消息缓冲区，用于存储和管理 Agent 对话"""

    def __init__(self, max_messages: int = 100):
        self.messages: Deque[AgentMessage] = deque(maxlen=max_messages)
        self.agent_status: Dict[str, str] = {
            "Market Analyst": "pending",
            "Social Analyst": "pending",
            "News Analyst": "pending",
            "Fundamentals Analyst": "pending",
            "Bull Researcher": "pending",
            "Bear Researcher": "pending",
            "Research Manager": "pending",
            "Trader": "pending",
            "Risky Analyst": "pending",
            "Neutral Analyst": "pending",
            "Safe Analyst": "pending",
            "Risk Manager": "pending",
            "Portfolio Manager": "pending",
        }
        self.current_agent: Optional[str] = None
        self.current_decision: Optional[str] = None
        self.reports: Dict[str, str] = {}

    def add_message(self, agent_name: str, content: str, msg_type: str = "report"):
        """添加 Agent 消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        agent_name_cn = AGENT_NAMES_CN.get(agent_name, agent_name)

        msg = AgentMessage(
            timestamp=timestamp,
            agent_name=agent_name,
            agent_name_cn=agent_name_cn,
            content=content,
            msg_type=msg_type,
        )
        self.messages.append(msg)

    def update_agent_status(self, agent_name: str, status: str):
        """更新 Agent 状态"""
        if agent_name in self.agent_status:
            self.agent_status[agent_name] = status
            if status == "in_progress":
                self.current_agent = agent_name

    def update_report(self, report_name: str, content: str):
        """更新报告内容"""
        self.reports[report_name] = content

    def set_decision(self, decision: str):
        """设置当前决策"""
        self.current_decision = decision

    def reset_for_new_day(self):
        """为新的交易日重置状态"""
        for agent in self.agent_status:
            self.agent_status[agent] = "pending"
        self.current_agent = None
        self.current_decision = None
        self.messages.clear()
        self.reports.clear()


class AgentStatusPanel:
    """Agent 状态面板"""

    def __init__(self, buffer: BacktestMessageBuffer):
        self.buffer = buffer

    def render(self) -> Panel:
        """渲染 Agent 状态面板"""
        table = Table(
            show_header=False,
            box=None,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("状态", width=3)
        table.add_column("Agent", width=12)

        # 分组显示
        groups = [
            ("分析团队", ["Market Analyst", "Social Analyst", "News Analyst", "Fundamentals Analyst"]),
            ("研究团队", ["Bull Researcher", "Bear Researcher", "Research Manager"]),
            ("交易团队", ["Trader"]),
            ("风控团队", ["Risky Analyst", "Neutral Analyst", "Safe Analyst", "Risk Manager"]),
            ("决策", ["Portfolio Manager"]),
        ]

        for group_name, agents in groups:
            # 添加分组标题
            table.add_row("", Text(f"[{group_name}]", style="bold cyan"))

            for agent in agents:
                status = self.buffer.agent_status.get(agent, "pending")
                icon = STATUS_ICONS.get(status, "  ")
                color = STATUS_COLORS.get(status, "dim")
                agent_cn = AGENT_NAMES_CN.get(agent, agent)

                # 进行中的 Agent 显示 spinner
                if status == "in_progress":
                    status_text = Text(icon, style="yellow bold")
                else:
                    status_text = Text(icon, style=color)

                table.add_row(status_text, Text(agent_cn, style=color))

        return Panel(
            table,
            title="Agent 状态",
            border_style="cyan",
            padding=(0, 1),
        )


class AgentConversationPanel:
    """Agent 对话面板"""

    def __init__(self, buffer: BacktestMessageBuffer, max_display: int = 10):
        self.buffer = buffer
        self.max_display = max_display

    def render(self) -> Panel:
        """渲染对话面板"""
        if not self.buffer.messages:
            content = Text("等待 Agent 分析...", style="dim italic")
        else:
            # 获取最近的消息
            recent_messages = list(self.buffer.messages)[-self.max_display:]

            lines = []
            for msg in recent_messages:
                # 时间戳
                time_text = f"[dim][{msg.timestamp}][/dim]"
                # Agent 名称
                agent_text = f"[bold cyan]{msg.agent_name_cn}:[/bold cyan]"
                # 内容（截断显示）
                content_preview = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                # 去掉换行符用于预览
                content_preview = content_preview.replace("\n", " ")

                lines.append(f"{time_text} {agent_text}")
                lines.append(f"  {content_preview}")
                lines.append("")

            content = Text.from_markup("\n".join(lines))

        return Panel(
            content,
            title="Agent 对话",
            border_style="green",
            padding=(0, 1),
        )


class BacktestProgressPanel:
    """回测进度面板"""

    def __init__(self):
        self.current_stock_idx: int = 0
        self.total_stocks: int = 0
        self.current_stock: str = ""
        self.stock_name: str = ""
        self.current_day_idx: int = 0
        self.total_days: int = 0
        self.current_date: str = ""

    def update(
        self,
        stock_idx: int = None,
        total_stocks: int = None,
        stock: str = None,
        stock_name: str = None,
        day_idx: int = None,
        total_days: int = None,
        date: str = None,
    ):
        """更新进度信息"""
        if stock_idx is not None:
            self.current_stock_idx = stock_idx
        if total_stocks is not None:
            self.total_stocks = total_stocks
        if stock is not None:
            self.current_stock = stock
        if stock_name is not None:
            self.stock_name = stock_name
        if day_idx is not None:
            self.current_day_idx = day_idx
        if total_days is not None:
            self.total_days = total_days
        if date is not None:
            self.current_date = date

    def render(self) -> Panel:
        """渲染进度面板"""
        stock_progress = f"[{self.current_stock_idx}/{self.total_stocks}]" if self.total_stocks > 0 else ""
        day_progress = f"[{self.current_day_idx}/{self.total_days}]" if self.total_days > 0 else ""

        stock_info = f"{self.current_stock}"
        if self.stock_name:
            stock_info += f" {self.stock_name}"

        content = Text()
        content.append("股票: ", style="bold")
        content.append(f"{stock_progress} {stock_info}", style="cyan")
        content.append("  |  ", style="dim")
        content.append("日期: ", style="bold")
        content.append(f"{day_progress} {self.current_date}", style="yellow")

        return Panel(
            content,
            title="TradingCrew A股回测系统",
            border_style="blue",
            padding=(0, 2),
        )


class DecisionPanel:
    """决策面板"""

    def __init__(self, buffer: BacktestMessageBuffer):
        self.buffer = buffer

    def render(self) -> Panel:
        """渲染决策面板"""
        decision = self.buffer.current_decision

        if decision:
            # 根据决策类型设置颜色
            if "BUY" in decision.upper() or "买入" in decision:
                style = "bold green"
                icon = "📈"
            elif "SELL" in decision.upper() or "卖出" in decision:
                style = "bold red"
                icon = "📉"
            else:
                style = "bold yellow"
                icon = "➖"

            content = Text(f"{icon} 当前决策: {decision}", style=style)
        else:
            content = Text("等待决策...", style="dim italic")

        return Panel(
            content,
            border_style="magenta",
            padding=(0, 2),
        )


class MetricsPanel:
    """统计指标面板"""

    def __init__(self):
        self.cumulative_return: float = 0.0
        self.win_rate: float = 0.0
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.current_day_return: float = 0.0

    def update(
        self,
        cumulative_return: float = None,
        win_rate: float = None,
        total_trades: int = None,
        winning_trades: int = None,
        current_day_return: float = None,
    ):
        """更新指标"""
        if cumulative_return is not None:
            self.cumulative_return = cumulative_return
        if win_rate is not None:
            self.win_rate = win_rate
        if total_trades is not None:
            self.total_trades = total_trades
        if winning_trades is not None:
            self.winning_trades = winning_trades
        if current_day_return is not None:
            self.current_day_return = current_day_return

    def render(self) -> Panel:
        """渲染指标面板"""
        # 累计收益颜色
        return_color = "green" if self.cumulative_return >= 0 else "red"
        return_sign = "+" if self.cumulative_return >= 0 else ""

        # 当日收益颜色
        day_return_color = "green" if self.current_day_return >= 0 else "red"
        day_return_sign = "+" if self.current_day_return >= 0 else ""

        content = Text()
        content.append("累计收益: ", style="bold")
        content.append(f"{return_sign}{self.cumulative_return:.2f}%", style=return_color)
        content.append("  |  ", style="dim")
        content.append("胜率: ", style="bold")
        content.append(f"{self.win_rate:.1f}%", style="cyan")
        content.append("  |  ", style="dim")
        content.append("交易: ", style="bold")
        content.append(f"{self.winning_trades}/{self.total_trades}", style="yellow")
        content.append("  |  ", style="dim")
        content.append("今日: ", style="bold")
        content.append(f"{day_return_sign}{self.current_day_return:.2f}%", style=day_return_color)

        return Panel(
            content,
            border_style="blue",
            padding=(0, 2),
        )


def create_backtest_layout() -> Layout:
    """创建回测 TUI 布局"""
    layout = Layout()

    # 三层布局: header + main + footer
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3),
    )

    # main 分为左侧状态和右侧对话
    layout["main"].split_row(
        Layout(name="status", ratio=1, minimum_size=20),
        Layout(name="content", ratio=3),
    )

    # content 分为对话区和决策区
    layout["content"].split_column(
        Layout(name="conversation", ratio=4),
        Layout(name="decision", size=3),
    )

    return layout
