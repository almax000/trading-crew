/**
 * Session Manager - Session Lifecycle Management
 *
 * Manages session creation, execution, and state tracking.
 * Supports concurrent session execution with JSON file persistence.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs'
import { join, dirname } from 'path'
import type { Session, SessionStatus, SessionSummary, Market, Model, AnalyzeRequest } from '../types'
import { DATA_DIR, AGENT_ORDER } from '../config'
import { sseManager } from './sse-manager'
import { analysisClient } from './analysis-client'

// Session storage file path
const SESSIONS_FILE = join(DATA_DIR, 'sessions.json')

// Generate short ID
function generateId(): string {
  return Math.random().toString(36).substring(2, 10)
}

// Get next agent
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
   * Load sessions from file
   */
  loadSessions(): void {
    if (!existsSync(SESSIONS_FILE)) {
      return
    }

    try {
      const data = JSON.parse(readFileSync(SESSIONS_FILE, 'utf-8'))
      for (const sessionData of data) {
        const session = this.parseSession(sessionData)
        // If previously running, mark as error (server restarted)
        if (session.status === 'running') {
          session.status = 'error'
          session.errorMsg = 'Server restarted, analysis interrupted'
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
   * Save sessions to file
   */
  private saveSessions(): void {
    try {
      // Ensure directory exists
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
   * Parse session data
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
   * Create a new session
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
   * Get a session
   */
  getSession(sessionId: string, userId?: string, isAdmin?: boolean): Session | null {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return null
    }

    // Admin can access all sessions
    if (isAdmin) {
      return session
    }

    // Regular users can only access their own sessions
    if (userId && session.userId && session.userId !== userId) {
      return null
    }

    return session
  }

  /**
   * Get all sessions (sorted by creation time descending)
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
   * Get all session summaries (without reports, optimized for list loading)
   */
  getAllSessionSummaries(userId?: string, isAdmin?: boolean): SessionSummary[] {
    const sessions = this.getAllSessions(userId, isAdmin)

    // Calculate queue position per user
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

      // Calculate queue position
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
   * Get running session count
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
   * Check if user has a running session
   * Used to limit one concurrent analysis task per user
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
   * Delete a session
   */
  deleteSession(sessionId: string): boolean {
    if (this.sessions.has(sessionId)) {
      // Cancel running task
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
   * Start session execution (supports queuing)
   */
  async startSession(sessionId: string, analysts: string[]): Promise<void> {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return
    }

    // Save analysts config for later queued start
    ;(session as any)._analysts = analysts

    // Check if user has a running task
    const runningSession = this.getUserRunningSession(session.userId)
    if (runningSession) {
      // Has running task, add to queue
      session.status = 'queued'
      this.saveSessions()
      sseManager.publish(sessionId, session)
      console.log(`[Session ${sessionId}] Queued (user ${session.userId} has running session ${runningSession.id})`)
      return
    }

    // No running task, start immediately
    this.startSessionNow(sessionId, analysts)
  }

  /**
   * Start session immediately (internal method, skips queue check)
   */
  private startSessionNow(sessionId: string, analysts: string[]): void {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return
    }

    // Update status to running
    session.status = 'running'
    session.currentAgent = AGENT_ORDER[0] || ''
    this.saveSessions()
    sseManager.publish(sessionId, session)
    console.log(`[Session ${sessionId}] Started`)

    // Create AbortController for cancellation
    const controller = new AbortController()
    this.runningTasks.set(sessionId, controller)

    // Run analysis in background
    this.runAnalysis(sessionId, analysts, controller.signal).catch(console.error)
  }

  /**
   * Start next queued session for this user
   */
  private startNextQueuedSession(userId: string): void {
    // Find the earliest created queued session for this user
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
   * Run analysis (in background) - uses token-level streaming
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

      // Track current agent's accumulated content
      let currentAgent = ''
      let accumulatedContent = ''
      let tokenCount = 0

      for await (const chunk of analysisClient.streamTokens(request)) {
        if (signal.aborted) return

        const { type, agent, content } = chunk

        switch (type) {
          case 'heartbeat':
            // Heartbeat message, ignore
            break

          case 'node_start':
            // Agent started processing
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
            // Received token, accumulate and push in real-time
            if (agent && content) {
              accumulatedContent += content
              tokenCount++
              session.reports[agent] = accumulatedContent

              // Push every token for smooth typewriter effect
              sseManager.publish(sessionId, session)
            }
            break

          case 'node_end':
            // Agent completed
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
            // Analysis complete
            session.decision = (content || 'HOLD') as any
            session.status = 'completed'
            session.currentAgent = ''
            this.saveSessions()
            sseManager.publish(sessionId, session)
            return

          case 'quota_error':
            session.status = 'error'
            session.errorMsg = 'API quota exhausted'
            session.currentAgent = ''
            this.saveSessions()
            sseManager.publish(sessionId, session)
            return

          case 'timeout_error':
            session.status = 'error'
            session.errorMsg = 'Network response timeout'
            session.currentAgent = ''
            this.saveSessions()
            sseManager.publish(sessionId, session)
            return

          case 'error':
            session.status = 'error'
            session.errorMsg = (content || 'Unknown error').substring(0, 200)
            session.currentAgent = ''
            this.saveSessions()
            sseManager.publish(sessionId, session)
            return
        }
      }

      // If stream ended without a complete event, mark as completed
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
      session.errorMsg = error.message?.substring(0, 200) || 'Unknown error'
      session.currentAgent = ''
      this.saveSessions()
      sseManager.publish(sessionId, session)
    } finally {
      this.runningTasks.delete(sessionId)

      // Start next queued task for this user
      if (session.userId) {
        this.startNextQueuedSession(session.userId)
      }
    }
  }

  /**
   * Retry a failed session
   */
  async retrySession(sessionId: string, analysts?: string[]): Promise<void> {
    const session = this.sessions.get(sessionId)
    if (!session) {
      return
    }

    // Reset state
    session.status = 'pending'
    session.errorMsg = ''
    session.progress = []
    session.reports = {}
    session.decision = ''
    session.currentAgent = ''
    this.saveSessions()

    // Restart
    await this.startSession(
      sessionId,
      analysts || ['market', 'social', 'news', 'fundamentals']
    )
  }

  /**
   * Clear completed sessions
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
   * Graceful shutdown: mark all running sessions as interrupted
   * Called before server shutdown
   */
  gracefulShutdown(): void {
    console.log('[SessionManager] Graceful shutdown initiated')
    let interrupted = 0

    for (const session of this.sessions.values()) {
      if (session.status === 'running') {
        session.status = 'error'
        session.errorMsg = 'Server restarted, analysis interrupted (click retry to continue)'
        session.currentAgent = ''
        interrupted++
      }
    }

    if (interrupted > 0) {
      this.saveSessions()
      console.log(`[SessionManager] Marked ${interrupted} running sessions as interrupted`)
    }

    // Cancel all running tasks
    for (const [sessionId, controller] of this.runningTasks) {
      controller.abort()
      console.log(`[SessionManager] Aborted task for session ${sessionId}`)
    }
    this.runningTasks.clear()
  }
}

// Global singleton
export const sessionManager = new SessionManager()
