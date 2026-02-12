/**
 * TradingCrew Web UI - Frontend Application
 * Updated for Bun + Hono backend (camelCase API)
 */

// ============ State ============
const state = {
    loggedIn: false,
    username: '',
    isAdmin: false,
    config: null,
    sessions: [],
    currentSessionId: null,
    eventSource: null,  // SSE connection
    tickerValidateTimeout: null,
    sessionOrder: [],  // User-defined session order
};

// ============ Custom Modal ============
const modal = {
    confirmCallback: null,

    show(title, message, onConfirm) {
        this.confirmCallback = onConfirm;
        document.getElementById('confirm-modal-title').textContent = title;
        document.getElementById('confirm-modal-message').textContent = message;
        document.getElementById('confirm-modal').style.display = 'flex';
    },

    hide() {
        document.getElementById('confirm-modal').style.display = 'none';
        this.confirmCallback = null;
    },

    confirm() {
        if (this.confirmCallback) {
            this.confirmCallback();
        }
        this.hide();
    },

    init() {
        const modalEl = document.getElementById('confirm-modal');
        const cancelBtn = document.getElementById('confirm-modal-cancel');
        const confirmBtn = document.getElementById('confirm-modal-confirm');

        // Cancel button
        cancelBtn.addEventListener('click', () => this.hide());

        // Confirm button
        confirmBtn.addEventListener('click', () => this.confirm());

        // Click overlay to close
        modalEl.addEventListener('click', (e) => {
            if (e.target === modalEl) {
                this.hide();
            }
        });

        // ESC key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modalEl.style.display === 'flex') {
                this.hide();
            }
        });
    }
};

// ============ Session Order (Drag & Drop) ============
function loadSessionOrder() {
    try {
        const saved = localStorage.getItem(`tradingcrew_order_${state.username || 'guest'}`);
        if (saved) {
            state.sessionOrder = JSON.parse(saved);
        }
    } catch (e) {
        console.error('Failed to load session order:', e);
        state.sessionOrder = [];
    }
}

function saveSessionOrder() {
    try {
        localStorage.setItem(
            `tradingcrew_order_${state.username || 'guest'}`,
            JSON.stringify(state.sessionOrder)
        );
    } catch (e) {
        console.error('Failed to save session order:', e);
    }
}

// ============ Font Size ============
function loadFontSize() {
    try {
        const saved = localStorage.getItem('tradingcrew_fontsize');
        if (saved && ['small', 'medium', 'large', 'xlarge'].includes(saved)) {
            applyFontSize(saved);
        } else {
            applyFontSize('medium'); // Default medium
        }
    } catch (e) {
        console.error('Failed to load font size:', e);
    }
}

function saveFontSize(size) {
    try {
        localStorage.setItem('tradingcrew_fontsize', size);
    } catch (e) {
        console.error('Failed to save font size:', e);
    }
}

function applyFontSize(size) {
    // Remove all font size classes
    document.body.classList.remove('font-size-small', 'font-size-medium', 'font-size-large', 'font-size-xlarge');
    // Add new font size class
    document.body.classList.add(`font-size-${size}`);
    // Update button states
    document.querySelectorAll('.font-size-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.size === size);
    });
}

function initFontSizeSelector() {
    document.querySelectorAll('.font-size-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const size = btn.dataset.size;
            applyFontSize(size);
            saveFontSize(size);
        });
    });
}

function sortSessionsByOrder(sessions) {
    if (!state.sessionOrder.length) return sessions;

    // Create sort map
    const orderMap = new Map(state.sessionOrder.map((id, idx) => [id, idx]));

    return [...sessions].sort((a, b) => {
        const orderA = orderMap.has(a.id) ? orderMap.get(a.id) : Infinity;
        const orderB = orderMap.has(b.id) ? orderMap.get(b.id) : Infinity;

        // If both have custom order, sort by order
        if (orderA !== Infinity && orderB !== Infinity) {
            return orderA - orderB;
        }
        // Items with custom order come first
        if (orderA !== Infinity) return -1;
        if (orderB !== Infinity) return 1;
        // Neither has custom order, sort by creation time descending
        return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
    });
}

function setupDragAndDrop() {
    const sessionList = elements.sessionList;
    let draggedItem = null;

    sessionList.addEventListener('dragstart', (e) => {
        const item = e.target.closest('.session-item');
        if (!item) return;

        draggedItem = item;
        item.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', item.dataset.id);
    });

    sessionList.addEventListener('dragend', (e) => {
        const item = e.target.closest('.session-item');
        if (item) {
            item.classList.remove('dragging');
        }
        document.querySelectorAll('.session-item.drag-over').forEach(el => {
            el.classList.remove('drag-over');
        });
        draggedItem = null;
    });

    sessionList.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';

        const target = e.target.closest('.session-item');
        if (!target || target === draggedItem) return;

        // Clear drag-over from other elements
        document.querySelectorAll('.session-item.drag-over').forEach(el => {
            if (el !== target) el.classList.remove('drag-over');
        });

        target.classList.add('drag-over');
    });

    sessionList.addEventListener('dragleave', (e) => {
        const target = e.target.closest('.session-item');
        if (target && !target.contains(e.relatedTarget)) {
            target.classList.remove('drag-over');
        }
    });

    sessionList.addEventListener('drop', (e) => {
        e.preventDefault();
        const target = e.target.closest('.session-item');
        if (!target || !draggedItem || target === draggedItem) return;

        target.classList.remove('drag-over');

        const draggedId = draggedItem.dataset.id;
        const targetId = target.dataset.id;

        // Update order
        const currentOrder = state.sessions.map(s => s.id);
        const draggedIdx = currentOrder.indexOf(draggedId);
        const targetIdx = currentOrder.indexOf(targetId);

        if (draggedIdx !== -1 && targetIdx !== -1) {
            // Remove dragged item
            currentOrder.splice(draggedIdx, 1);
            // Insert at target position
            const newTargetIdx = currentOrder.indexOf(targetId);
            currentOrder.splice(newTargetIdx, 0, draggedId);

            // Save new order
            state.sessionOrder = currentOrder;
            saveSessionOrder();

            // Re-sort and render
            state.sessions = sortSessionsByOrder(state.sessions);
            renderSessionList();
        }
    });
}

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

        // Add user identifier
        if (state.username) {
            options.headers['X-Username'] = state.username;
        }

        if (data) {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(this.baseUrl + path, options);

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || error.error || 'Request failed');
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
    sessionDecision: document.getElementById('session-decision'),
    sessionActions: document.getElementById('session-actions'),
    agentStatus: document.getElementById('agent-status'),
    reportContent: document.getElementById('report-content'),
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

    // Initialize modal
    modal.init();

    // Load saved session order
    loadSessionOrder();

    // Initialize font size selector
    loadFontSize();
    initFontSizeSelector();

    // Show appropriate page
    if (state.loggedIn) {
        await showMainPage();
    } else {
        showLoginPage();
    }

    // Initialization complete, show page (prevent flash)
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

    // Market toggle buttons
    document.querySelectorAll('.market-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.market-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            elements.market.value = btn.dataset.value;
            // Trigger market change
            handleMarketChange();
        });
    });

}

// ============ Form Initialization ============
function initForm() {
    if (!state.config) return;

    // Date presets (camelCase: datePresets)
    const presetsHtml = state.config.datePresets.map((preset, index) => `
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

    // Default dates (camelCase: defaultDates)
    elements.startDate.value = state.config.defaultDates.start;
    elements.endDate.value = state.config.defaultDates.end;

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
        showLoginError(e.message || 'Login failed');
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

    // Reload config to get isAdmin status (now with X-Username header)
    try {
        state.config = await api.getConfig();
        state.isAdmin = state.config.isAdmin || false;
    } catch (e) {
        console.error('Failed to load config:', e);
    }

    // Display username and admin badge
    elements.userDisplay.innerHTML = state.isAdmin
        ? `${state.username} <span class="admin-badge">Admin</span>`
        : state.username;

    // Load sessions
    refreshSessions();
    showNewSessionView();

    // Setup drag and drop after initial render
    setupDragAndDrop();
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

    // Fetch initial state, then connect SSE
    updateSessionDetail().then(() => {
        // If running, connect SSE
        const session = state.sessions.find(s => s.id === sessionId);
        if (session && session.status === 'running') {
            connectSSE(sessionId);
        }
    });
}

// ============ Session Handlers ============
async function handleCreateSession(e) {
    e.preventDefault();

    // camelCase request body
    const formData = {
        ticker: elements.ticker.value.trim(),
        market: elements.market.value,
        model: document.getElementById('model').value,
        startDate: elements.startDate.value,
        endDate: elements.endDate.value,
        analysts: Array.from(document.querySelectorAll('input[name="analysts"]:checked'))
            .map(cb => cb.value),
    };

    try {
        elements.submitBtn.disabled = true;
        elements.submitError.style.display = 'none';

        const session = await api.createSession(formData);

        // Refresh and show detail
        await refreshSessions();

        // Switch to detail view
        elements.newSessionView.style.display = 'none';
        elements.sessionDetailView.style.display = 'block';
        state.currentSessionId = session.id;

        // Render detail and connect SSE (newly created is always running)
        renderSessionDetail(session);
        connectSSE(session.id);

        // Highlight in list
        elements.sessionList.querySelectorAll('.session-item').forEach(item => {
            item.classList.toggle('selected', item.dataset.id === session.id);
        });
    } catch (e) {
        elements.submitError.textContent = e.message || 'Creation failed';
        elements.submitError.style.display = 'block';
        elements.submitBtn.disabled = false;
    }
}

async function refreshSessions() {
    try {
        const sessions = await api.getSessions();
        // Sort by user-defined order
        state.sessions = sortSessionsByOrder(sessions);
        renderSessionList();

        const runningData = await api.getRunningCount();
        elements.runningCount.textContent = `Running: ${runningData.count} sessions`;
    } catch (e) {
        console.error('Failed to refresh sessions:', e);
    }
}

function renderSessionList() {
    if (state.sessions.length === 0) {
        elements.sessionList.innerHTML = '<div class="empty-state">No sessions yet</div>';
        return;
    }

    const marketNames = { 'A-share': 'A-Share', 'US': 'US Stock', 'HK': 'HK Stock' };
    const statusLabels = {
        pending: 'Pending',
        queued: 'Queued',
        running: 'Running',
        completed: 'Completed',
        error: 'Error',
    };
    const decisionLabels = { BUY: 'BUY', SELL: 'SELL', HOLD: 'HOLD' };

    const html = state.sessions.map(session => {
        const statusClass = session.status;
        let statusLabel = statusLabels[session.status] || session.status;

        // Show queue position
        if (session.status === 'queued' && session.queuePosition) {
            statusLabel = `Queue #${session.queuePosition}`;
        }

        const marketName = marketNames[session.market] || session.market;

        let decisionBadge = '';
        if (session.decision) {
            const dec = session.decision.toUpperCase();
            const decClass = dec.toLowerCase();
            const decLabel = decisionLabels[dec] || dec;
            decisionBadge = `<span class="badge badge-${decClass}">${decLabel}</span>`;
        }

        // Admin can see other users' sessions, show owner (camelCase: userId)
        let ownerBadge = '';
        if (state.isAdmin && session.userId && session.userId !== state.username) {
            ownerBadge = `<span class="owner-badge">@${session.userId}</span>`;
        }

        // camelCase fields: stockName, endDate
        return `
            <div class="session-item ${state.currentSessionId === session.id ? 'selected' : ''}"
                 data-id="${session.id}" draggable="true"
                 onclick="window.selectSession('${session.id}')">
                <div class="session-item-content">
                    <div class="session-item-main">
                        <div>
                            <span class="session-ticker">${session.ticker}</span>
                            ${session.stockName ? `<span class="session-name">${session.stockName}</span>` : ''}
                            ${ownerBadge}
                        </div>
                        <div class="session-meta">${marketName} | ${session.endDate}</div>
                        <div class="session-badges">
                            <span class="badge badge-${statusClass}">${statusLabel}</span>
                            ${decisionBadge}
                        </div>
                    </div>
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

window.deleteSession = function(sessionId) {
    // Find session name for display
    const session = state.sessions.find(s => s.id === sessionId);
    const displayName = session ? `${session.ticker} (${session.stockName || session.endDate})` : 'this session';

    modal.show('Confirm Delete', `Are you sure you want to delete ${displayName}?`, async () => {
        try {
            await api.deleteSession(sessionId);

            // If deleted session is currently displayed, go back to new session page
            if (state.currentSessionId === sessionId) {
                showNewSessionView();
            }

            // Refresh list
            await refreshSessions();
        } catch (e) {
            alert('Delete failed: ' + (e.message || 'Unknown error'));
        }
    });
};

window.retrySession = async function(sessionId) {
    try {
        const session = await api.retrySession(sessionId);

        // Refresh list
        await refreshSessions();

        // Show detail and connect SSE
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
        alert('Retry failed: ' + (e.message || 'Unknown error'));
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

    elements.tickerStatus.textContent = 'Validating...';
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
        // Fetch current session details
        const session = await api.getSession(state.currentSessionId);

        // Update current session details
        renderSessionDetail(session);

        // Update list
        await refreshSessions();
    } catch (e) {
        console.error('Failed to update session:', e);
    }
}

// Quiet list refresh (with debounce to avoid request storms)
let refreshDebounceTimer = null;
function refreshSessionListQuiet() {
    // Debounce: execute only once within 500ms
    if (refreshDebounceTimer) {
        return;
    }
    refreshDebounceTimer = setTimeout(() => {
        refreshDebounceTimer = null;
    }, 500);

    Promise.all([
        api.getSessions(),
        api.getRunningCount(),
    ]).then(([sessions, runningData]) => {
        // Sort by user-defined order
        state.sessions = sortSessionsByOrder(sessions);
        renderSessionList();
        elements.runningCount.textContent = `Running: ${runningData.count} sessions`;
    }).catch(e => {
        console.error('Failed to refresh sessions:', e);
    });
}

function renderSessionDetail(session) {
    const marketNames = { 'A-share': 'A-Share', 'US': 'US Stock', 'HK': 'HK Stock' };
    const marketName = marketNames[session.market] || session.market;

    // Header
    elements.sessionHeader.innerHTML = `
        <div class="session-title">${session.ticker}${session.stockName ? ` - ${session.stockName}` : ''}</div>
        <div class="session-meta">${marketName} · ${session.endDate}</div>
    `;

    // Action buttons
    renderSessionActions(session);

    // Decision (only shown when completed or errored)
    renderSessionDecision(session);

    // Agent status (analysis pipeline)
    renderAgentStatus(session);

    // Report content
    renderReportContent(session);
}

function renderSessionActions(session) {
    let html = '';
    if (session.status !== 'running') {
        html += `<button class="action-btn delete" onclick="window.deleteSession('${session.id}')">Delete</button>`;
    }
    elements.sessionActions.innerHTML = html;
}

function renderSessionDecision(session) {
    const decisionLabels = { BUY: 'BUY', SELL: 'SELL', HOLD: 'HOLD' };

    if (session.status === 'completed' && session.decision) {
        const dec = session.decision.toUpperCase();
        const decClass = dec.toLowerCase();
        const decLabel = decisionLabels[dec] || dec;
        elements.sessionDecision.innerHTML = `
            <div class="decision-card ${decClass}">
                <span class="decision-label">Final Recommendation</span>
                <span class="decision-value">${decLabel}</span>
            </div>
        `;
    } else if (session.status === 'error') {
        elements.sessionDecision.innerHTML = `
            <div class="decision-card error">
                <span class="decision-label">Analysis Error</span>
                <button class="retry-btn" onclick="window.retrySession('${session.id}')">Retry</button>
            </div>
        `;
    } else {
        elements.sessionDecision.innerHTML = '';
    }
}

function renderAgentStatus(session) {
    if (!state.config) return;

    // camelCase: agentOrder, agentNames, currentAgent
    const html = state.config.agentOrder.map(agent => {
        const name = state.config.agentNames[agent] || agent;
        const isCompleted = session.progress.includes(agent);
        const isRunning = session.currentAgent === agent;

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
                ${icon} ${name}${isRunning ? ' (in progress)' : ''}
            </div>
        `;
    }).join('');

    elements.agentStatus.innerHTML = html;
}

// HTML escape function
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderReportContent(session) {
    if (!session.reports || Object.keys(session.reports).length === 0) {
        elements.reportContent.innerHTML = '';
        return;
    }

    const sections = state.config.agentOrder
        .filter(agent => session.reports[agent])
        .map(agent => {
            const name = state.config.agentNames[agent] || agent;
            const content = session.reports[agent];
            const isCompleted = session.progress.includes(agent);
            const isStreaming = session.currentAgent === agent;

            if (isCompleted) {
                return `<div class="agent-report">
                    <h3 class="agent-report-header">${name}</h3>
                    <div class="agent-report-content">${marked.parse(content)}</div>
                </div>`;
            } else if (isStreaming) {
                return `<div class="agent-report">
                    <h3 class="agent-report-header streaming">${name}</h3>
                    <div class="agent-report-content">${escapeHtml(content)}<span class="typing-cursor"></span></div>
                </div>`;
            } else {
                return `<div class="agent-report">
                    <h3 class="agent-report-header">${name}</h3>
                    <div class="agent-report-content">${escapeHtml(content)}</div>
                </div>`;
            }
        });

    elements.reportContent.innerHTML = sections.join('');
}

// ============ SSE (Server-Sent Events) ============
function connectSSE(sessionId) {
    disconnectSSE();

    // EventSource doesn't support custom headers, use query param for username
    let url = `/api/sessions/${sessionId}/stream`;
    if (state.username) {
        url += `?username=${encodeURIComponent(state.username)}`;
        if (state.isAdmin) {
            url += `&isAdmin=true`;
        }
    }

    const eventSource = new EventSource(url);

    let lastStatus = null;
    eventSource.onmessage = (event) => {
        try {
            const session = JSON.parse(event.data);
            renderSessionDetail(session);

            // Only refresh list on status change (avoid request storms during token streaming)
            if (session.status !== lastStatus) {
                lastStatus = session.status;
                refreshSessionListQuiet();
            }

            // If completed or errored, close connection
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
        // On connection error, fall back to polling mode
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

// Fall back to polling mode (used when SSE fails)
let pollInterval = null;

function fallbackToPolling() {
    if (pollInterval) return;  // Already polling
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
