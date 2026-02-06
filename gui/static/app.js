/**
 * TradingCrew Web UI - Frontend Application
 */

// ============ State ============
const state = {
    loggedIn: false,
    username: '',
    isAdmin: false,
    config: null,
    sessions: [],
    currentSessionId: null,
    eventSource: null,  // SSE 连接
    tickerValidateTimeout: null,
};

// ============ API Client ============
const api = {
    baseUrl: '',

    async request(method, path, data = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        // 添加用户标识
        if (state.username) {
            options.headers['X-Username'] = state.username;
        }

        if (data) {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(this.baseUrl + path, options);

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || 'Request failed');
        }

        return response.json();
    },

    // Auth
    login: (username, password) => api.request('POST', '/api/auth/login', { username, password }),
    logout: () => api.request('POST', '/api/auth/logout'),

    // Config
    getConfig: () => api.request('GET', '/api/config'),

    // Ticker
    validateTicker: (ticker, market) => api.request('POST', '/api/ticker/validate', { ticker, market }),

    // Sessions
    getSessions: () => api.request('GET', '/api/sessions'),
    getSession: (id) => api.request('GET', `/api/sessions/${id}`),
    createSession: (data) => api.request('POST', '/api/sessions', data),
    deleteSession: (id) => api.request('DELETE', `/api/sessions/${id}`),
    retrySession: (id) => api.request('POST', `/api/sessions/${id}/retry`),
    getRunningCount: () => api.request('GET', '/api/sessions/running/count'),
};

// ============ DOM Elements ============
const elements = {
    // Pages
    loginPage: document.getElementById('login-page'),
    mainPage: document.getElementById('main-page'),

    // Login
    loginForm: document.getElementById('login-form'),
    username: document.getElementById('username'),
    password: document.getElementById('password'),
    loginError: document.getElementById('login-error'),

    // Sidebar
    userDisplay: document.getElementById('user-display'),
    logoutBtn: document.getElementById('logout-btn'),
    newSessionBtn: document.getElementById('new-session-btn'),
    runningCount: document.getElementById('running-count'),
    sessionList: document.getElementById('session-list'),

    // New Session
    newSessionView: document.getElementById('new-session-view'),
    sessionForm: document.getElementById('session-form'),
    market: document.getElementById('market'),
    startDate: document.getElementById('start-date'),
    endDate: document.getElementById('end-date'),
    datePresets: document.getElementById('date-presets'),
    ticker: document.getElementById('ticker'),
    tickerStatus: document.getElementById('ticker-status'),
    analystCheckboxes: document.getElementById('analyst-checkboxes'),
    submitBtn: document.getElementById('submit-btn'),
    submitError: document.getElementById('submit-error'),

    // Session Detail
    sessionDetailView: document.getElementById('session-detail-view'),
    sessionHeader: document.getElementById('session-header'),
    sessionStatus: document.getElementById('session-status'),
    agentStatus: document.getElementById('agent-status'),
    analysisOutput: document.getElementById('analysis-output'),
    reportDetails: document.getElementById('report-details'),
};

// ============ Initialization ============
async function init() {
    // Check localStorage for saved login
    const savedUser = localStorage.getItem('tradingcrew_user');
    if (savedUser) {
        state.username = savedUser;
        state.loggedIn = true;
    }

    // Load config
    try {
        state.config = await api.getConfig();
        initForm();
    } catch (e) {
        console.error('Failed to load config:', e);
    }

    // Bind events
    bindEvents();

    // Show appropriate page
    if (state.loggedIn) {
        await showMainPage();
    } else {
        showLoginPage();
    }

    // 初始化完成，显示页面（防止闪屏）
    document.body.classList.add('loaded');
}

function bindEvents() {
    // Login
    elements.loginForm.addEventListener('submit', handleLogin);
    elements.logoutBtn.addEventListener('click', handleLogout);

    // Session
    elements.newSessionBtn.addEventListener('click', showNewSessionView);
    elements.sessionForm.addEventListener('submit', handleCreateSession);

    // Ticker validation
    elements.ticker.addEventListener('input', handleTickerInput);
    elements.market.addEventListener('change', handleMarketChange);

    // Top tabs
    document.querySelectorAll('.top-tab-btn').forEach(btn => {
        btn.addEventListener('click', handleTopTabClick);
    });
}

function handleTopTabClick(e) {
    const tab = e.target.dataset.tab;

    // Update buttons
    document.querySelectorAll('.top-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });

    // Update content
    document.querySelectorAll('.top-tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tab}`);
    });
}

// ============ Form Initialization ============
function initForm() {
    if (!state.config) return;

    // Date presets
    const presetsHtml = state.config.date_presets.map((preset, index) => `
        <button type="button" class="date-preset ${index === 0 ? 'active' : ''}"
                data-start="${preset.start}" data-end="${preset.end}">
            ${preset.label}
        </button>
    `).join('');
    elements.datePresets.innerHTML = presetsHtml;

    // Bind preset clicks
    elements.datePresets.querySelectorAll('.date-preset').forEach(btn => {
        btn.addEventListener('click', () => {
            elements.datePresets.querySelectorAll('.date-preset').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            elements.startDate.value = btn.dataset.start;
            elements.endDate.value = btn.dataset.end;
        });
    });

    // Default dates
    elements.startDate.value = state.config.default_dates.start;
    elements.endDate.value = state.config.default_dates.end;

    // Analyst checkboxes
    const analystsHtml = Object.entries(state.config.analysts).map(([name, value]) => `
        <label>
            <input type="checkbox" name="analysts" value="${value}" checked>
            ${name}
        </label>
    `).join('');
    elements.analystCheckboxes.innerHTML = analystsHtml;
}

// ============ Auth Handlers ============
async function handleLogin(e) {
    e.preventDefault();

    const username = elements.username.value.trim();
    const password = elements.password.value;

    try {
        const result = await api.login(username, password);

        if (result.success) {
            state.loggedIn = true;
            state.username = username;
            localStorage.setItem('tradingcrew_user', username);
            showMainPage();
        } else {
            showLoginError(result.message);
        }
    } catch (e) {
        showLoginError(e.message || '登录失败');
    }
}

function handleLogout() {
    state.loggedIn = false;
    state.username = '';
    localStorage.removeItem('tradingcrew_user');
    stopPolling();
    showLoginPage();
}

function showLoginError(message) {
    elements.loginError.textContent = message;
    elements.loginError.style.display = 'block';
}

// ============ Page Navigation ============
function showLoginPage() {
    elements.loginPage.style.display = 'flex';
    elements.mainPage.style.display = 'none';
    elements.loginError.style.display = 'none';
    elements.username.value = '';
    elements.password.value = '';
}

async function showMainPage() {
    elements.loginPage.style.display = 'none';
    elements.mainPage.style.display = 'flex';

    // 重新加载配置以获取 isAdmin 状态（因为现在有了 X-Username header）
    try {
        state.config = await api.getConfig();
        state.isAdmin = state.config.is_admin || false;
    } catch (e) {
        console.error('Failed to load config:', e);
    }

    // 显示用户名和管理员标识
    elements.userDisplay.innerHTML = state.isAdmin
        ? `${state.username} <span class="admin-badge">管理员</span>`
        : state.username;

    // Load sessions
    refreshSessions();
    showNewSessionView();
}

function showNewSessionView() {
    elements.newSessionView.style.display = 'block';
    elements.sessionDetailView.style.display = 'none';
    state.currentSessionId = null;

    // Clear form
    elements.ticker.value = '';
    elements.tickerStatus.textContent = '';
    elements.tickerStatus.className = 'ticker-status';
    elements.submitBtn.disabled = true;
    elements.submitError.style.display = 'none';

    // Deselect sessions
    elements.sessionList.querySelectorAll('.session-item').forEach(item => {
        item.classList.remove('selected');
    });
}

function showSessionDetail(sessionId) {
    elements.newSessionView.style.display = 'none';
    elements.sessionDetailView.style.display = 'block';
    state.currentSessionId = sessionId;

    // Highlight in list
    elements.sessionList.querySelectorAll('.session-item').forEach(item => {
        item.classList.toggle('selected', item.dataset.id === sessionId);
    });

    // 先获取一次初始状态，然后连接 SSE
    updateSessionDetail().then(() => {
        // 如果是 running 状态，连接 SSE
        const session = state.sessions.find(s => s.id === sessionId);
        if (session && session.status === 'running') {
            connectSSE(sessionId);
        }
    });
}

// ============ Session Handlers ============
async function handleCreateSession(e) {
    e.preventDefault();

    const formData = {
        ticker: elements.ticker.value.trim(),
        market: elements.market.value,
        start_date: elements.startDate.value,
        end_date: elements.endDate.value,
        analysts: Array.from(document.querySelectorAll('input[name="analysts"]:checked'))
            .map(cb => cb.value),
    };

    try {
        elements.submitBtn.disabled = true;
        elements.submitError.style.display = 'none';

        const session = await api.createSession(formData);

        // Refresh and show detail
        await refreshSessions();

        // 切换到详情视图
        elements.newSessionView.style.display = 'none';
        elements.sessionDetailView.style.display = 'block';
        state.currentSessionId = session.id;

        // 渲染详情并连接 SSE（新创建的一定是 running 状态）
        renderSessionDetail(session);
        connectSSE(session.id);

        // Highlight in list
        elements.sessionList.querySelectorAll('.session-item').forEach(item => {
            item.classList.toggle('selected', item.dataset.id === session.id);
        });
    } catch (e) {
        elements.submitError.textContent = e.message || '创建失败';
        elements.submitError.style.display = 'block';
        elements.submitBtn.disabled = false;
    }
}

async function refreshSessions() {
    try {
        state.sessions = await api.getSessions();
        renderSessionList();

        const runningData = await api.getRunningCount();
        elements.runningCount.textContent = `当前运行: ${runningData.count} 个会话`;
    } catch (e) {
        console.error('Failed to refresh sessions:', e);
    }
}

function renderSessionList() {
    if (state.sessions.length === 0) {
        elements.sessionList.innerHTML = '<div class="empty-state">暂无会话记录</div>';
        return;
    }

    const marketNames = { 'A-share': 'A股', 'US': '美股', 'HK': '港股' };
    const statusLabels = {
        pending: '待运行',
        running: '运行中',
        completed: '已完成',
        error: '出错',
    };
    const decisionLabels = { BUY: '买入', SELL: '卖出', HOLD: '持有' };

    const html = state.sessions.map(session => {
        const statusClass = session.status;
        const statusLabel = statusLabels[session.status] || session.status;
        const marketName = marketNames[session.market] || session.market;

        let decisionBadge = '';
        if (session.decision) {
            const dec = session.decision.toUpperCase();
            const decClass = dec.toLowerCase();
            const decLabel = decisionLabels[dec] || dec;
            decisionBadge = `<span class="badge badge-${decClass}">${decLabel}</span>`;
        }

        // 管理员可以看到其他用户的会话，显示所属用户
        let ownerBadge = '';
        if (state.isAdmin && session.user_id && session.user_id !== state.username) {
            ownerBadge = `<span class="owner-badge">@${session.user_id}</span>`;
        }

        // 操作按钮
        let actionButtons = '';
        if (session.status === 'error') {
            actionButtons += `<button class="session-action-btn retry" onclick="event.stopPropagation(); window.retrySession('${session.id}')" title="重试">↻</button>`;
        }
        if (session.status !== 'running') {
            actionButtons += `<button class="session-action-btn delete" onclick="event.stopPropagation(); window.deleteSession('${session.id}')" title="删除">×</button>`;
        }

        return `
            <div class="session-item ${state.currentSessionId === session.id ? 'selected' : ''}"
                 data-id="${session.id}" onclick="window.selectSession('${session.id}')">
                <div class="session-item-content">
                    <div class="session-item-main">
                        <div>
                            <span class="session-ticker">${session.ticker}</span>
                            ${session.stock_name ? `<span class="session-name">${session.stock_name}</span>` : ''}
                            ${ownerBadge}
                        </div>
                        <div class="session-meta">${marketName} | ${session.end_date}</div>
                        <div class="session-badges">
                            <span class="badge badge-${statusClass}">${statusLabel}</span>
                            ${decisionBadge}
                        </div>
                    </div>
                    ${actionButtons ? `<div class="session-item-actions">${actionButtons}</div>` : ''}
                </div>
            </div>
        `;
    }).join('');

    elements.sessionList.innerHTML = html;
}

// Global functions for onclick
window.selectSession = function(sessionId) {
    showSessionDetail(sessionId);
};

window.deleteSession = async function(sessionId) {
    if (!confirm('确定要删除这个会话吗？')) {
        return;
    }

    try {
        await api.deleteSession(sessionId);

        // 如果删除的是当前显示的会话，返回新建页面
        if (state.currentSessionId === sessionId) {
            showNewSessionView();
        }

        // 刷新列表
        await refreshSessions();
    } catch (e) {
        alert('删除失败: ' + (e.message || '未知错误'));
    }
};

window.retrySession = async function(sessionId) {
    try {
        const session = await api.retrySession(sessionId);

        // 刷新列表
        await refreshSessions();

        // 显示详情并连接 SSE
        elements.newSessionView.style.display = 'none';
        elements.sessionDetailView.style.display = 'block';
        state.currentSessionId = sessionId;
        renderSessionDetail(session);
        connectSSE(sessionId);

        // Highlight in list
        elements.sessionList.querySelectorAll('.session-item').forEach(item => {
            item.classList.toggle('selected', item.dataset.id === sessionId);
        });
    } catch (e) {
        alert('重试失败: ' + (e.message || '未知错误'));
    }
};

// ============ Ticker Validation ============
function handleTickerInput() {
    // Debounce
    clearTimeout(state.tickerValidateTimeout);
    state.tickerValidateTimeout = setTimeout(validateTicker, 300);
}

function handleMarketChange() {
    if (elements.ticker.value.trim()) {
        validateTicker();
    }
}

async function validateTicker() {
    const ticker = elements.ticker.value.trim();
    const market = elements.market.value;

    if (!ticker) {
        elements.tickerStatus.textContent = '';
        elements.tickerStatus.className = 'ticker-status';
        elements.submitBtn.disabled = true;
        return;
    }

    elements.tickerStatus.textContent = '验证中...';
    elements.tickerStatus.className = 'ticker-status validating';

    try {
        const result = await api.validateTicker(ticker, market);

        if (result.valid) {
            const display = result.name
                ? `✓ ${result.normalized} - ${result.name}`
                : `✓ ${result.normalized}`;
            elements.tickerStatus.textContent = display;
            elements.tickerStatus.className = 'ticker-status valid';
            elements.submitBtn.disabled = false;
        } else {
            elements.tickerStatus.textContent = `✗ ${result.error}`;
            elements.tickerStatus.className = 'ticker-status invalid';
            elements.submitBtn.disabled = true;
        }
    } catch (e) {
        elements.tickerStatus.textContent = `✗ ${e.message}`;
        elements.tickerStatus.className = 'ticker-status invalid';
        elements.submitBtn.disabled = true;
    }
}

// ============ Session Detail ============
async function updateSessionDetail() {
    if (!state.currentSessionId) return;

    try {
        // 获取当前 session 详情
        const session = await api.getSession(state.currentSessionId);

        // 更新当前 session 详情
        renderSessionDetail(session);

        // 更新列表
        await refreshSessions();
    } catch (e) {
        console.error('Failed to update session:', e);
    }
}

// 静默刷新列表（不等待完成）
function refreshSessionListQuiet() {
    Promise.all([
        api.getSessions(),
        api.getRunningCount(),
    ]).then(([sessions, runningData]) => {
        state.sessions = sessions;
        renderSessionList();
        elements.runningCount.textContent = `当前运行: ${runningData.count} 个会话`;
    }).catch(e => {
        console.error('Failed to refresh sessions:', e);
    });
}

function renderSessionDetail(session) {
    const marketNames = { 'A-share': 'A股', 'US': '美股', 'HK': '港股' };
    const marketName = marketNames[session.market] || session.market;

    // Header
    elements.sessionHeader.innerHTML = `
        <h2>${session.ticker}${session.stock_name ? ` - ${session.stock_name}` : ''}</h2>
        <div class="meta">
            <strong>市场:</strong> ${marketName} |
            <strong>日期:</strong> ${session.start_date} ~ ${session.end_date}
        </div>
    `;

    // Status
    renderSessionStatus(session);

    // Agent status
    renderAgentStatus(session);

    // 出错的会话：分析过程和报告详情为空
    if (session.status === 'error') {
        elements.analysisOutput.innerHTML = '';
        elements.reportDetails.innerHTML = '';
    } else {
        // Analysis output
        renderAnalysisOutput(session);

        // Report details
        renderReportDetails(session);
    }
}


function renderSessionStatus(session) {
    const decisionLabels = { BUY: '买入', SELL: '卖出', HOLD: '持有' };

    if (session.status === 'completed' && session.decision) {
        const dec = session.decision.toUpperCase();
        const decClass = dec.toLowerCase();
        const decLabel = decisionLabels[dec] || dec;
        elements.sessionStatus.innerHTML = `
            <div class="decision-box ${decClass}">
                ${decLabel} (${dec})
            </div>
        `;
    } else if (session.status === 'error') {
        elements.sessionStatus.innerHTML = `
            <div class="session-status-box error">
                <strong>分析出错</strong><br>
                ${session.error_msg}
            </div>
        `;
    } else if (session.status === 'running') {
        const currentAgent = state.config?.agent_names[session.current_agent] || session.current_agent;
        elements.sessionStatus.innerHTML = `
            <div class="session-status-box running">
                <strong>分析进行中</strong> - 当前: ${currentAgent}
            </div>
        `;
    } else {
        elements.sessionStatus.innerHTML = `
            <div class="session-status-box pending">
                <strong>待运行</strong>
            </div>
        `;
    }
}

function renderAgentStatus(session) {
    if (!state.config) return;

    const html = state.config.agent_order.map(agent => {
        const name = state.config.agent_names[agent] || agent;
        const isCompleted = session.progress.includes(agent);
        const isRunning = session.current_agent === agent;

        let icon = '⬜';
        let statusClass = 'pending';

        if (isCompleted) {
            icon = '✅';
            statusClass = 'completed';
        } else if (isRunning) {
            icon = '⏳';
            statusClass = 'running';
        }

        return `
            <div class="agent-item ${statusClass}">
                ${icon} ${name}${isRunning ? ' (进行中)' : ''}
            </div>
        `;
    }).join('');

    elements.agentStatus.innerHTML = html;
}

function renderAnalysisOutput(session) {
    if (!session.reports || Object.keys(session.reports).length === 0) {
        if (session.status === 'running') {
            elements.analysisOutput.innerHTML = '分析进行中，请稍候...';
        } else {
            elements.analysisOutput.innerHTML = '等待分析开始...';
        }
        return;
    }

    const sections = state.config.agent_order
        .filter(agent => session.reports[agent])
        .map(agent => {
            const name = state.config.agent_names[agent] || agent;
            const content = session.reports[agent];
            return `<h2>${name}</h2>\n${marked.parse(content)}`;
        });

    elements.analysisOutput.innerHTML = sections.join('<hr>');
}

function renderReportDetails(session) {
    if (!session.reports || Object.keys(session.reports).length === 0) {
        elements.reportDetails.innerHTML = '暂无报告';
        return;
    }

    const sections = state.config.agent_order
        .filter(agent => session.reports[agent])
        .map(agent => {
            const name = state.config.agent_names[agent] || agent;
            const content = session.reports[agent];
            return `<h3>${name}</h3>\n${marked.parse(content)}`;
        });

    elements.reportDetails.innerHTML = sections.join('<hr>');
}

// ============ SSE (Server-Sent Events) ============
function connectSSE(sessionId) {
    disconnectSSE();

    // EventSource 不支持自定义 header，用 query param 传递用户名
    let url = `/api/sessions/${sessionId}/stream`;
    if (state.username) {
        url += `?username=${encodeURIComponent(state.username)}`;
    }

    const eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
        try {
            const session = JSON.parse(event.data);
            renderSessionDetail(session);

            // 更新列表中的状态
            refreshSessionListQuiet();

            // 如果完成或出错，关闭连接
            if (session.status === 'completed' || session.status === 'error') {
                disconnectSSE();
                refreshSessions();
            }
        } catch (e) {
            console.error('SSE parse error:', e);
        }
    };

    eventSource.onerror = (event) => {
        console.error('SSE error:', event);
        // 连接出错时，回退到轮询模式
        disconnectSSE();
        fallbackToPolling();
    };

    state.eventSource = eventSource;
}

function disconnectSSE() {
    if (state.eventSource) {
        state.eventSource.close();
        state.eventSource = null;
    }
}

// 回退到轮询模式（SSE 失败时使用）
let pollInterval = null;

function fallbackToPolling() {
    if (pollInterval) return;  // 已经在轮询
    console.log('Falling back to polling mode');
    pollInterval = setInterval(async () => {
        if (!state.currentSessionId) {
            clearInterval(pollInterval);
            pollInterval = null;
            return;
        }
        try {
            const session = await api.getSession(state.currentSessionId);
            renderSessionDetail(session);
            if (session.status === 'completed' || session.status === 'error') {
                clearInterval(pollInterval);
                pollInterval = null;
                refreshSessions();
            }
        } catch (e) {
            console.error('Polling error:', e);
        }
    }, 4000);
}

function stopPolling() {
    disconnectSSE();
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

// ============ Start App ============
document.addEventListener('DOMContentLoaded', init);
