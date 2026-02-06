"""
TradingCrew 多市场回测 TUI 输入处理工具

提供用户输入的验证和处理功能
支持 A股、美股、港股市场
"""

import re
from typing import List, Tuple, Optional
from datetime import datetime
from pathlib import Path

import questionary
from rich.console import Console
from rich.table import Table

from cli.history_manager import (
    get_stock_history,
    add_stock_to_history,
    get_favorite_stocks,
    get_date_presets,
    get_date_history,
    add_date_to_history,
    get_last_market,
)

console = Console()

# 市场信息
MARKET_INFO = {
    "A-share": {
        "name": "A股",
        "name_en": "A-Share (China)",
        "code_format": "6位数字 (如 600519, 000001)",
        "code_example": ["600519", "000858", "300750"],
    },
    "US": {
        "name": "美股",
        "name_en": "US Stock",
        "code_format": "字母代码 (如 AAPL, MSFT)",
        "code_example": ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"],
    },
    "HK": {
        "name": "港股",
        "name_en": "HK Stock",
        "code_format": "数字.HK (如 0700.HK, 9988.HK)",
        "code_example": ["0700.HK", "9988.HK", "0005.HK"],
    },
}

# Questionary 样式
QUESTIONARY_STYLE = questionary.Style([
    ("text", "fg:green"),
    ("highlighted", "noinherit"),
    ("selected", "fg:green noinherit"),
    ("pointer", "noinherit"),
    ("checkbox-selected", "fg:green"),
])


def validate_date(date_str: str) -> bool:
    """验证日期格式 YYYY-MM-DD"""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return False
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_a_share_code(code: str) -> bool:
    """
    验证 A 股代码格式

    规则:
    - 6位数字
    - 上海: 600xxx, 601xxx, 603xxx, 605xxx, 688xxx (科创板)
    - 深圳: 000xxx, 001xxx, 002xxx (中小板), 300xxx (创业板)
    """
    code = code.strip()
    if not re.match(r"^\d{6}$", code):
        return False

    prefix = code[:3]
    valid_prefixes = ["600", "601", "603", "605", "688", "000", "001", "002", "300"]
    return prefix in valid_prefixes


def validate_us_stock_code(code: str) -> bool:
    """
    验证美股代码格式

    规则:
    - 1-5 个大写字母
    - 可选: 带 . 的类别标识 (如 BRK.B, BRK-B)
    """
    code = code.strip().upper()
    # 标准股票代码: 1-5 个字母
    if re.match(r"^[A-Z]{1,5}$", code):
        return True
    # 带类别的代码: 如 BRK.B, BRK-B
    if re.match(r"^[A-Z]{1,4}[.\-][A-Z]$", code):
        return True
    return False


def validate_hk_stock_code(code: str) -> bool:
    """
    验证港股代码格式

    规则:
    - 4-5 位数字 + .HK 后缀
    - 例如: 0700.HK, 9988.HK, 00005.HK
    """
    code = code.strip().upper()
    # 标准格式: 数字.HK
    if re.match(r"^\d{4,5}\.HK$", code):
        return True
    # 也接受纯数字 (自动补 .HK)
    if re.match(r"^\d{4,5}$", code):
        return True
    return False


def normalize_stock_code(code: str, market: str) -> str:
    """
    标准化股票代码

    Args:
        code: 原始代码
        market: 市场类型

    Returns:
        标准化后的代码
    """
    code = code.strip()

    if market == "US":
        return code.upper()
    elif market == "HK":
        code = code.upper()
        if not code.endswith(".HK"):
            code = code + ".HK"
        # 补齐前导零 (如 700 -> 0700)
        parts = code.split(".")
        if len(parts[0]) < 4:
            parts[0] = parts[0].zfill(4)
        return ".".join(parts)
    else:
        return code


def validate_stock_code(code: str, market: str) -> bool:
    """
    根据市场验证股票代码

    Args:
        code: 股票代码
        market: 市场类型 ("A-share", "US", "HK")

    Returns:
        是否有效
    """
    if market == "A-share":
        return validate_a_share_code(code)
    elif market == "US":
        return validate_us_stock_code(code)
    elif market == "HK":
        return validate_hk_stock_code(code)
    else:
        return False


def select_market() -> str:
    """
    选择市场

    Returns:
        市场类型 ("A-share", "US", "HK")
    """
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]       TradingCrew 多市场回测          [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print()

    # 获取上次使用的市场
    last_market = get_last_market()

    # 构建选项，把上次使用的放在前面
    market_choices = [
        ("🇨🇳 A股 (沪深股票)", "A-share"),
        ("🇺🇸 美股 (NYSE/NASDAQ)", "US"),
        ("🇭🇰 港股 (香港交易所)", "HK"),
    ]

    # 重新排序，上次使用的在前
    choices = []
    for label, value in market_choices:
        if value == last_market:
            choices.insert(0, questionary.Choice(f"{label} [上次]", value=value))
        else:
            choices.append(questionary.Choice(label, value=value))

    market = questionary.select(
        "选择市场:",
        choices=choices,
        style=QUESTIONARY_STYLE,
    ).ask()

    if not market:
        return "A-share"  # 默认 A 股

    market_info = MARKET_INFO.get(market, {})
    console.print(f"\n[green]已选择: {market_info.get('name', market)}[/green]")
    console.print(f"[dim]代码格式: {market_info.get('code_format', '')}[/dim]")
    console.print(f"[dim]示例: {', '.join(market_info.get('code_example', []))}[/dim]")

    return market


def parse_stock_codes(input_str: str) -> List[str]:
    """
    解析股票代码输入

    支持格式:
    - 单个: 600519
    - 多个 (逗号分隔): 600519,000858,601318
    - 多个 (空格分隔): 600519 000858 601318
    - 文件 (@前缀): @stocks.txt
    """
    input_str = input_str.strip()

    # 文件输入
    if input_str.startswith("@"):
        file_path = Path(input_str[1:])
        if not file_path.exists():
            console.print(f"[red]文件不存在: {file_path}[/red]")
            return []
        codes = []
        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    codes.append(line)
        return codes

    # 分隔符处理
    if "," in input_str:
        codes = [c.strip() for c in input_str.split(",")]
    elif " " in input_str:
        codes = input_str.split()
    else:
        codes = [input_str]

    return [c for c in codes if c]


def get_stock_codes(market: str = "A-share") -> List[str]:
    """
    获取股票代码输入

    Args:
        market: 市场类型 ("A-share", "US", "HK")

    Returns:
        验证过的股票代码列表
    """
    market_info = MARKET_INFO.get(market, MARKET_INFO["A-share"])

    # 获取历史记录
    history = get_stock_history(market)
    favorites = get_favorite_stocks(market)

    console.print(f"\n[bold cyan]{market_info['name']}股票代码选择[/bold cyan]")

    # 显示历史记录
    if favorites:
        console.print("\n[dim]最近使用:[/dim]")
        for i, item in enumerate(favorites[:5], 1):
            name_str = f" ({item['name']})" if item['name'] else ""
            console.print(f"  [{i}] {item['code']}{name_str}")

    console.print(f"\n[dim]格式: {market_info['code_format']}[/dim]")
    console.print("[dim]输入数字选择历史记录，或直接输入新代码[/dim]")
    console.print()

    while True:
        # 构建输入提示
        default_hint = history[0] if history else ""

        answer = questionary.text(
            "请输入股票代码:",
            default=default_hint,
            style=QUESTIONARY_STYLE,
        ).ask()

        if not answer:
            console.print("[red]已取消[/red]")
            return []

        answer = answer.strip()

        # 检查是否是数字选择
        if answer.isdigit():
            idx = int(answer) - 1
            if 0 <= idx < len(favorites):
                answer = favorites[idx]["code"]
                console.print(f"[green]已选择: {answer}[/green]")

        codes = parse_stock_codes(answer)

        if not codes:
            console.print("[red]未解析到有效的股票代码，请重试[/red]")
            continue

        # 验证每个代码
        valid_codes = []
        invalid_codes = []

        for code in codes:
            if validate_stock_code(code, market):
                # 标准化代码
                normalized = normalize_stock_code(code, market)
                valid_codes.append(normalized)
            else:
                invalid_codes.append(code)

        if invalid_codes:
            console.print(f"[yellow]以下代码格式无效: {', '.join(invalid_codes)}[/yellow]")
            console.print(f"[dim]预期格式: {market_info['code_format']}[/dim]")

        if valid_codes:
            console.print(f"[green]有效股票代码: {', '.join(valid_codes)}[/green]")

            confirm = questionary.confirm(
                f"确认使用这 {len(valid_codes)} 只股票进行回测?",
                default=True,
                style=QUESTIONARY_STYLE,
            ).ask()

            if confirm:
                # 保存到历史记录
                add_stock_to_history(market, valid_codes)
                return valid_codes
        else:
            console.print("[red]没有有效的股票代码，请重试[/red]")


def get_backtest_date_range() -> Tuple[str, str]:
    """
    获取回测日期范围

    返回 (开始日期, 结束日期) 元组
    """
    console.print("\n[bold cyan]选择回测日期范围[/bold cyan]")

    # 获取预设和历史
    presets = get_date_presets()
    history = get_date_history()

    # 构建选项
    choices = []

    # 添加预设选项
    for preset in presets:
        label = f"{preset['label']} ({preset['start']} ~ {preset['end']})"
        choices.append(questionary.Choice(label, value=preset))

    # 添加历史记录
    if history:
        choices.append(questionary.Separator("── 历史记录 ──"))
        for h in history[:3]:
            if h not in presets:
                label = f"{h.get('label', '自定义')} ({h['start']} ~ {h['end']})"
                choices.append(questionary.Choice(label, value=h))

    # 添加自定义选项
    choices.append(questionary.Separator("────────────"))
    choices.append(questionary.Choice("📅 自定义日期范围...", value="custom"))

    # 选择
    selection = questionary.select(
        "选择日期范围:",
        choices=choices,
        style=QUESTIONARY_STYLE,
    ).ask()

    if not selection:
        console.print("[red]已取消[/red]")
        return ("", "")

    # 处理选择
    if selection == "custom":
        # 自定义输入
        console.print("\n[dim]日期格式: YYYY-MM-DD[/dim]")

        start_date = questionary.text(
            "请输入开始日期:",
            validate=lambda x: validate_date(x.strip()) or "请输入有效的日期格式 (YYYY-MM-DD)",
            style=QUESTIONARY_STYLE,
        ).ask()

        if not start_date:
            console.print("[red]已取消[/red]")
            return ("", "")

        start_date = start_date.strip()

        end_date = questionary.text(
            "请输入结束日期:",
            validate=lambda x: validate_date(x.strip()) or "请输入有效的日期格式 (YYYY-MM-DD)",
            style=QUESTIONARY_STYLE,
        ).ask()

        if not end_date:
            console.print("[red]已取消[/red]")
            return ("", "")

        end_date = end_date.strip()

        # 验证日期顺序
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        if start_dt > end_dt:
            console.print("[yellow]开始日期晚于结束日期，已自动交换[/yellow]")
            start_date, end_date = end_date, start_date

        # 保存到历史
        add_date_to_history(start_date, end_date, "自定义")

    else:
        # 使用预设/历史
        start_date = selection["start"]
        end_date = selection["end"]
        console.print(f"[green]已选择: {start_date} ~ {end_date}[/green]")

    return (start_date, end_date)


def select_llm_config() -> dict:
    """
    选择 LLM 配置

    返回配置字典
    """
    console.print("\n[bold cyan]LLM 配置[/bold cyan]")
    console.print()

    # 选择提供商
    provider = questionary.select(
        "选择 LLM 提供商:",
        choices=[
            questionary.Choice("DashScope 百炼 (推荐, DeepSeek/Qwen)", value="dashscope"),
            questionary.Choice("OpenRouter (国际, 400+ 模型)", value="openrouter"),
            questionary.Choice("OpenAI", value="openai"),
            questionary.Choice("Ollama (本地)", value="ollama"),
        ],
        style=QUESTIONARY_STYLE,
    ).ask()

    if not provider:
        return {}

    # 选择分析深度
    depth = questionary.select(
        "选择分析深度:",
        choices=[
            questionary.Choice("快速 (1轮辩论)", value=1),
            questionary.Choice("标准 (2轮辩论, 推荐)", value=2),
            questionary.Choice("深度 (3轮辩论)", value=3),
        ],
        style=QUESTIONARY_STYLE,
    ).ask()

    if not depth:
        return {}

    return {
        "llm_provider": provider,
        "max_debate_rounds": depth,
        "max_risk_discuss_rounds": depth,
    }


def select_analysts() -> List[str]:
    """
    选择分析师团队

    返回选中的分析师列表
    """
    ANALYST_OPTIONS = [
        ("市场分析师 (技术指标)", "market"),
        ("舆情分析师 (社交媒体)", "social"),
        ("新闻分析师 (新闻资讯)", "news"),
        ("基本面分析师 (财务数据)", "fundamentals"),
    ]

    choices = questionary.checkbox(
        "选择分析师团队:",
        choices=[
            questionary.Choice(display, value=value, checked=True)
            for display, value in ANALYST_OPTIONS
        ],
        instruction="\n  Space: 选择/取消  |  a: 全选/取消全选  |  Enter: 确认",
        validate=lambda x: len(x) > 0 or "请至少选择一个分析师",
        style=QUESTIONARY_STYLE,
    ).ask()

    if not choices:
        return ["market"]  # 默认至少有市场分析师

    return choices


def select_output_mode() -> bool:
    """
    选择输出模式

    返回 True 表示完整输出模式，False 表示简洁面板模式
    """
    console.print("\n[bold cyan]输出模式[/bold cyan]")
    console.print()

    mode = questionary.select(
        "选择输出模式:",
        choices=[
            questionary.Choice("完整输出 (显示每个 Agent 的完整报告，推荐)", value=True),
            questionary.Choice("简洁面板 (仅显示摘要，适合快速查看)", value=False),
        ],
        style=QUESTIONARY_STYLE,
    ).ask()

    if mode is None:
        return True  # 默认完整输出

    return mode


def confirm_backtest_settings(
    stocks: List[str],
    start_date: str,
    end_date: str,
    llm_config: dict,
    analysts: List[str],
    market: str = "A-share",
) -> bool:
    """
    确认回测设置

    显示设置摘要并请求确认

    Args:
        stocks: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        llm_config: LLM 配置
        analysts: 分析师列表
        market: 市场类型
    """
    market_info = MARKET_INFO.get(market, {})

    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]           回测设置确认                 [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]")

    console.print(f"\n[bold]市场:[/bold] {market_info.get('name', market)} ({market})")
    console.print(f"[bold]股票:[/bold] {', '.join(stocks)} ({len(stocks)} 只)")
    console.print(f"[bold]日期范围:[/bold] {start_date} 至 {end_date}")
    console.print(f"[bold]LLM 提供商:[/bold] {llm_config.get('llm_provider', 'dashscope')}")
    console.print(f"[bold]辩论轮数:[/bold] {llm_config.get('max_debate_rounds', 2)}")

    analyst_names = {
        "market": "市场分析师",
        "social": "舆情分析师",
        "news": "新闻分析师",
        "fundamentals": "基本面分析师",
    }
    analyst_display = [analyst_names.get(a, a) for a in analysts]
    console.print(f"[bold]分析师:[/bold] {', '.join(analyst_display)}")

    console.print()

    return questionary.confirm(
        "确认开始回测?",
        default=True,
        style=QUESTIONARY_STYLE,
    ).ask()
