/**
 * Sessions Routes - Session 管理 API
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
 * 获取当前用户的 Session 列表（管理员可见所有）
 * 返回摘要信息（不含完整报告），优化加载速度
 */
sessionRoutes.get('/', (c) => {
  const user = c.get('user') as UserContext | undefined
  const sessions = sessionManager.getAllSessionSummaries(user?.username, user?.isAdmin)

  return c.json(sessions)
})

/**
 * GET /api/sessions/admin/all
 * 管理员专用：获取所有用户的所有会话（含完整报告）
 * 需要 ?token=<ADMIN_TOKEN> 参数
 */
sessionRoutes.get('/admin/all', (c) => {
  const token = c.req.query('token')
  const adminToken = process.env.ADMIN_TOKEN || 'trading-crew-admin-2026'

  if (token !== adminToken) {
    return c.json({ error: 'Unauthorized' }, 401)
  }

  const sessions = Array.from((sessionManager as any).sessions.values())

  // 按用户分组统计
  const userStats: Record<string, number> = {}
  for (const s of sessions) {
    const user = s.userId || '(anonymous)'
    userStats[user] = (userStats[user] || 0) + 1
  }

  return c.json({
    total: sessions.length,
    byUser: userStats,
    sessions: sessions.sort((a: any, b: any) =>
      new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    )
  })
})

/**
 * GET /api/sessions/running/count
 * 获取运行中的 Session 数量
 */
sessionRoutes.get('/running/count', (c) => {
  const user = c.get('user') as UserContext | undefined
  const count = sessionManager.getRunningCount(user?.username, user?.isAdmin)

  return c.json({ count })
})

/**
 * GET /api/sessions/:id
 * 获取单个 Session 详情
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
 * 创建并启动新 Session（支持排队机制）
 * 如果用户已有运行中的任务，新任务会自动排队
 */
sessionRoutes.post('/', async (c) => {
  const user = c.get('user') as UserContext | undefined
  const body = await c.req.json<CreateSessionRequest>()
  const { ticker, market: marketName, model: modelName, startDate, endDate, analysts } = body

  const userId = user?.username || ''

  // 将中文市场名转换为内部代码
  const market = (MARKET_OPTIONS[marketName] || marketName) as Market

  // 模型名（默认 deepseek-v3）
  const model = (modelName || 'deepseek-v3') as Model

  // 验证股票代码
  const validation = await validateAndGetName(ticker, market)
  if (!validation.valid) {
    return c.json({ error: validation.error }, 400)
  }

  // 创建 Session
  const session = sessionManager.createSession({
    ticker: validation.normalized,
    stockName: validation.name,
    market,
    model,
    startDate,
    endDate,
    userId,
  })

  // 启动 Session（会自动检查是否需要排队）
  await sessionManager.startSession(session.id, analysts)

  // 重新获取 session 以返回最新状态（可能是 running 或 queued）
  const updatedSession = sessionManager.getSession(session.id, userId, user?.isAdmin)
  return c.json(updatedSession)
})

/**
 * DELETE /api/sessions/:id
 * 删除 Session
 */
sessionRoutes.delete('/:id', (c) => {
  const sessionId = c.req.param('id')
  const user = c.get('user') as UserContext | undefined

  // 先检查权限
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
 * 重试失败的 Session（支持排队机制）
 */
sessionRoutes.post('/:id/retry', async (c) => {
  const sessionId = c.req.param('id')
  const user = c.get('user') as UserContext | undefined

  const session = sessionManager.getSession(sessionId, user?.username, user?.isAdmin)
  if (!session) {
    return c.json({ error: 'Session not found' }, 404)
  }

  if (session.status !== 'error') {
    return c.json({ error: '只能重试出错的会话' }, 400)
  }

  // 重试 Session（会自动检查是否需要排队）
  await sessionManager.retrySession(sessionId)

  // 重新获取 Session
  const updatedSession = sessionManager.getSession(sessionId, user?.username, user?.isAdmin)
  return c.json(updatedSession)
})

/**
 * GET /api/sessions/:id/stream
 * SSE 端点：实时推送 Session 状态更新
 */
sessionRoutes.get('/:id/stream', async (c) => {
  const sessionId = c.req.param('id')
  // EventSource 不支持 header，用 query param
  const username = c.req.query('username') || ''
  const isAdmin = c.req.query('isAdmin') === 'true'

  const session = sessionManager.getSession(sessionId, username, isAdmin)
  if (!session) {
    return c.json({ error: 'Session not found' }, 404)
  }

  // 设置 SSE headers
  c.header('Content-Type', 'text/event-stream')
  c.header('Cache-Control', 'no-cache')
  c.header('Connection', 'keep-alive')
  c.header('X-Accel-Buffering', 'no')  // 禁用 nginx 缓冲

  return stream(c, async (stream) => {
    // 发送初始状态
    const initialData = JSON.stringify(session)
    await stream.write(`data: ${initialData}\n\n`)

    // 如果已完成或出错，直接返回
    if (session.status === 'completed' || session.status === 'error') {
      return
    }

    // 订阅 SSE 更新
    const sseStream = sseManager.subscribe(sessionId)
    const reader = sseStream.getReader()

    // 设置心跳定时器
    const heartbeatInterval = setInterval(() => {
      stream.write(': heartbeat\n\n').catch(() => {
        clearInterval(heartbeatInterval)
      })
    }, 30000)

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        // 直接写入（value 已经是 Uint8Array 格式的 SSE 消息）
        await stream.write(new TextDecoder().decode(value))

        // 获取最新 session 状态
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
