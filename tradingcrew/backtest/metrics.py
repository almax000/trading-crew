"""
回测评估指标计算

支持的指标:
- 胜率 (Win Rate)
- 累计收益 (Cumulative Return)
- 最大回撤 (Maximum Drawdown)
- 夏普比率 (Sharpe Ratio)
- 平均收益 (Average Return)
- 波动率 (Volatility)
"""

from dataclasses import dataclass
from typing import List, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from .runner import TradeRecord


@dataclass
class BacktestMetrics:
    """回测评估指标"""
    win_rate: float = 0.0              # 胜率 (%)
    cumulative_return: float = 0.0     # 累计收益 (%)
    max_drawdown: float = 0.0          # 最大回撤 (%)
    sharpe_ratio: float = 0.0          # 夏普比率 (年化)
    total_trades: int = 0              # 总交易次数
    active_trades: int = 0             # 主动交易次数 (BUY/SELL)
    winning_trades: int = 0            # 盈利交易次数
    losing_trades: int = 0             # 亏损交易次数
    avg_return: float = 0.0            # 平均收益 (%)
    volatility: float = 0.0            # 波动率 (%)
    profit_factor: float = 0.0         # 盈亏比
    max_consecutive_wins: int = 0      # 最大连胜次数
    max_consecutive_losses: int = 0    # 最大连亏次数

    def __str__(self) -> str:
        return f"""
========================================
           回测评估报告
========================================
交易统计:
  总交易日数:      {self.total_trades}
  主动交易次数:    {self.active_trades} (BUY/SELL)
  盈利次数:        {self.winning_trades}
  亏损次数:        {self.losing_trades}
  胜率:            {self.win_rate:.2f}%

收益指标:
  累计收益:        {self.cumulative_return:.2f}%
  平均收益:        {self.avg_return:.2f}%
  最大回撤:        {self.max_drawdown:.2f}%

风险指标:
  波动率:          {self.volatility:.2f}%
  夏普比率:        {self.sharpe_ratio:.2f}
  盈亏比:          {self.profit_factor:.2f}

连续统计:
  最大连胜:        {self.max_consecutive_wins}
  最大连亏:        {self.max_consecutive_losses}
========================================
"""

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "win_rate": self.win_rate,
            "cumulative_return": self.cumulative_return,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "total_trades": self.total_trades,
            "active_trades": self.active_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_return": self.avg_return,
            "volatility": self.volatility,
            "profit_factor": self.profit_factor,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
        }


def calculate_metrics(trades: List["TradeRecord"]) -> BacktestMetrics:
    """
    计算回测评估指标

    Args:
        trades: TradeRecord 列表

    Returns:
        BacktestMetrics 对象
    """
    if not trades:
        return BacktestMetrics()

    # 提取收益率序列
    returns = [t.return_pct for t in trades]

    # 过滤非零收益 (BUY/SELL 决策)
    active_trades_list = [(r, t) for r, t in zip(returns, trades) if t.decision != "HOLD"]
    active_returns = [r for r, t in active_trades_list]

    # 基础统计
    total_trades = len(trades)
    active_trades = len(active_returns)

    if active_trades == 0:
        return BacktestMetrics(total_trades=total_trades)

    # 胜率
    winning_trades = sum(1 for r in active_returns if r > 0)
    losing_trades = sum(1 for r in active_returns if r < 0)
    win_rate = (winning_trades / active_trades * 100) if active_trades > 0 else 0

    # 累计收益 (简单累加)
    cumulative_return = sum(returns)

    # 最大回撤
    max_drawdown = calculate_max_drawdown(returns)

    # 平均收益
    avg_return = np.mean(active_returns) if active_returns else 0

    # 波动率
    volatility = np.std(active_returns) if len(active_returns) > 1 else 0

    # 夏普比率 (假设无风险利率为0，年化因子约 sqrt(252))
    if volatility > 0:
        sharpe_ratio = (avg_return / volatility) * np.sqrt(252)
    else:
        sharpe_ratio = 0

    # 盈亏比
    total_profit = sum(r for r in active_returns if r > 0)
    total_loss = abs(sum(r for r in active_returns if r < 0))
    profit_factor = (total_profit / total_loss) if total_loss > 0 else float('inf') if total_profit > 0 else 0

    # 连续统计
    max_consecutive_wins, max_consecutive_losses = calculate_consecutive_stats(active_returns)

    return BacktestMetrics(
        win_rate=win_rate,
        cumulative_return=cumulative_return,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe_ratio,
        total_trades=total_trades,
        active_trades=active_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        avg_return=avg_return,
        volatility=volatility,
        profit_factor=profit_factor if profit_factor != float('inf') else 999.99,
        max_consecutive_wins=max_consecutive_wins,
        max_consecutive_losses=max_consecutive_losses,
    )


def calculate_max_drawdown(returns: List[float]) -> float:
    """
    计算最大回撤

    Args:
        returns: 收益率序列 (%)

    Returns:
        最大回撤百分比
    """
    if not returns:
        return 0.0

    # 计算累计净值曲线
    cumulative = [100.0]  # 初始净值 100
    for r in returns:
        cumulative.append(cumulative[-1] * (1 + r / 100))

    # 计算历史最高点
    peak = cumulative[0]
    max_dd = 0.0

    for value in cumulative:
        if value > peak:
            peak = value
        if peak > 0:
            drawdown = (peak - value) / peak * 100
            max_dd = max(max_dd, drawdown)

    return max_dd


def calculate_consecutive_stats(returns: List[float]) -> tuple:
    """
    计算连续盈亏统计

    Args:
        returns: 收益率序列

    Returns:
        (最大连胜次数, 最大连亏次数)
    """
    if not returns:
        return 0, 0

    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0

    for r in returns:
        if r > 0:
            current_wins += 1
            current_losses = 0
            max_wins = max(max_wins, current_wins)
        elif r < 0:
            current_losses += 1
            current_wins = 0
            max_losses = max(max_losses, current_losses)
        else:
            # r == 0, 不改变连续计数
            pass

    return max_wins, max_losses


def calculate_sortino_ratio(returns: List[float], target_return: float = 0) -> float:
    """
    计算 Sortino 比率 (仅考虑下行风险)

    Args:
        returns: 收益率序列
        target_return: 目标收益率

    Returns:
        Sortino 比率
    """
    if not returns:
        return 0.0

    excess_returns = [r - target_return for r in returns]
    downside_returns = [r for r in excess_returns if r < 0]

    if not downside_returns:
        return float('inf') if np.mean(excess_returns) > 0 else 0

    downside_std = np.std(downside_returns)
    if downside_std == 0:
        return 0

    return (np.mean(excess_returns) / downside_std) * np.sqrt(252)


def calculate_calmar_ratio(cumulative_return: float, max_drawdown: float) -> float:
    """
    计算 Calmar 比率 (收益/最大回撤)

    Args:
        cumulative_return: 累计收益率 (%)
        max_drawdown: 最大回撤 (%)

    Returns:
        Calmar 比率
    """
    if max_drawdown == 0:
        return float('inf') if cumulative_return > 0 else 0

    return cumulative_return / max_drawdown
