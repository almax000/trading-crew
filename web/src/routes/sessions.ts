/**
 * Sessions Routes - Session Management API
 */

import { Hono } from 'hono'
import { stream } from 'hono/streaming'
import type { CreateSessionRequest, UserContext, Market, Model } from '../types'
import { MARKET_OPTIONS } from '../config'
import { sessionManager } from '../services/session-manager'
import { sseManager } from '../services/sse-manager'
import { validateAndGetName } from '../services/ticker-validator'

export const sessionRoutes = new Hono()

/**
 * GET /api/sessions
 * Get session list for current user (admin can see all)
 * Returns summaries (without full reports) for optimized loading
 */
sessionRoutes.get('/', (c) => {
  const user = c.get('user') as UserContext | undefined
  const sessions = sessionManager.getAllSessionSummaries(user?.username, user?.isAdmin)

  return c.json(sessions)
})

/**
 * GET /api/sessions/running/count
 * Get running session count
 */
sessionRoutes.get('/running/count', (c) => {
  const user = c.get('user') as UserContext | undefined
  const count = sessionManager.getRunningCount(user?.username, user?.isAdmin)

  return c.json({ count })
})

/**
 * GET /api/sessions/:id
 * Get single session details
 */
sessionRoutes.get('/:id', (c) => {
  const sessionId = c.req.param('id')
  const user = c.get('user') as UserContext | undefined

  const session = sessionManager.getSession(sessionId, user?.username, user?.isAdmin)
  if (!session) {
    return c.json({ error: 'Session not found' }, 404)
  }

  return c.json(session)
})

/**
 * POST /api/sessions
 * Create and start a new session (supports queuing)
 * If user already has a running task, new task will be queued automatically
 */
sessionRoutes.post('/', async (c) => {
  const user = c.get('user') as UserContext | undefined
  const body = await c.req.json<CreateSessionRequest>()
  const { ticker, market: marketName, model: modelName, startDate, endDate, analysts } = body

  const userId = user?.username || ''

  // Convert market display name to internal code
  const market = (MARKET_OPTIONS[marketName] || marketName) as Market

  // Model name (default deepseek-v3)
  const model = (modelName || 'deepseek-v3') as Model

  // Validate ticker
  const validation = await validateAndGetName(ticker, market)
  if (!validation.valid) {
    return c.json({ error: validation.error }, 400)
  }

  // Create session
  const session = sessionManager.createSession({
    ticker: validation.normalized,
    stockName: validation.name,
    market,
    model,
    startDate,
    endDate,
    userId,
  })

  // Start session (will auto-check if queuing is needed)
  await sessionManager.startSession(session.id, analysts)

  // Re-fetch session to return latest status (may be running or queued)
  const updatedSession = sessionManager.getSession(session.id, userId, user?.isAdmin)
  return c.json(updatedSession)
})

/**
 * DELETE /api/sessions/:id
 * Delete a session
 */
sessionRoutes.delete('/:id', (c) => {
  const sessionId = c.req.param('id')
  const user = c.get('user') as UserContext | undefined

  // Check permissions first
  const session = sessionManager.getSession(sessionId, user?.username, user?.isAdmin)
  if (!session) {
    return c.json({ error: 'Session not found' }, 404)
  }

  const success = sessionManager.deleteSession(sessionId)
  if (!success) {
    return c.json({ error: 'Session not found' }, 404)
  }

  return c.json({ success: true })
})

/**
 * POST /api/sessions/:id/retry
 * Retry a failed session (supports queuing)
 */
sessionRoutes.post('/:id/retry', async (c) => {
  const sessionId = c.req.param('id')
  const user = c.get('user') as UserContext | undefined

  const session = sessionManager.getSession(sessionId, user?.username, user?.isAdmin)
  if (!session) {
    return c.json({ error: 'Session not found' }, 404)
  }

  if (session.status !== 'error') {
    return c.json({ error: 'Can only retry sessions with errors' }, 400)
  }

  // Retry session (will auto-check if queuing is needed)
  await sessionManager.retrySession(sessionId)

  // Re-fetch session
  const updatedSession = sessionManager.getSession(sessionId, user?.username, user?.isAdmin)
  return c.json(updatedSession)
})

/**
 * GET /api/sessions/:id/stream
 * SSE endpoint: real-time session status updates
 */
sessionRoutes.get('/:id/stream', async (c) => {
  const sessionId = c.req.param('id')
  // EventSource doesn't support headers, use query param
  const username = c.req.query('username') || ''
  const isAdmin = c.req.query('isAdmin') === 'true'

  const session = sessionManager.getSession(sessionId, username, isAdmin)
  if (!session) {
    return c.json({ error: 'Session not found' }, 404)
  }

  // Set SSE headers
  c.header('Content-Type', 'text/event-stream')
  c.header('Cache-Control', 'no-cache')
  c.header('Connection', 'keep-alive')
  c.header('X-Accel-Buffering', 'no')  // Disable nginx buffering

  return stream(c, async (stream) => {
    // Send initial state
    const initialData = JSON.stringify(session)
    await stream.write(`data: ${initialData}\n\n`)

    // If already completed or errored, return immediately
    if (session.status === 'completed' || session.status === 'error') {
      return
    }

    // Subscribe to SSE updates
    const sseStream = sseManager.subscribe(sessionId)
    const reader = sseStream.getReader()

    // Set heartbeat timer
    const heartbeatInterval = setInterval(() => {
      stream.write(': heartbeat\n\n').catch(() => {
        clearInterval(heartbeatInterval)
      })
    }, 30000)

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        // Write directly (value is already Uint8Array SSE message)
        await stream.write(new TextDecoder().decode(value))

        // Get latest session status
        const currentSession = sessionManager.getSession(sessionId, username, isAdmin)
        if (!currentSession ||
            currentSession.status === 'completed' ||
            currentSession.status === 'error') {
          break
        }
      }
    } finally {
      clearInterval(heartbeatInterval)
      reader.releaseLock()
    }
  })
})
