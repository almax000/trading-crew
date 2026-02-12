/**
 * TradingCrew Web UI - Type Definitions
 */

// Session status
export type SessionStatus = 'pending' | 'queued' | 'running' | 'completed' | 'error'

// Market type
export type Market = 'A-share' | 'US' | 'HK'

// Model type
export type Model = 'deepseek-v3' | 'qwen3-max' | 'gpt-4o' | 'claude-sonnet-4' | 'deepseek/deepseek-chat-v3-0324'

// Trading decision
export type Decision = 'BUY' | 'SELL' | 'HOLD' | ''

// Session data structure
export interface Session {
  id: string
  ticker: string
  stockName: string
  market: Market
  model: Model
  startDate: string
  endDate: string
  userId: string
  status: SessionStatus
  decision: Decision
  progress: string[]
  reports: Record<string, string>
  createdAt: string
  errorMsg: string
  currentAgent: string
}

// Session list summary (without full reports, optimized for list loading)
export interface SessionSummary {
  id: string
  ticker: string
  stockName: string
  market: Market
  model: Model
  startDate: string
  endDate: string
  userId: string
  status: SessionStatus
  decision: Decision
  progress: string[]
  createdAt: string
  errorMsg: string
  currentAgent: string
  // Queue position (only for queued status)
  queuePosition?: number
}

// User context
export interface UserContext {
  username: string
  isAdmin: boolean
}

// Login request
export interface LoginRequest {
  username: string
  password: string
}

// Login response
export interface LoginResponse {
  success: boolean
  message: string
  username?: string
}

// Ticker validation request
export interface TickerValidateRequest {
  ticker: string
  market: string
}

// Ticker validation response
export interface TickerValidateResponse {
  valid: boolean
  normalized: string
  name: string
  error: string
}

// Create session request
export interface CreateSessionRequest {
  ticker: string
  market: string
  model: string
  startDate: string
  endDate: string
  analysts: string[]
}

// Analysis request (sent to Python service)
export interface AnalyzeRequest {
  ticker: string
  date: string
  market: string
  analysts: string[]
  model: string
}

// Analysis stream response (from Python service - legacy endpoint)
export interface AnalyzeStreamChunk {
  agent: string
  content: string
}

// Token-level streaming response (new endpoint /analyze/stream)
export interface AnalyzeStreamTokenChunk {
  type: 'node_start' | 'token' | 'node_end' | 'heartbeat' | 'complete' | 'error' | 'quota_error' | 'timeout_error'
  agent: string | null
  content: string | null
}

// Config response
export interface ConfigResponse {
  markets: Record<string, string>
  analysts: Record<string, string>
  agentNames: Record<string, string>
  agentOrder: string[]
  datePresets: DatePreset[]
  defaultDates: {
    start: string
    end: string
  }
  isAdmin: boolean
}

// Date preset
export interface DatePreset {
  label: string
  start: string
  end: string
}

// SSE event data
export interface SSEEventData {
  type: 'session_update' | 'heartbeat'
  data?: Session
}
