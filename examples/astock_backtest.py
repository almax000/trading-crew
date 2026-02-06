#!/usr/bin/env python3
"""
A股回测示例

演示如何使用 TradingCrew 进行 A股模拟回测。

使用方法:
    python examples/astock_backtest.py

环境变量:
    OPENAI_API_KEY: OpenAI API 密钥 (必需)
"""

import os
import sys
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from tradingcrew.astock_config import get_astock_config, ASTOCK_FAST_CONFIG
from tradingcrew.backtest import (
    BacktestRunner,
    get_hs300_constituents,
    get_trading_days_in_range,
)


def demo_single_stock():
    """
    演示: 单只股票回测
    """
    print("\n" + "="*70)
    print("示例 1: 单只股票回测 - 贵州茅台 (600519)")
    print("="*70)

    # 1. 获取 A股配置
    config = get_astock_config(
        llm_provider="openai",
        deep_think_llm="gpt-4o-mini",
        quick_think_llm="gpt-4o-mini",
        max_debate_rounds=1,       # 减少辩论轮数以加快速度
        max_risk_discuss_rounds=1,
    )

    # 2. 创建回测执行器
    runner = BacktestRunner(
        config=config,
        selected_analysts=["market", "news"],  # 只启用市场和新闻分析师
        enable_reflection=True,                 # 启用反思学习
        api_call_delay=2.0,                     # 2秒延迟避免API限制
        debug=False,
    )

    # 3. 执行回测
    # 使用最近2周作为测试
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=14)

    result = runner.run(
        symbol="600519",
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
    )

    # 4. 打印结果
    print(result.metrics)

    # 5. 保存结果
    os.makedirs("backtest_results", exist_ok=True)
    result.save_to_csv("backtest_results/600519_trades.csv")
    result.save_to_json("backtest_results/600519_result.json")

    return result


def demo_multiple_stocks():
    """
    演示: 批量回测多只股票
    """
    print("\n" + "="*70)
    print("示例 2: 批量回测 - 沪深300部分成分股")
    print("="*70)

    # 1. 获取配置 (使用快速配置)
    config = ASTOCK_FAST_CONFIG.copy()
    config["quick_think_llm"] = "gpt-4o-mini"
    config["deep_think_llm"] = "gpt-4o-mini"

    # 2. 创建回测执行器
    runner = BacktestRunner(
        config=config,
        selected_analysts=["market"],  # 只用市场分析师，最快
        enable_reflection=False,       # 批量时关闭反思以加快速度
        api_call_delay=1.5,
        debug=False,
    )

    # 3. 获取沪深300成分股 (取前3只演示)
    hs300 = get_hs300_constituents()[:3]
    print(f"回测标的: {hs300}")

    # 4. 设置日期范围 (最近1周)
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=7)

    # 5. 执行批量回测
    results = runner.run_multiple(
        symbols=hs300,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        output_dir="backtest_results",
    )

    return results


def demo_data_only():
    """
    演示: 仅测试数据获取 (不调用 LLM)
    """
    print("\n" + "="*70)
    print("示例 3: 数据获取测试 (无 LLM 调用)")
    print("="*70)

    from tradingcrew.dataflows.akshare_astock import (
        get_stock_data,
        get_indicators,
        get_news,
    )

    # 测试股票数据
    print("\n1. 获取股票数据 (600519)...")
    stock_data = get_stock_data("600519", "2024-12-01", "2024-12-10")
    print(stock_data[:500] + "..." if len(stock_data) > 500 else stock_data)

    # 测试技术指标
    print("\n2. 获取 MACD 指标...")
    indicators = get_indicators("600519", "macd", "2024-12-10", 30)
    print(indicators[:500] + "..." if len(indicators) > 500 else indicators)

    # 测试新闻
    print("\n3. 获取股票新闻...")
    news = get_news("600519", "2024-12-01", "2024-12-10")
    print(news[:500] + "..." if len(news) > 500 else news)

    # 测试交易日历
    print("\n4. 获取交易日列表...")
    trading_days = get_trading_days_in_range("2024-12-01", "2024-12-15")
    print(f"交易日: {trading_days}")

    # 测试沪深300成分股
    print("\n5. 获取沪深300成分股 (前10只)...")
    hs300 = get_hs300_constituents()[:10]
    print(f"成分股: {hs300}")


def main():
    """主函数"""
    print("\n" + "#"*70)
    print("TradingCrew A股回测示例")
    print("#"*70)

    # 检查 API Key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n警告: 未设置 OPENAI_API_KEY 环境变量")
        print("只能运行数据测试示例")
        demo_data_only()
        return

    # 选择示例
    print("\n请选择要运行的示例:")
    print("  1. 单只股票回测 (贵州茅台)")
    print("  2. 批量回测 (沪深300部分成分股)")
    print("  3. 数据获取测试 (不调用 LLM)")
    print("  q. 退出")

    choice = input("\n请输入选项 [1/2/3/q]: ").strip()

    if choice == "1":
        demo_single_stock()
    elif choice == "2":
        demo_multiple_stocks()
    elif choice == "3":
        demo_data_only()
    elif choice.lower() == "q":
        print("退出")
    else:
        print("无效选项，运行数据测试")
        demo_data_only()


if __name__ == "__main__":
    main()
