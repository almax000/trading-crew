/**
 * Session Manager - Session 生命周期管理
 *
 * 管理 Session 的创建、执行、状态跟踪。
 * 支持并发执行多个 Session，数据持久化到 JSON 文件。
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs'
import { join, dirname } from 'path'
import type { Session, SessionStatus, SessionSummary, Market, Model, AnalyzeRequest } from '../types'
import { DATA_DIR, AGENT_ORDER } from '../config'
import { sseManager } from './sse-manager'
import { analysisClient } from './analysis-client'

// Session 存储文件路径
const SESSIONS_FILE = join(DATA_DIR, 'sessions.json')

// 生成短 ID
function generateId(): string {
  return Math.random().toString(36).substring(2, 10)
}

// 获取下一个 Agent
function getNextAgent(currentAgent: string): string {
  const idx = AGENT_ORDER.indexOf(currentAgent)
  if (idx >= 0 && idx + 1 < AGENT_ORDER.length) {
    return AGENT_ORDER[idx + 1]
  }
  return ''
}

export class SessionManager {
  private sessions: Map<string, Session> = new Map()
  private runningTasks: Map<string, AbortController> = new Map()

  /**
   * 从文件加载 Sessions
   */
  loadSessions(): void {
    if (!existsSync(SESSIONS_FILE)) {
      return
    }

    try {
      const data = JSON.parse(readFileSync(SESSIONS_FILE, 'utf-8'))
      for (const sessionData of data) {
        const session = this.parseSession(sessionData)
        // 如果之前是 running 状态，标记为 error（服务器重启）
        if (session.status === 'running') {
          session.status = 'error'
          session.errorMsg = '服务器重启，分析中断'
          session.currentAgent = ''
        }
        this.sessions.set(session.id, session)
      }
      console.log(`Loaded ${this.sessions.size} sessions from disk`)
    } catch (e) {
      console.error('Failed to load sessions:', e)
    }
  }

  /**
   * 保存 Sessions 到文件
   */
  private saveSessions(): void {
    try {
      // 确保目录存在
      const dir = dirname(SESSIONS_FILE)
      if (!existsSync(dir)) {
        mkdirSync(dir, { recursive: true })
      }

      const data = Array.from(this.sessions.values())
      writeFileSync(SESSIONS_FILE, JSON.stringify(data, null, 2), 'utf-8')
    } catch (e) {
      console.error('Failed to save sessions:', e)
    }
  }

  /**
   * 解析 Session 数据
   */
  private parseSession(data: any): Session {
    return {
      id: data.id || generateId(),
      ticker: data.ticker || '',
      stockName: data.stock_name || data.stockName || '',
      market: data.market || 'A-share',
      model: data.model || 'deepseek-v3',
      startDate: data.start_date || data.startDate || '',
      endDate: data.end_date || data.endDate || '',
      userId: data.user_id || data.userId || '',
      status: data.status || 'pending',
      decision: data.decision || '',
      progress: data.progress || [],
      reports: data.reports || {},
      createdAt: data.created_at || data.createdAt || new Date().toISOString(),
      errorMsg: data.error_msg || data.errorMsg || '',
      currentAgent: data.current_agent || data.currentAgent || '',
    }
  }

  /**
   * 创建新 Session
   */
  createSession(params: {
    ticker: string
    stockName: string
    market: Market
    model: Model
    startDate: string
    endDate: string
    userId: string
  }): Session {
    const session: Session = {
      id: generateId(),
      ticker: params.ticker,
      stockName: params.stockName,
      market: params.market,
      model: params.model,
      startDate: params.startDate,
      endDate: params.endDate,
      userId: params.userId,
      status: 'pending',
      decision: '',
      progress: [],
      reports: {},
      createdAt: new Date().toISOString().replace('T', ' ').substring(0, 19),
      errorMsg: '',
      currentAgent: '',
    }

    this.sessions.set(session.id, session)
    this.saveSessions()

    return session
  }

  /**
   * 获取 Session
   */
  getSession(sessionId: string, userId?: string, isAdmin?: boolean): Session | null {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return null
    }

    // 管理员可以访问所有 session
    if (isAdmin) {
      return session
    }

    // 普通用户只能访问自己的 session
    if (userId && session.userId && session.userId !== userId) {
      return null
    }

    return session
  }

  /**
   * 获取所有 Sessions（按创建时间降序）
   */
  getAllSessions(userId?: string, isAdmin?: boolean): Session[] {
    let sessions: Session[]

    if (isAdmin) {
      sessions = Array.from(this.sessions.values())
    } else if (userId) {
      sessions = Array.from(this.sessions.values()).filter(s => s.userId === userId)
    } else {
      sessions = Array.from(this.sessions.values()).filter(s => !s.userId)
    }

    return sessions.sort((a, b) =>
      new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    )
  }

  /**
   * 获取所有 Sessions 的摘要（不含 reports，用于优化列表加载）
   */
  getAllSessionSummaries(userId?: string, isAdmin?: boolean): SessionSummary[] {
    const sessions = this.getAllSessions(userId, isAdmin)

    // 计算每个用户的队列位置
    const userQueuePositions = new Map<string, number>()

    return sessions.map(session => {
      const summary: SessionSummary = {
        id: session.id,
        ticker: session.ticker,
        stockName: session.stockName,
        market: session.market,
        model: session.model,
        startDate: session.startDate,
        endDate: session.endDate,
        userId: session.userId,
        status: session.status,
        decision: session.decision,
        progress: session.progress,
        createdAt: session.createdAt,
        errorMsg: session.errorMsg,
        currentAgent: session.currentAgent,
      }

      // 计算队列位置
      if (session.status === 'queued') {
        const key = session.userId || '__anonymous__'
        const pos = (userQueuePositions.get(key) || 0) + 1
        userQueuePositions.set(key, pos)
        summary.queuePosition = pos
      }

      return summary
    })
  }

  /**
   * 获取运行中的 Session 数量
   */
  getRunningCount(userId?: string, isAdmin?: boolean): number {
    let count = 0
    for (const session of this.sessions.values()) {
      if (session.status !== 'running') continue

      if (isAdmin) {
        count++
      } else if (userId && session.userId === userId) {
        count++
      } else if (!userId && !session.userId) {
        count++
      }
    }
    return count
  }

  /**
   * 检查用户是否有正在运行的 Session
   * 用于限制每用户只能同时运行一个分析任务
   */
  getUserRunningSession(userId: string): Session | null {
    for (const session of this.sessions.values()) {
      if (session.status === 'running' && session.userId === userId) {
        return session
      }
    }
    return null
  }

  /**
   * 删除 Session
   */
  deleteSession(sessionId: string): boolean {
    if (this.sessions.has(sessionId)) {
      // 取消运行中的任务
      const controller = this.runningTasks.get(sessionId)
      if (controller) {
        controller.abort()
        this.runningTasks.delete(sessionId)
      }

      this.sessions.delete(sessionId)
      this.saveSessions()
      return true
    }
    return false
  }

  /**
   * 启动 Session 执行（支持排队机制）
   */
  async startSession(sessionId: string, analysts: string[]): Promise<void> {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return
    }

    // 保存 analysts 配置供后续排队启动使用
    ;(session as any)._analysts = analysts

    // 检查该用户是否有正在运行的任务
    const runningSession = this.getUserRunningSession(session.userId)
    if (runningSession) {
      // 有运行中的任务，加入队列
      session.status = 'queued'
      this.saveSessions()
      sseManager.publish(sessionId, session)
      console.log(`[Session ${sessionId}] Queued (user ${session.userId} has running session ${runningSession.id})`)
      return
    }

    // 没有运行中的任务，直接启动
    this.startSessionNow(sessionId, analysts)
  }

  /**
   * 立即启动 Session（内部方法，跳过排队检查）
   */
  private startSessionNow(sessionId: string, analysts: string[]): void {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return
    }

    // 更新状态为运行中
    session.status = 'running'
    session.currentAgent = AGENT_ORDER[0] || ''
    this.saveSessions()
    sseManager.publish(sessionId, session)
    console.log(`[Session ${sessionId}] Started`)

    // 创建 AbortController 用于取消
    const controller = new AbortController()
    this.runningTasks.set(sessionId, controller)

    // 在后台执行分析
    this.runAnalysis(sessionId, analysts, controller.signal).catch(console.error)
  }

  /**
   * 启动该用户队列中的下一个 Session
   */
  private startNextQueuedSession(userId: string): void {
    // 找到该用户最早创建的 queued session
    let nextSession: Session | null = null
    let earliestTime = Infinity

    for (const session of this.sessions.values()) {
      if (session.status === 'queued' && session.userId === userId) {
        const time = new Date(session.createdAt).getTime()
        if (time < earliestTime) {
          earliestTime = time
          nextSession = session
        }
      }
    }

    if (nextSession) {
      const analysts = (nextSession as any)._analysts || ['market', 'social', 'news', 'fundamentals']
      console.log(`[Queue] Starting next session ${nextSession.id} for user ${userId}`)
      this.startSessionNow(nextSession.id, analysts)
    }
  }

  /**
   * 执行分析（在后台运行）- 使用 token-level streaming
   */
  private async runAnalysis(
    sessionId: string,
    analysts: string[],
    signal: AbortSignal
  ): Promise<void> {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return
    }

    try {
      const request: AnalyzeRequest = {
        ticker: session.ticker,
        date: session.endDate,
        market: session.market,
        analysts,
        model: session.model,
      }

      // 跟踪当前 agent 的累积内容
      let currentAgent = ''
      let accumulatedContent = ''
      let tokenCount = 0

      for await (const chunk of analysisClient.streamTokens(request)) {
        if (signal.aborted) return

        const { type, agent, content } = chunk

        switch (type) {
          case 'heartbeat':
            // 心跳消息，忽略
            break

          case 'node_start':
            // Agent 开始处理
            if (agent) {
              currentAgent = agent
              accumulatedContent = ''
              tokenCount = 0
              session.currentAgent = agent
              this.saveSessions()
              sseManager.publish(sessionId, session)
            }
            break

          case 'token':
            // 收到 token，累积并实时推送
            if (agent && content) {
              accumulatedContent += content
              tokenCount++
              session.reports[agent] = accumulatedContent

              // 每个 token 都推送，确保流畅的打字机效果
              sseManager.publish(sessionId, session)
            }
            break

          case 'node_end':
            // Agent 完成
            if (agent && content) {
              session.reports[agent] = content
              session.progress.push(agent)
              session.currentAgent = getNextAgent(agent)
              this.saveSessions()
              sseManager.publish(sessionId, session)
            }
            currentAgent = ''
            accumulatedContent = ''
            break

          case 'complete':
            // 分析完成
            session.decision = (content || 'HOLD') as any
            session.status = 'completed'
            session.currentAgent = ''
            this.saveSessions()
            sseManager.publish(sessionId, session)
            return

          case 'quota_error':
            session.status = 'error'
            session.errorMsg = 'API 额度已用完'
            session.currentAgent = ''
            this.saveSessions()
            sseManager.publish(sessionId, session)
            return

          case 'timeout_error':
            session.status = 'error'
            session.errorMsg = '网络响应超时'
            session.currentAgent = ''
            this.saveSessions()
            sseManager.publish(sessionId, session)
            return

          case 'error':
            session.status = 'error'
            session.errorMsg = (content || '未知错误').substring(0, 200)
            session.currentAgent = ''
            this.saveSessions()
            sseManager.publish(sessionId, session)
            return
        }
      }

      // 如果流结束但没有收到 complete，标记为完成
      if (session.status === 'running') {
        session.status = 'completed'
        session.currentAgent = ''
        this.saveSessions()
        sseManager.publish(sessionId, session)
      }

    } catch (e) {
      const error = e as Error
      console.error(`[Session ${sessionId}] Analysis error:`, error.message)
      session.status = 'error'
      session.errorMsg = error.message?.substring(0, 200) || '未知错误'
      session.currentAgent = ''
      this.saveSessions()
      sseManager.publish(sessionId, session)
    } finally {
      this.runningTasks.delete(sessionId)

      // 启动该用户队列中的下一个任务
      if (session.userId) {
        this.startNextQueuedSession(session.userId)
      }
    }
  }

  /**
   * 重试失败的 Session
   */
  async retrySession(sessionId: string, analysts?: string[]): Promise<void> {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return
    }

    // 重置状态
    session.status = 'pending'
    session.errorMsg = ''
    session.progress = []
    session.reports = {}
    session.decision = ''
    session.currentAgent = ''
    this.saveSessions()

    // 重新启动
    await this.startSession(
      sessionId,
      analysts || ['market', 'social', 'news', 'fundamentals']
    )
  }

  /**
   * 清除已完成的 Session
   */
  clearCompleted(): number {
    const toDelete: string[] = []

    for (const [id, session] of this.sessions) {
      if (session.status === 'completed' || session.status === 'error') {
        toDelete.push(id)
      }
    }

    for (const id of toDelete) {
      this.sessions.delete(id)
    }

    if (toDelete.length > 0) {
      this.saveSessions()
    }

    return toDelete.length
  }

  /**
   * 优雅关闭：标记所有运行中的 Session 为中断状态
   * 在服务器关闭前调用
   */
  gracefulShutdown(): void {
    console.log('[SessionManager] Graceful shutdown initiated')
    let interrupted = 0

    for (const session of this.sessions.values()) {
      if (session.status === 'running') {
        session.status = 'error'
        session.errorMsg = '服务器重启，分析中断（可点击重试继续）'
        session.currentAgent = ''
        interrupted++
      }
    }

    if (interrupted > 0) {
      this.saveSessions()
      console.log(`[SessionManager] Marked ${interrupted} running sessions as interrupted`)
    }

    // 取消所有运行中的任务
    for (const [sessionId, controller] of this.runningTasks) {
      controller.abort()
      console.log(`[SessionManager] Aborted task for session ${sessionId}`)
    }
    this.runningTasks.clear()
  }
}

// 全局单例
export const sessionManager = new SessionManager()
