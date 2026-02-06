# TradingCrew

Multi-agent LLM trading framework with Web GUI and China A-share support.

> Derivative of [TradingAgents](https://github.com/TauricResearch/TradingAgents) (Apache 2.0)
> with added features for Chinese markets.

[中文文档](./README-zh.md) | [API Docs](./docs/API.md)

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
# Install
pip install -r requirements.txt
cp .env.example .env  # Add your API keys

# CLI
python -m cli.main

# Web (requires Bun)
cd web && bun install
bun run src/index.ts
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DASHSCOPE_API_KEY` | Recommended (China) | Alibaba Cloud DashScope |
| `OPENROUTER_API_KEY` | Recommended (Intl) | OpenRouter (400+ models) |
| `OPENAI_API_KEY` | Alternative | OpenAI direct API |

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
