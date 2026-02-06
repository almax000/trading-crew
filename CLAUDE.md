# CLAUDE.md - TradingCrew 项目完全指南

> 本文档为 Claude Code Agent 设计，旨在让新 Agent 快速理解并上手项目。

---

## 一、项目概述

**TradingCrew** 是基于 LangGraph 的多智能体金融交易决策框架，模拟一个交易公司的决策流程：

```
分析师团队 → 研究员辩论 → 交易员 → 风控辩论 → 最终决策 (BUY/SELL/HOLD)
```

### 支持的市场

| 市场 | 代码格式 | 数据源 | 示例 |
|------|---------|--------|------|
| A股 | 6位数字 | AKShare | 600519, 000858 |
| 美股 | 字母代码 | yfinance | AAPL, NVDA |
| 港股 | 数字.HK | yfinance | 0700.HK |

### 技术栈

- **核心框架**: LangGraph (状态机编排)
- **LLM**: 阿里云百炼 (DashScope) / OpenRouter / OpenAI
- **数据源**: AKShare (A股), yfinance (美股/港股), Alpha Vantage
- **Web 服务**: Bun + Hono (TypeScript) + FastAPI (Python)
- **部署**: Railway (Docker)

---

## 二、目录结构

```
trading-crew/
├── tradingcrew/                 # 核心框架
│   ├── graph/                   # LangGraph 图定义
│   │   ├── trading_graph.py     # 主入口类 TradingCrewGraph
│   │   ├── setup.py             # 图构建逻辑
│   │   ├── conditional_logic.py # 条件边判断
│   │   ├── propagation.py       # 状态初始化
│   │   ├── reflection.py        # 反思学习 (已禁用)
│   │   └── signal_processing.py # 信号提取
│   │
│   ├── agents/                  # 智能体定义
│   │   ├── analysts/            # 4个分析师
│   │   │   ├── market_analyst.py        # 技术分析
│   │   │   ├── social_media_analyst.py  # 舆情分析
│   │   │   ├── news_analyst.py          # 新闻分析
│   │   │   └── fundamentals_analyst.py  # 基本面分析
│   │   │
│   │   ├── researchers/         # 研究员辩论
│   │   │   ├── bull_researcher.py  # 多头
│   │   │   └── bear_researcher.py  # 空头
│   │   │
│   │   ├── trader/              # 交易员
│   │   │   └── trader.py
│   │   │
│   │   ├── risk_mgmt/           # 风控辩论
│   │   │   ├── aggresive_debator.py  # 激进派
│   │   │   ├── neutral_debator.py    # 中性派
│   │   │   └── conservative_debator.py # 保守派
│   │   │
│   │   ├── managers/            # 经理 (裁判)
│   │   │   ├── research_manager.py  # 研究经理
│   │   │   └── risk_manager.py      # 风控经理
│   │   │
│   │   ├── utils/               # 工具
│   │   │   ├── agent_states.py      # 状态定义
│   │   │   ├── agent_utils.py       # 数据获取工具
│   │   │   └── memory.py            # ChromaDB 记忆 (已禁用)
│   │   │
│   │   └── prompts/             # 中文提示词
│   │       └── chinese_prompts.py
│   │
│   ├── dataflows/               # 数据层
│   │   ├── interface.py         # 路由接口 (核心)
│   │   ├── config.py            # 配置管理
│   │   ├── akshare_astock.py    # A股数据适配器
│   │   ├── y_finance.py         # yfinance 适配器
│   │   ├── alpha_vantage*.py    # Alpha Vantage 适配器
│   │   └── ...                  # 其他数据源
│   │
│   ├── backtest/                # 回测模块
│   │   ├── runner.py            # 回测运行器
│   │   └── metrics.py           # 绩效指标
│   │
│   ├── default_config.py        # 默认配置
│   ├── market_config.py         # 多市场配置 (重要)
│   └── astock_config.py         # A股专用配置
│
├── analysis_service/            # Python 分析服务 (FastAPI)
│   ├── main.py                  # API 入口
│   └── service.py               # 服务封装
│
├── web/                         # Web 前端 (Bun + Hono)
│   ├── src/
│   │   ├── index.ts             # 入口
│   │   ├── app.ts               # Hono 应用
│   │   ├── config.ts            # 配置
│   │   ├── routes/              # API 路由
│   │   │   ├── sessions.ts      # Session 管理
│   │   │   ├── auth.ts          # 认证
│   │   │   └── ticker.ts        # 股票验证
│   │   └── services/            # 服务
│   │       ├── session-manager.ts   # Session 生命周期
│   │       ├── sse-manager.ts       # SSE 推送
│   │       └── analysis-client.ts   # Python 服务客户端
│   └── static/                  # 静态文件 (HTML/CSS/JS)
│
├── cli/                         # 命令行界面
│   ├── main.py                  # 交互式 CLI
│   └── backtest_tui.py          # 回测 TUI
│
├── Dockerfile                   # 多阶段构建
├── railway.toml                 # Railway 配置
├── requirements.txt             # Python 依赖
└── .env.example                 # 环境变量示例
```

---

## 三、核心架构

### 3.1 执行流程图

```
START
  │
  ├─► Market Analyst ──► tools_market ──┐
  │                                     │
  ├─► Social Analyst ──► tools_social ──┤
  │                                     │
  ├─► News Analyst ──► tools_news ──────┤
  │                                     │
  └─► Fundamentals Analyst ──► tools ───┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │ Bull Researcher │◄──────┐
                               └────────┬────────┘       │
                                        │                │
                                        ▼                │
                               ┌─────────────────┐       │
                               │ Bear Researcher │───────┤
                               └────────┬────────┘       │
                                        │      辩论轮数<N?
                                        ▼
                               ┌─────────────────┐
                               │Research Manager │
                               └────────┬────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │     Trader      │
                               └────────┬────────┘
                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          │                             │                             │
          ▼                             ▼                             ▼
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│  Risky Analyst  │◄────────►│ Neutral Analyst │◄────────►│  Safe Analyst   │
└────────┬────────┘          └────────┬────────┘          └────────┬────────┘
          │                             │                             │
          └─────────────────────────────┼─────────────────────────────┘
                                        │ 讨论轮数<M?
                                        ▼
                               ┌─────────────────┐
                               │  Risk Manager   │
                               └────────┬────────┘
                                        │
                                        ▼
                                       END
                               (BUY / SELL / HOLD)
```

### 3.2 状态结构 (AgentState)

```python
class AgentState(MessagesState):
    # 基本信息
    company_of_interest: str    # 股票代码
    trade_date: str             # 分析日期

    # 分析师报告
    market_report: str          # 技术分析报告
    sentiment_report: str       # 舆情分析报告
    news_report: str            # 新闻分析报告
    fundamentals_report: str    # 基本面分析报告

    # 研究辩论
    investment_debate_state: InvestDebateState  # 多空辩论状态
    investment_plan: str        # 研究经理的投资计划

    # 交易
    trader_investment_plan: str # 交易员的交易方案

    # 风控辩论
    risk_debate_state: RiskDebateState  # 风控辩论状态
    final_trade_decision: str   # 最终决策
```

### 3.3 数据流

```
用户输入: ticker="600519", date="2024-01-15", market="A-share"
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     DataVendor 路由层                             │
│                  (tradingcrew/dataflows/interface.py)            │
│                                                                  │
│  route_to_vendor("get_stock_data", ticker, date)                │
│       │                                                          │
│       ├── A股 → akshare_astock.py                               │
│       ├── 美股 → y_finance.py                                    │
│       └── 失败 → 自动故障转移到下一个 vendor                       │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
                    返回 OHLCV 数据
                           │
                           ▼
              Market Analyst 生成报告
```

---

## 四、关键文件详解

### 4.1 `tradingcrew/graph/trading_graph.py`

**主入口类**，负责:
- 初始化 LLM (支持 DeepSeek/Anthropic/Google/OpenAI)
- 创建工具节点
- 编排整个分析流程

```python
# 核心用法
from tradingcrew.graph.trading_graph import TradingCrewGraph

graph = TradingCrewGraph(
    selected_analysts=["market", "social", "news", "fundamentals"],
    config=config,
)

# 同步执行
final_state, decision = graph.propagate("600519", "2024-01-15")

# 异步流式执行
async for event_type, agent, content in graph.propagate_streaming(ticker, date):
    print(f"{agent}: {content[:50]}...")
```

**重要配置**:
```python
config = {
    "llm_provider": "dashscope",          # LLM 提供商 (dashscope/openrouter/openai)
    "backend_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "deep_think_llm": "deepseek-v3",      # 用于 Manager
    "quick_think_llm": "deepseek-v3",     # 用于 Analyst/Researcher
    "llm_timeout": 300,                   # 超时 (秒)
    "max_debate_rounds": 1,               # 研究辩论轮数
    "max_risk_discuss_rounds": 1,         # 风控讨论轮数
    "data_vendors": {
        "core_stock_apis": "akshare",
        "technical_indicators": "akshare",
        "fundamental_data": "akshare",
        "news_data": "akshare",
    },
}
```

### 4.2 `tradingcrew/dataflows/interface.py`

**数据路由核心**，实现:
- 根据配置选择数据源
- 自动故障转移
- 多数据源聚合

```python
# 调用方式
from tradingcrew.dataflows.interface import route_to_vendor

# 自动根据配置路由到正确的数据源
data = route_to_vendor("get_stock_data", ticker="600519", date="2024-01-15")
```

**数据源优先级** (可配置):
```
A股: akshare → yfinance → local
美股: yfinance → alpha_vantage → local
港股: yfinance → local
```

### 4.3 `tradingcrew/market_config.py`

**多市场配置中心**，提供:
- 不同市场的预设配置
- 不同 LLM 提供商的配置工厂

```python
from tradingcrew.market_config import get_dashscope_config, get_openrouter_config

# 使用阿里云百炼 (中国推荐)
config = get_dashscope_config(market="A-share", model="deepseek-v3")

# 使用 OpenRouter (国际推荐)
config = get_openrouter_config(market="US", model="gpt-4o")
```

### 4.4 `analysis_service/main.py`

**FastAPI 分析服务**，提供:
- `/analyze` - 节点级流式输出
- `/analyze/stream` - Token 级流式输出
- `/health` - 健康检查

**NDJSON 流式协议**:
```json
{"type": "heartbeat", "agent": null, "content": null}
{"type": "node_start", "agent": "Market Analyst", "content": null}
{"type": "token", "agent": "Market Analyst", "content": "分"}
{"type": "token", "agent": "Market Analyst", "content": "析"}
{"type": "node_end", "agent": "Market Analyst", "content": "完整报告..."}
{"type": "complete", "agent": null, "content": "BUY"}
```

### 4.5 `web/src/services/session-manager.ts`

**Session 生命周期管理**:
- 创建/获取/删除 Session
- 排队机制 (每用户限 1 个并发)
- 优雅关闭 (标记中断的 Session)

```typescript
// 核心方法
sessionManager.createSession(params)     // 创建
sessionManager.startSession(id, analysts) // 启动 (支持排队)
sessionManager.getSession(id, userId)    // 获取
sessionManager.retrySession(id)          // 重试
sessionManager.gracefulShutdown()        // 优雅关闭
```

---

## 五、常用命令

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt
cd web && bun install

# 启动 Python 分析服务
python -m uvicorn analysis_service.main:app --host 127.0.0.1 --port 8000

# 启动 Web 服务 (另一个终端)
cd web && bun run src/index.ts

# 或使用旧版全栈模式
python run_gui.py

# 命令行模式
python -m cli.main
python -m cli.backtest_tui  # 回测
```

### Railway 部署

```bash
# 推送并部署
railway up --service trading-crew

# 仅重新部署
railway redeploy --service trading-crew -y

# 查看日志
railway logs --service trading-crew --lines 50

# 环境变量
railway variables --set "DASHSCOPE_API_KEY=your_key"
railway variables --set "INVITE_CODES=user1:pass1,user2:pass2"
railway variables --set "DATA_DIR=/app/data"

# Volume 持久化 (重要!)
railway volume add --mount-path /app/data
```

---

## 六、环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `DASHSCOPE_API_KEY` | 推荐 (中国) | 阿里云百炼 API Key |
| `OPENROUTER_API_KEY` | 推荐 (国际) | OpenRouter API Key (400+ 模型) |
| `OPENAI_API_KEY` | 备选 | OpenAI 直连 API Key |
| `INVITE_CODES` | Web | 用户凭据 `user1:pass1,user2:pass2` |
| `ADMIN_USERS` | Web | 管理员 `user1,user2` |
| `DATA_DIR` | Railway | 必须设为 `/app/data` |
| `ALPHA_VANTAGE_API_KEY` | 可选 | Alpha Vantage (美股数据) |

---

## 七、已知问题与注意事项

### 7.1 已修复的 Bug

1. **risk_manager 数据混淆** (`risk_manager.py:14`)
   - 问题: `fundamentals_report` 错误读取 `state["news_report"]`
   - 状态: 已修复

### 7.2 架构限制

1. **ChromaDB 已禁用**
   - 原因: 并发 Session 导致数据库锁冲突
   - 影响: `reflect_and_remember()` 无效，Agent 没有历史记忆

2. **串行执行**
   - 4 个分析师串行运行，效率较低
   - 每次分析约需 2-5 分钟

3. **Session 排队**
   - 每用户限制 1 个并发任务
   - 多任务会自动排队

### 7.3 部署注意

1. **Railway Volume**
   - 必须创建 Volume 并设置 `DATA_DIR=/app/data`
   - 否则重新部署会丢失 Session 数据

2. **LLM 超时**
   - 默认 300 秒 (5 分钟)
   - 跨境网络可能需要更长

3. **心跳机制**
   - 每 15 秒发送心跳防止连接断开
   - `web/src/index.ts` 设置 `idleTimeout: 255`

---

## 八、扩展指南

### 添加新分析师

1. 在 `tradingcrew/agents/analysts/` 创建新文件
2. 实现 `create_xxx_analyst(llm)` 函数
3. 在 `tradingcrew/agents/__init__.py` 导出
4. 在 `tradingcrew/graph/setup.py` 注册节点
5. 在 `analysis_service/service.py` 添加映射

### 添加新数据源

1. 在 `tradingcrew/dataflows/` 创建适配器
2. 在 `interface.py` 的 `VENDOR_METHODS` 注册
3. 在 `market_config.py` 配置使用

### 添加新市场

1. 在 `market_config.py` 的 `MARKET_INFO` 添加定义
2. 创建对应的数据适配器
3. 在 `get_market_config()` 添加分支

---

## 九、调试技巧

### 查看完整执行日志

```python
graph = TradingCrewGraph(debug=True, config=config)
final_state, decision = graph.propagate("600519", "2024-01-15")
```

### 检查数据源路由

观察控制台输出:
```
DEBUG: get_stock_data - Primary: [akshare] | Full fallback order: [akshare → yfinance → local]
DEBUG: Attempting PRIMARY vendor 'akshare' for get_stock_data (attempt #1)
SUCCESS: get_stock_data from vendor 'akshare' completed successfully
```

### 检查 Session 状态

```bash
# 查看 sessions.json
cat web/data/sessions.json | jq '.[] | {id, status, ticker}'
```

---

## 十、参考资料

- **原始论文**: TradingAgents (arXiv:2412.20138)
- **LangGraph 文档**: https://langchain-ai.github.io/langgraph/
- **AKShare 文档**: https://akshare.akfamily.xyz/
- **Railway 文档**: https://docs.railway.app/
