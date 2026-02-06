# API Documentation

## Analysis Service (FastAPI - Port 8000)

### POST /analyze

Start streaming analysis.

**Request:**
```json
{
  "ticker": "600519",
  "date": "2024-01-15",
  "market": "A-share",
  "analysts": ["market", "social", "news", "fundamentals"]
}
```

**Response (NDJSON stream):**
```json
{"type": "node_start", "agent": "Market Analyst"}
{"type": "token", "agent": "Market Analyst", "content": "..."}
{"type": "node_end", "agent": "Market Analyst", "content": "full report"}
{"type": "complete", "content": "BUY"}
```

### POST /analyze/stream

Token-level streaming analysis (SSE).

**Request:** Same as `/analyze`

**Response:** Server-Sent Events with same payload structure.

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "has_dashscope": true,
  "has_deepseek": false
}
```

---

## Web Service (Bun + Hono - Port 3000)

### POST /api/auth/login

User authentication.

**Request:**
```json
{
  "username": "user1",
  "password": "pass1"
}
```

**Response:**
```json
{
  "success": true,
  "userId": "user1",
  "isAdmin": false
}
```

### GET /api/sessions

List user sessions.

**Response:**
```json
{
  "sessions": [
    {
      "id": "abc123",
      "ticker": "600519",
      "market": "A-share",
      "status": "completed",
      "decision": "BUY",
      "createdAt": "2024-01-15T10:00:00Z"
    }
  ]
}
```

### POST /api/sessions

Create new analysis session.

**Request:**
```json
{
  "ticker": "600519",
  "date": "2024-01-15",
  "market": "A-share",
  "analysts": ["market", "social", "news", "fundamentals"],
  "model": "deepseek-v3"
}
```

**Response:**
```json
{
  "id": "abc123",
  "status": "pending"
}
```

### GET /api/sessions/:id/stream

SSE stream for session progress.

**Response:** Server-Sent Events:
```
event: heartbeat
data: {"type": "heartbeat"}

event: node_start
data: {"type": "node_start", "agent": "Market Analyst"}

event: token
data: {"type": "token", "agent": "Market Analyst", "content": "..."}

event: node_end
data: {"type": "node_end", "agent": "Market Analyst", "content": "full report"}

event: complete
data: {"type": "complete", "decision": "BUY"}
```

### POST /api/sessions/:id/retry

Retry a failed session.

**Response:**
```json
{
  "success": true,
  "id": "abc123"
}
```

### DELETE /api/sessions/:id

Delete a session.

**Response:**
```json
{
  "success": true
}
```

---

## Supported Markets

| Market | Code Format | Data Source | Example |
|--------|-------------|-------------|---------|
| A-share | 6 digits | AKShare | 600519, 000858 |
| US | Letters | yfinance | AAPL, NVDA |
| HK | digits.HK | yfinance | 0700.HK |

## Supported Models

| Model | Provider | Description |
|-------|----------|-------------|
| deepseek-v3 | DashScope | DeepSeek V3 via Alibaba Cloud |
| qwen3-max | DashScope | Qwen3 Max via Alibaba Cloud |
| deepseek-official | DeepSeek | DeepSeek official API |
