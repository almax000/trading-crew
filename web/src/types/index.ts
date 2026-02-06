/**
 * TradingCrew Web UI - Type Definitions
 */

// Session 状态
export type SessionStatus = 'pending' | 'queued' | 'running' | 'completed' | 'error'

// 市场类型
export type Market = 'A-share' | 'US' | 'HK'

// 模型类型
export type Model = 'deepseek-v3' | 'qwen3-max'

// 交易决策
export type Decision = 'BUY' | 'SELL' | 'HOLD' | ''

// Session 数据结构
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

// Session 列表摘要（不含完整报告，用于优化列表加载）
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
  // 队列位置（仅 queued 状态有值）
  queuePosition?: number
}

// 用户上下文
export interface UserContext {
  username: string
  isAdmin: boolean
}

// 登录请求
export interface LoginRequest {
  username: string
  password: string
}

// 登录响应
export interface LoginResponse {
  success: boolean
  message: string
  username?: string
}

// 股票验证请求
export interface TickerValidateRequest {
  ticker: string
  market: string
}

// 股票验证响应
export interface TickerValidateResponse {
  valid: boolean
  normalized: string
  name: string
  error: string
}

// 创建 Session 请求
export interface CreateSessionRequest {
  ticker: string
  market: string
  model: string
  startDate: string
  endDate: string
  analysts: string[]
}

// 分析请求（发送给 Python 服务）
export interface AnalyzeRequest {
  ticker: string
  date: string
  market: string
  analysts: string[]
  model: string
}

// 分析流式响应（从 Python 服务 - 旧端点）
export interface AnalyzeStreamChunk {
  agent: string
  content: string
}

// Token-level streaming response (新端点 /analyze/stream)
export interface AnalyzeStreamTokenChunk {
  type: 'node_start' | 'token' | 'node_end' | 'heartbeat' | 'complete' | 'error' | 'quota_error' | 'timeout_error'
  agent: string | null
  content: string | null
}

// 配置响应
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

// 日期预设
export interface DatePreset {
  label: string
  start: string
  end: string
}

// SSE 事件数据
export interface SSEEventData {
  type: 'session_update' | 'heartbeat'
  data?: Session
}
