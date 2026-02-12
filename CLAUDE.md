# CLAUDE.md - TradingCrew Project Guide

> This document is designed for Claude Code agents to quickly understand and work with the project.

---

## 1. Project Overview

**TradingCrew** is a multi-agent financial trading decision framework based on LangGraph, simulating a trading firm's decision-making process:

```
Analyst Team → Researcher Debate → Trader → Risk Debate → Final Decision (BUY/SELL/HOLD)
```

### Supported Markets

| Market | Code Format | Data Source | Examples |
|--------|-------------|-------------|----------|
| A-Share (China) | 6-digit number | AKShare | 600519, 000858 |
| US Stock | Letter ticker | yfinance | AAPL, NVDA |
| HK Stock | Number.HK | yfinance | 0700.HK |

### Tech Stack

- **Core Framework**: LangGraph (state machine orchestration)
- **LLM**: Alibaba Cloud DashScope / OpenRouter / OpenAI
- **Data Sources**: AKShare (A-Share), yfinance (US/HK), Alpha Vantage
- **Web Service**: Bun + Hono (TypeScript) + FastAPI (Python)

---

## 2. Directory Structure

```
trading-crew/
├── tradingcrew/                 # Core framework
│   ├── graph/                   # LangGraph graph definitions
│   │   ├── trading_graph.py     # Main entry class TradingCrewGraph
│   │   ├── setup.py             # Graph construction logic
│   │   ├── conditional_logic.py # Conditional edge logic
│   │   ├── propagation.py       # State initialization
│   │   ├── reflection.py        # Reflection learning (disabled)
│   │   └── signal_processing.py # Signal extraction
│   │
│   ├── agents/                  # Agent definitions
│   │   ├── analysts/            # 4 analysts
│   │   ├── researchers/         # Bull/bear debate
│   │   ├── trader/              # Trader
│   │   ├── risk_mgmt/           # Risk debate (3 styles)
│   │   ├── managers/            # Research/Risk managers
│   │   ├── utils/               # Utilities
│   │   └── prompts/             # Prompt templates
│   │
│   ├── dataflows/               # Data layer
│   │   ├── interface.py         # Routing interface (core)
│   │   ├── config.py            # Config management
│   │   ├── akshare_astock.py    # A-Share data adapter
│   │   ├── y_finance.py         # yfinance adapter
│   │   └── alpha_vantage*.py    # Alpha Vantage adapter
│   │
│   ├── backtest/                # Backtesting module
│   ├── default_config.py        # Default config
│   ├── market_config.py         # Multi-market config
│   └── astock_config.py         # A-Share specific config
│
├── analysis_service/            # Python analysis service (FastAPI)
│   ├── main.py                  # API entry point
│   └── service.py               # Service wrapper
│
├── web/                         # Web frontend (Bun + Hono)
│   ├── src/
│   │   ├── index.ts             # Entry point
│   │   ├── app.ts               # Hono application
│   │   ├── config.ts            # Configuration
│   │   ├── routes/              # API routes
│   │   └── services/            # Services
│   └── static/                  # Static files (HTML/CSS/JS)
│
├── start-dev.sh                 # Dev startup script
├── requirements.txt             # Python deps
├── .env.example                 # Config template
├── README.md                    # English readme
└── README-zh.md                 # Chinese readme
```

---

## 3. Core Architecture

### 3.1 Execution Flow

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
                                        │   debate rounds<N?
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
                                        │ discussion rounds<M?
                                        ▼
                               ┌─────────────────┐
                               │  Risk Manager   │
                               └────────┬────────┘
                                        │
                                        ▼
                                       END
                               (BUY / SELL / HOLD)
```

### 3.2 Data Flow

```
User input: ticker="600519", date="2024-01-15", market="A-share"
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     DataVendor Routing Layer                     │
│                  (tradingcrew/dataflows/interface.py)            │
│                                                                  │
│  route_to_vendor("get_stock_data", ticker, date)                │
│       │                                                          │
│       ├── A-Share → akshare_astock.py                           │
│       ├── US Stock → y_finance.py                               │
│       └── Failure → Auto-failover to next vendor                │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Common Commands

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt
cd web && bun install

# Start all services
./start-dev.sh

# Or start individually:
# Python analysis service
python -m uvicorn analysis_service.main:app --host 127.0.0.1 --port 8000

# Web service (another terminal)
cd web && bun run src/index.ts
```

---

## 5. Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DASHSCOPE_API_KEY` | Recommended (China) | Alibaba Cloud DashScope API Key |
| `OPENROUTER_API_KEY` | Recommended (International) | OpenRouter API Key (400+ models) |
| `OPENAI_API_KEY` | Alternative | OpenAI direct API Key |
| `INVITE_CODES` | Web | User credentials `user1:pass1,user2:pass2` |
| `ADMIN_USERS` | Web | Admins `user1,user2` |
| `ALPHA_VANTAGE_API_KEY` | Optional | Alpha Vantage (US stock data) |

---

## 6. Known Issues and Notes

### 6.1 Architecture Limitations

1. **ChromaDB Disabled** — Concurrent sessions cause database lock conflicts. `reflect_and_remember()` is a no-op.
2. **Sequential Execution** — 4 analysts run sequentially, each taking 2-5 minutes.
3. **Session Queuing** — 1 concurrent task per user, additional tasks auto-queued.

### 6.2 LLM Timeout

Default 300 seconds. Cross-border networks may need longer.

---

## 7. Extension Guide

### Adding a New Analyst

1. Create file in `tradingcrew/agents/analysts/`
2. Implement `create_xxx_analyst(llm)` function
3. Export in `tradingcrew/agents/__init__.py`
4. Register node in `tradingcrew/graph/setup.py`
5. Add mapping in `analysis_service/service.py`

### Adding a New Data Source

1. Create adapter in `tradingcrew/dataflows/`
2. Register in `interface.py`'s `VENDOR_METHODS`
3. Configure in `market_config.py`

---

## 8. References

- **Original Paper**: TradingAgents (arXiv:2412.20138)
- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **AKShare Docs**: https://akshare.akfamily.xyz/
