# TradingCrew

Multi-agent LLM trading framework with Web GUI and China A-share support.

> Derivative of [TradingAgents](https://github.com/TauricResearch/TradingAgents) (Apache 2.0)
> with added features for Chinese markets.

[中文文档](./README-zh.md)

## Features

- **Multi-agent debate system**: Analysts → Researchers (bull/bear debate) → Trader → Risk team → Decision
- **Web GUI**: Real-time streaming analysis with SSE
- **Multi-market**: A-share (AKShare), US & HK stocks (yfinance)
- **Multi-LLM**: DashScope (DeepSeek-V3, Qwen3), OpenRouter (GPT, Claude, DeepSeek), OpenAI

## Architecture

```
Analysts (4) → Bull/Bear Debate → Research Manager → Trader
                                                       ↓
                              Risk Manager ← Risk Debate (3)
                                    ↓
                            BUY / SELL / HOLD
```

## Quick Start

```bash
# Install Python dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env  # Add your API keys

# Install Web dependencies
cd web && bun install && cd ..

# Start all services
./start-dev.sh
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DASHSCOPE_API_KEY` | Recommended (China) | Alibaba Cloud DashScope |
| `OPENROUTER_API_KEY` | Recommended (Intl) | OpenRouter (400+ models) |
| `OPENAI_API_KEY` | Alternative | OpenAI direct API |
| `INVITE_CODES` | Web | User credentials `user1:pass1,user2:pass2` |
| `ADMIN_USERS` | Web | Admin users `admin1,admin2` |

## API

### Analysis Service (FastAPI - Port 8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analyze` | POST | Streaming analysis (NDJSON) |
| `/analyze/stream` | POST | Token-level streaming (SSE) |
| `/health` | GET | Health check |

### Web Service (Bun + Hono - Port 1788)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | User authentication |
| `/api/sessions` | GET | List user sessions |
| `/api/sessions` | POST | Create analysis session |
| `/api/sessions/:id/stream` | GET | SSE stream for session progress |
| `/api/sessions/:id/retry` | POST | Retry a failed session |
| `/api/sessions/:id` | DELETE | Delete a session |

**Supported markets:** A-share (6 digits, AKShare), US (letters, yfinance), HK (digits.HK, yfinance)

**Supported models:** deepseek-v3, qwen3-max (DashScope), gpt-4o, claude-sonnet-4, deepseek-v3-0324 (OpenRouter)

## Citation

```bibtex
@misc{xiao2025tradingagents,
  title={TradingAgents: Multi-Agents LLM Financial Trading Framework},
  author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
  year={2025},
  eprint={2412.20138},
  archivePrefix={arXiv}
}
```

## License

Apache 2.0 - See [LICENSE](./LICENSE) and [NOTICE](./NOTICE)
