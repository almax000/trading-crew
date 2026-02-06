"""
TradingCrew Web UI - Session 管理界面

类似 AI Chat 产品的界面：左侧 Session 列表，右侧 Session 详情。
支持多个 Session 并发运行、自定义登录页面、股票代码实时验证。
"""

import gradio as gr
import json
from datetime import datetime
from typing import List, Tuple, Optional

from .config import (
    INVITE_CODES,
    WEB_PORT,
    MARKET_OPTIONS,
    ANALYST_OPTIONS,
    AGENT_DISPLAY_NAMES,
    AGENT_ORDER,
    SESSION_STATUS_DISPLAY,
    DECISION_DISPLAY,
    get_date_presets,
    get_default_dates,
)
from .auth import authenticate, create_session, clear_session, is_logged_in
from .ticker_validator import validate_ticker_format, validate_and_get_name
from .session_manager import (
    get_session_manager,
    Session,
    SessionStatus,
)
from .analysis_service import AnalysisService


def create_app() -> gr.Blocks:
    """创建 Gradio 应用"""

    # CSS 样式
    custom_css = """
    /* 全局布局 */
    .main-container {
        min-height: 100vh;
    }

    /* 侧边栏样式 */
    .sidebar {
        background: #f8f9fa;
        border-right: 1px solid #e9ecef;
        min-height: calc(100vh - 60px);
    }

    .sidebar-header {
        padding: 16px;
        border-bottom: 1px solid #e9ecef;
        background: #fff;
    }

    .user-info {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }

    .user-name {
        font-weight: bold;
        font-size: 14px;
    }

    /* Session 列表 */
    .session-list {
        padding: 8px;
        max-height: calc(100vh - 200px);
        overflow-y: auto;
    }

    .session-item {
        padding: 12px;
        margin: 4px 0;
        border-radius: 8px;
        cursor: pointer;
        background: #fff;
        border: 1px solid #e9ecef;
        transition: all 0.2s;
    }

    .session-item:hover {
        background: #e9ecef;
        border-color: #dee2e6;
    }

    .session-item.selected {
        background: #e7f1ff;
        border-color: #0d6efd;
    }

    .session-ticker {
        font-weight: bold;
        font-size: 15px;
        color: #212529;
    }

    .session-name {
        font-size: 12px;
        color: #6c757d;
        margin-left: 6px;
    }

    .session-meta {
        font-size: 11px;
        color: #6c757d;
        margin-top: 4px;
    }

    .session-status {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: bold;
    }

    .session-status.pending { background: #e9ecef; color: #6c757d; }
    .session-status.running { background: #fff3cd; color: #856404; }
    .session-status.completed { background: #d4edda; color: #155724; }
    .session-status.error { background: #f8d7da; color: #721c24; }

    .session-decision {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: bold;
        margin-left: 6px;
    }

    .session-decision.buy { background: #d4edda; color: #155724; }
    .session-decision.sell { background: #f8d7da; color: #721c24; }
    .session-decision.hold { background: #cce5ff; color: #004085; }

    /* 新建按钮 */
    .new-session-btn {
        width: 100%;
        margin-bottom: 12px;
    }

    /* 主内容区 */
    .main-content {
        padding: 20px;
        background: #fff;
    }

    /* 表单样式 */
    .form-section {
        background: #f8f9fa;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 20px;
    }

    /* 验证状态 */
    .ticker-valid {
        color: #28a745;
        font-weight: bold;
    }

    .ticker-invalid {
        color: #dc3545;
        font-weight: bold;
    }

    .ticker-validating {
        color: #6c757d;
        font-style: italic;
    }

    /* Agent 状态面板 */
    .agent-status {
        font-size: 14px;
        line-height: 1.8;
    }

    .status-pending { color: #888; }
    .status-running { color: #f0ad4e; }
    .status-done { color: #5cb85c; }

    /* 决策显示 */
    .decision-box {
        font-size: 24px;
        font-weight: bold;
        padding: 20px;
        text-align: center;
        border-radius: 10px;
        margin: 10px 0;
    }

    .decision-buy {
        color: #155724;
        background: #d4edda;
        border: 2px solid #28a745;
    }

    .decision-sell {
        color: #721c24;
        background: #f8d7da;
        border: 2px solid #dc3545;
    }

    .decision-hold {
        color: #004085;
        background: #cce5ff;
        border: 2px solid #17a2b8;
    }

    /* 分析输出 */
    .analysis-output {
        max-height: 600px;
        overflow-y: auto;
    }

    /* 登录页面 */
    .login-container {
        max-width: 400px;
        margin: 100px auto;
        padding: 40px;
        background: #fff;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }

    .login-title {
        text-align: center;
        margin-bottom: 30px;
    }

    .login-error {
        color: #dc3545;
        text-align: center;
        margin-top: 10px;
    }

    /* 空状态 */
    .empty-state {
        text-align: center;
        color: #6c757d;
        padding: 60px 20px;
    }

    .empty-state-icon {
        font-size: 48px;
        margin-bottom: 16px;
    }
    """

    with gr.Blocks(
        title="TradingCrew 智能交易分析",
        css=custom_css,
        theme=gr.themes.Soft(),
    ) as app:

        # ========== 状态变量 ==========
        session_state = gr.State(value={"logged_in": False, "username": ""})
        current_session_id = gr.State(value="")
        sessions_data = gr.State(value=[])  # Session 列表数据

        # ========== 登录页面 ==========
        with gr.Column(visible=True, elem_classes=["login-container"]) as login_area:
            gr.Markdown(
                """
                <div class="login-title">
                    <h1>TradingCrew</h1>
                    <p>多 Agent 协作的 AI 交易分析系统</p>
                </div>
                """,
                elem_classes=["login-title"],
            )

            login_username = gr.Textbox(
                label="用户名",
                placeholder="请输入用户名",
                interactive=True,
            )

            login_password = gr.Textbox(
                label="密码",
                placeholder="请输入密码",
                type="password",
                interactive=True,
            )

            login_btn = gr.Button("登录", variant="primary", size="lg")

            login_error = gr.Markdown(visible=False, elem_classes=["login-error"])

        # ========== 主界面（登录后显示） ==========
        with gr.Row(visible=False, elem_classes=["main-container"]) as main_area:

            # ===== 左侧侧边栏 =====
            with gr.Column(scale=1, min_width=280, elem_classes=["sidebar"]):
                # 用户信息
                with gr.Row(elem_classes=["sidebar-header"]):
                    user_display = gr.Markdown("**用户**: 未登录")
                    logout_btn = gr.Button("登出", size="sm", variant="secondary")

                # 新建会话按钮
                new_session_btn = gr.Button(
                    "+ 新建会话",
                    variant="primary",
                    elem_classes=["new-session-btn"],
                )

                # 运行中计数
                running_count = gr.Markdown("*当前运行: 0 个会话*")

                # Session 列表
                gr.Markdown("### 会话列表")
                session_list_html = gr.HTML(
                    value='<div class="empty-state">暂无会话记录</div>',
                    elem_id="session-list",
                )

            # ===== 右侧主内容区 =====
            with gr.Column(scale=3, elem_classes=["main-content"]):

                # == 视图1: 新建会话表单 ==
                with gr.Column(visible=True) as new_session_view:
                    gr.Markdown("## 新建分析会话")

                    with gr.Row():
                        # 市场选择
                        market_dropdown = gr.Dropdown(
                            choices=list(MARKET_OPTIONS.keys()),
                            value="A股",
                            label="市场",
                            interactive=True,
                            scale=1,
                        )

                    with gr.Row():
                        # 日期范围
                        start_date = gr.Textbox(
                            label="开始日期",
                            value=get_default_dates()[0],
                            placeholder="YYYY-MM-DD",
                            interactive=True,
                            scale=1,
                        )
                        end_date = gr.Textbox(
                            label="结束日期",
                            value=get_default_dates()[1],
                            placeholder="YYYY-MM-DD",
                            interactive=True,
                            scale=1,
                        )

                    # 日期预设快捷选择
                    date_presets = get_date_presets()
                    preset_choices = [p["label"] for p in date_presets]
                    date_preset_radio = gr.Radio(
                        choices=preset_choices,
                        label="快捷选择",
                        value="最近一周",
                        interactive=True,
                    )

                    # 股票代码输入
                    ticker_input = gr.Textbox(
                        label="股票代码",
                        placeholder="例如: 600519 (A股), AAPL (美股), 0700 (港股)",
                        interactive=True,
                    )
                    # 验证状态
                    ticker_status = gr.Markdown(
                        value="",
                        elem_classes=["ticker-status"],
                    )

                    # 高级选项
                    with gr.Accordion("高级选项", open=False):
                        analyst_checkbox = gr.CheckboxGroup(
                            choices=list(ANALYST_OPTIONS.keys()),
                            value=list(ANALYST_OPTIONS.keys()),
                            label="启用的分析师",
                            interactive=True,
                        )

                    # 提交按钮
                    submit_btn = gr.Button(
                        "开始分析",
                        variant="primary",
                        size="lg",
                        interactive=False,  # 初始禁用，验证通过后启用
                    )

                    submit_error = gr.Markdown(visible=False)

                # == 视图2: Session 详情 ==
                with gr.Column(visible=False) as session_detail_view:
                    # 返回按钮
                    back_btn = gr.Button("< 返回新建", size="sm", variant="secondary")

                    # Session 信息头
                    session_header = gr.Markdown("## Session 详情")

                    # 状态和决策
                    session_status_display = gr.Markdown("")

                    # Agent 状态面板
                    gr.Markdown("### Agent 进度")
                    agent_status_md = gr.Markdown(
                        value=_render_agent_status(set(), None),
                        elem_classes=["agent-status"],
                    )

                    # 分析内容
                    with gr.Tabs():
                        with gr.Tab("分析过程"):
                            analysis_output = gr.Markdown(
                                value="等待分析开始...",
                                elem_classes=["analysis-output"],
                            )

                        with gr.Tab("各报告详情"):
                            report_details = gr.Markdown(
                                value="分析完成后显示各 Agent 的详细报告",
                            )

        # ========== 隐藏的状态同步元素 ==========
        session_list_data = gr.Textbox(visible=False, elem_id="session-list-data")
        refresh_trigger = gr.Number(visible=False, value=0)

        # ========== 事件处理函数 ==========

        def do_login(username: str, password: str, state: dict):
            """处理登录"""
            success, message = authenticate(username, password)
            if success:
                new_state = create_session(username)
                return (
                    new_state,
                    gr.update(visible=False),  # login_area
                    gr.update(visible=True),   # main_area
                    f"**用户**: {username}",   # user_display
                    gr.update(visible=False),  # login_error
                )
            else:
                return (
                    state,
                    gr.update(visible=True),   # login_area
                    gr.update(visible=False),  # main_area
                    "",                        # user_display
                    gr.update(value=message, visible=True),  # login_error
                )

        def do_logout(state: dict):
            """处理登出"""
            new_state = clear_session()
            return (
                new_state,
                gr.update(visible=True),   # login_area
                gr.update(visible=False),  # main_area
                "",                        # user_display
                "",                        # login_username
                "",                        # login_password
            )

        def on_date_preset_change(preset_label: str):
            """日期预设变化"""
            presets = get_date_presets()
            for p in presets:
                if p["label"] == preset_label:
                    return p["start"], p["end"]
            return get_default_dates()

        def on_ticker_change(ticker: str, market_name: str):
            """股票代码输入变化时验证"""
            if not ticker.strip():
                return "", gr.update(interactive=False)

            market = MARKET_OPTIONS.get(market_name, "A-share")
            is_valid, normalized, error = validate_ticker_format(ticker, market)

            if is_valid:
                # 格式正确，尝试获取名称
                try:
                    success, _, name = validate_and_get_name(ticker, market)
                    if success and name:
                        return (
                            f'<span class="ticker-valid">✓ {normalized} - {name}</span>',
                            gr.update(interactive=True),
                        )
                    elif success:
                        return (
                            f'<span class="ticker-valid">✓ {normalized}</span>',
                            gr.update(interactive=True),
                        )
                    else:
                        return (
                            f'<span class="ticker-invalid">✗ {name}</span>',
                            gr.update(interactive=False),
                        )
                except Exception:
                    # 名称查询失败，但格式正确
                    return (
                        f'<span class="ticker-valid">✓ {normalized}</span>',
                        gr.update(interactive=True),
                    )
            else:
                return (
                    f'<span class="ticker-invalid">✗ {error}</span>',
                    gr.update(interactive=False),
                )

        def on_market_change(market_name: str, ticker: str):
            """市场变化时重新验证"""
            if ticker.strip():
                return on_ticker_change(ticker, market_name)
            return "", gr.update(interactive=False)

        def create_and_start_session(
            ticker: str,
            market_name: str,
            start: str,
            end: str,
            analysts_names: List[str],
        ):
            """创建并启动 Session"""
            market = MARKET_OPTIONS.get(market_name, "A-share")

            # 验证股票
            is_valid, normalized, name_or_error = validate_and_get_name(ticker, market)
            if not is_valid:
                return (
                    gr.update(visible=True),   # new_session_view
                    gr.update(visible=False),  # session_detail_view
                    "",                        # current_session_id
                    gr.update(value=f"**错误**: {name_or_error}", visible=True),
                    0,                         # refresh_trigger
                )

            # 创建 Session
            manager = get_session_manager()
            session = manager.create_session(
                ticker=normalized,
                stock_name=name_or_error if is_valid else "",
                market=market,
                start_date=start,
                end_date=end,
            )

            # 转换分析师名称
            selected_analysts = [
                ANALYST_OPTIONS[name]
                for name in analysts_names
                if name in ANALYST_OPTIONS
            ]

            # 启动 Session
            manager.start_session(session.id, selected_analysts)

            # 切换到详情视图
            return (
                gr.update(visible=False),  # new_session_view
                gr.update(visible=True),   # session_detail_view
                session.id,                # current_session_id
                gr.update(visible=False),  # submit_error
                1,                         # refresh_trigger (触发刷新)
            )

        def show_new_session_view():
            """显示新建会话视图"""
            return (
                gr.update(visible=True),   # new_session_view
                gr.update(visible=False),  # session_detail_view
                "",                        # current_session_id
            )

        def show_session_detail(session_id: str):
            """显示 Session 详情"""
            if not session_id:
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    "",
                    "",
                    "",
                    "",
                    "",
                )

            manager = get_session_manager()
            session = manager.get_session(session_id)

            if not session:
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    "",
                    "",
                    "",
                    "",
                    "",
                )

            market_display = {"A-share": "A股", "US": "美股", "HK": "港股"}.get(
                session.market, session.market
            )

            header = f"## {session.ticker}"
            if session.stock_name:
                header += f" - {session.stock_name}"
            header += f"\n\n**市场**: {market_display} | **日期**: {session.start_date} ~ {session.end_date}"

            status_html = _render_session_status(session)
            agent_status = _render_agent_status(set(session.progress), session.current_agent)
            analysis_text = _render_analysis_content(session)
            reports_text = _render_reports(session.reports)

            return (
                gr.update(visible=False),  # new_session_view
                gr.update(visible=True),   # session_detail_view
                header,                    # session_header
                status_html,               # session_status_display
                agent_status,              # agent_status_md
                analysis_text,             # analysis_output
                reports_text,              # report_details
            )

        def refresh_session_list(trigger: int):
            """刷新 Session 列表"""
            manager = get_session_manager()
            sessions = manager.get_all_sessions()
            running = manager.get_running_count()

            list_html = _render_session_list(sessions)
            running_text = f"*当前运行: {running} 个会话*"

            return list_html, running_text

        def poll_session_updates(session_id: str, trigger: int):
            """轮询 Session 更新"""
            if not session_id:
                return (
                    "",
                    "",
                    "",
                    "",
                    trigger,
                    "",
                    "*当前运行: 0 个会话*",
                )

            manager = get_session_manager()
            session = manager.get_session(session_id)

            if not session:
                return (
                    "",
                    "",
                    "",
                    "",
                    trigger,
                    "",
                    "*当前运行: 0 个会话*",
                )

            status_html = _render_session_status(session)
            agent_status = _render_agent_status(set(session.progress), session.current_agent)
            analysis_text = _render_analysis_content(session)
            reports_text = _render_reports(session.reports)

            # 刷新列表
            sessions = manager.get_all_sessions()
            running = manager.get_running_count()
            list_html = _render_session_list(sessions)
            running_text = f"*当前运行: {running} 个会话*"

            # 如果还在运行，继续触发刷新
            new_trigger = trigger + 1 if session.status == SessionStatus.RUNNING else trigger

            return (
                status_html,
                agent_status,
                analysis_text,
                reports_text,
                new_trigger,
                list_html,
                running_text,
            )

        # ========== 绑定事件 ==========

        # 登录
        login_btn.click(
            fn=do_login,
            inputs=[login_username, login_password, session_state],
            outputs=[session_state, login_area, main_area, user_display, login_error],
        )

        # 密码框回车登录
        login_password.submit(
            fn=do_login,
            inputs=[login_username, login_password, session_state],
            outputs=[session_state, login_area, main_area, user_display, login_error],
        )

        # 登出
        logout_btn.click(
            fn=do_logout,
            inputs=[session_state],
            outputs=[session_state, login_area, main_area, user_display, login_username, login_password],
        )

        # 日期预设变化
        date_preset_radio.change(
            fn=on_date_preset_change,
            inputs=[date_preset_radio],
            outputs=[start_date, end_date],
        )

        # 股票代码验证
        ticker_input.change(
            fn=on_ticker_change,
            inputs=[ticker_input, market_dropdown],
            outputs=[ticker_status, submit_btn],
        )

        # 市场变化时重新验证
        market_dropdown.change(
            fn=on_market_change,
            inputs=[market_dropdown, ticker_input],
            outputs=[ticker_status, submit_btn],
        )

        # 新建会话按钮
        new_session_btn.click(
            fn=show_new_session_view,
            outputs=[new_session_view, session_detail_view, current_session_id],
        )

        # 返回新建按钮
        back_btn.click(
            fn=show_new_session_view,
            outputs=[new_session_view, session_detail_view, current_session_id],
        )

        # 提交分析
        submit_btn.click(
            fn=create_and_start_session,
            inputs=[ticker_input, market_dropdown, start_date, end_date, analyst_checkbox],
            outputs=[new_session_view, session_detail_view, current_session_id, submit_error, refresh_trigger],
        )

        # 刷新触发时更新 Session 状态
        refresh_trigger.change(
            fn=poll_session_updates,
            inputs=[current_session_id, refresh_trigger],
            outputs=[
                session_status_display,
                agent_status_md,
                analysis_output,
                report_details,
                refresh_trigger,
                session_list_html,
                running_count,
            ],
            every=2,  # 每 2 秒轮询一次
        )

        # 页面加载时初始化
        app.load(
            fn=lambda: refresh_session_list(0),
            outputs=[session_list_html, running_count],
        )

    return app


# ========== 渲染辅助函数 ==========

def _render_session_list(sessions: List[Session]) -> str:
    """渲染 Session 列表 HTML"""
    if not sessions:
        return '<div class="empty-state">暂无会话记录</div>'

    items = []
    for session in sessions:
        market_display = {"A-share": "A股", "US": "美股", "HK": "港股"}.get(
            session.market, session.market
        )

        # 状态
        status_label, status_color = SESSION_STATUS_DISPLAY.get(
            session.status.value, ("未知", "#888")
        )
        status_class = session.status.value

        # 决策
        decision_html = ""
        if session.decision:
            dec = session.decision.upper()
            if dec in DECISION_DISPLAY:
                dec_label, _, dec_class = DECISION_DISPLAY[dec]
                decision_html = f'<span class="session-decision {dec_class}">{dec_label}</span>'

        # 名称
        name_html = ""
        if session.stock_name:
            name_html = f'<span class="session-name">{session.stock_name}</span>'

        items.append(f'''
        <div class="session-item" onclick="selectSession('{session.id}')">
            <div>
                <span class="session-ticker">{session.ticker}</span>
                {name_html}
            </div>
            <div class="session-meta">
                {market_display} | {session.end_date}
            </div>
            <div style="margin-top: 4px;">
                <span class="session-status {status_class}">{status_label}</span>
                {decision_html}
            </div>
        </div>
        ''')

    return "".join(items)


def _render_session_status(session: Session) -> str:
    """渲染 Session 状态"""
    status_label, status_color = SESSION_STATUS_DISPLAY.get(
        session.status.value, ("未知", "#888")
    )

    if session.status == SessionStatus.COMPLETED and session.decision:
        dec = session.decision.upper()
        if dec in DECISION_DISPLAY:
            dec_label, dec_color, dec_class = DECISION_DISPLAY[dec]
            return f'''
<div class="decision-box decision-{dec_class}">
    {dec_label} ({dec})
</div>
'''

    elif session.status == SessionStatus.ERROR:
        return f'''
<div style="padding: 16px; background: #f8d7da; color: #721c24; border-radius: 8px;">
    <strong>分析出错</strong><br>
    {session.error_msg}
</div>
'''

    elif session.status == SessionStatus.RUNNING:
        current = AGENT_DISPLAY_NAMES.get(session.current_agent, session.current_agent)
        return f'''
<div style="padding: 16px; background: #fff3cd; color: #856404; border-radius: 8px;">
    <strong>分析进行中</strong> - 当前: {current}
</div>
'''

    else:
        return f'''
<div style="padding: 16px; background: #e9ecef; color: #6c757d; border-radius: 8px;">
    <strong>{status_label}</strong>
</div>
'''


def _render_agent_status(completed: set, current: Optional[str] = None) -> str:
    """渲染 Agent 状态面板"""
    lines = []
    for agent in AGENT_ORDER:
        display_name = AGENT_DISPLAY_NAMES.get(agent, agent)
        if agent in completed:
            lines.append(f"✅ {display_name}")
        elif agent == current:
            lines.append(f"⏳ **{display_name}** (进行中)")
        else:
            lines.append(f"⬜ {display_name}")
    return "\n".join(lines)


def _render_analysis_content(session: Session) -> str:
    """渲染分析内容"""
    if not session.reports:
        if session.status == SessionStatus.RUNNING:
            return "分析进行中，请稍候..."
        return "等待分析开始..."

    sections = []
    for agent in AGENT_ORDER:
        if agent in session.reports:
            display_name = AGENT_DISPLAY_NAMES.get(agent, agent)
            content = session.reports[agent]
            sections.append(f"## {display_name}\n\n{content}")

    return "\n\n---\n\n".join(sections)


def _render_reports(reports: dict) -> str:
    """渲染各报告详情"""
    if not reports:
        return "暂无报告"

    sections = []
    for agent in AGENT_ORDER:
        if agent in reports:
            display_name = AGENT_DISPLAY_NAMES.get(agent, agent)
            content = reports[agent]
            sections.append(f"### {display_name}\n\n{content}")

    return "\n\n---\n\n".join(sections)


def launch_app(
    server_name: str = "0.0.0.0",
    server_port: int = None,
    share: bool = False,
):
    """
    启动 Web UI

    Args:
        server_name: 服务器地址
        server_port: 服务端口 (默认使用配置中的 WEB_PORT)
        share: 是否创建公共链接
    """
    app = create_app()

    port = server_port or WEB_PORT

    print(f"\nTradingCrew Web UI 启动中...")
    print(f"地址: http://{server_name}:{port}")
    print(f"认证: 自定义登录页面 ({len(INVITE_CODES)} 个邀请码)")
    print()

    app.launch(
        server_name=server_name,
        server_port=port,
        share=share,
    )


if __name__ == "__main__":
    launch_app()
