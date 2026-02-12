"""
Backtest Evaluation Metrics

Supported metrics:
- Win Rate
- Cumulative Return
- Maximum Drawdown
- Sharpe Ratio
- Average Return
- Volatility
"""

from dataclasses import dataclass
from typing import List, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from .runner import TradeRecord


@dataclass
class BacktestMetrics:
    """Backtest evaluation metrics"""
    win_rate: float = 0.0              # Win rate (%)
    cumulative_return: float = 0.0     # Cumulative return (%)
    max_drawdown: float = 0.0          # Maximum drawdown (%)
    sharpe_ratio: float = 0.0          # Sharpe ratio (annualized)
    total_trades: int = 0              # Total number of trades
    active_trades: int = 0             # Active trades (BUY/SELL)
    winning_trades: int = 0            # Winning trades
    losing_trades: int = 0             # Losing trades
    avg_return: float = 0.0            # Average return (%)
    volatility: float = 0.0            # Volatility (%)
    profit_factor: float = 0.0         # Profit factor
    max_consecutive_wins: int = 0      # Max consecutive wins
    max_consecutive_losses: int = 0    # Max consecutive losses

    def __str__(self) -> str:
        return f"""
========================================
        Backtest Evaluation Report
========================================
Trade Statistics:
  Total Trading Days:    {self.total_trades}
  Active Trades:         {self.active_trades} (BUY/SELL)
  Winning Trades:        {self.winning_trades}
  Losing Trades:         {self.losing_trades}
  Win Rate:              {self.win_rate:.2f}%

Return Metrics:
  Cumulative Return:     {self.cumulative_return:.2f}%
  Average Return:        {self.avg_return:.2f}%
  Maximum Drawdown:      {self.max_drawdown:.2f}%

Risk Metrics:
  Volatility:            {self.volatility:.2f}%
  Sharpe Ratio:          {self.sharpe_ratio:.2f}
  Profit Factor:         {self.profit_factor:.2f}

Streak Statistics:
  Max Consecutive Wins:  {self.max_consecutive_wins}
  Max Consecutive Losses:{self.max_consecutive_losses}
========================================
"""

    def to_dict(self) -> dict:
        """Convert to dictionary"""
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
    Calculate backtest evaluation metrics

    Args:
        trades: List of TradeRecord

    Returns:
        BacktestMetrics object
    """
    if not trades:
        return BacktestMetrics()

    # Extract return series
    returns = [t.return_pct for t in trades]

    # Filter non-zero returns (BUY/SELL decisions)
    active_trades_list = [(r, t) for r, t in zip(returns, trades) if t.decision != "HOLD"]
    active_returns = [r for r, t in active_trades_list]

    # Basic statistics
    total_trades = len(trades)
    active_trades = len(active_returns)

    if active_trades == 0:
        return BacktestMetrics(total_trades=total_trades)

    # Win rate
    winning_trades = sum(1 for r in active_returns if r > 0)
    losing_trades = sum(1 for r in active_returns if r < 0)
    win_rate = (winning_trades / active_trades * 100) if active_trades > 0 else 0

    # Cumulative return (simple sum)
    cumulative_return = sum(returns)

    # Maximum drawdown
    max_drawdown = calculate_max_drawdown(returns)

    # Average return
    avg_return = np.mean(active_returns) if active_returns else 0

    # Volatility
    volatility = np.std(active_returns) if len(active_returns) > 1 else 0

    # Sharpe ratio (assuming risk-free rate = 0, annualization factor ~sqrt(252))
    if volatility > 0:
        sharpe_ratio = (avg_return / volatility) * np.sqrt(252)
    else:
        sharpe_ratio = 0

    # Profit factor
    total_profit = sum(r for r in active_returns if r > 0)
    total_loss = abs(sum(r for r in active_returns if r < 0))
    profit_factor = (total_profit / total_loss) if total_loss > 0 else float('inf') if total_profit > 0 else 0

    # Streak statistics
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
    Calculate maximum drawdown

    Args:
        returns: Return series (%)

    Returns:
        Maximum drawdown percentage
    """
    if not returns:
        return 0.0

    # Calculate cumulative NAV curve
    cumulative = [100.0]  # Initial NAV 100
    for r in returns:
        cumulative.append(cumulative[-1] * (1 + r / 100))

    # Calculate historical peak
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
    Calculate consecutive win/loss statistics

    Args:
        returns: Return series

    Returns:
        (max_consecutive_wins, max_consecutive_losses)
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
            # r == 0, don't change streak count
            pass

    return max_wins, max_losses


def calculate_sortino_ratio(returns: List[float], target_return: float = 0) -> float:
    """
    Calculate Sortino ratio (considers only downside risk)

    Args:
        returns: Return series
        target_return: Target return rate

    Returns:
        Sortino ratio
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
    Calculate Calmar ratio (return / max drawdown)

    Args:
        cumulative_return: Cumulative return (%)
        max_drawdown: Maximum drawdown (%)

    Returns:
        Calmar ratio
    """
    if max_drawdown == 0:
        return float('inf') if cumulative_return > 0 else 0

    return cumulative_return / max_drawdown
