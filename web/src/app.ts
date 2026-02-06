/**
 * TradingCrew Web UI - Hono Application
 */

import { Hono } from 'hono'
import { cors } from 'hono/cors'
import { serveStatic } from 'hono/bun'

import type { UserContext } from './types'
import { getInviteCodes, getAdminUsers } from './config'

import { authRoutes } from './routes/auth'
import { configRoutes } from './routes/config'
import { tickerRoutes } from './routes/ticker'
import { sessionRoutes } from './routes/sessions'

// 创建 Hono 应用
const app = new Hono()

// CORS 中间件
app.use('/*', cors({
  origin: '*',
  allowMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'X-Username'],
}))

// 用户上下文中间件
app.use('/api/*', async (c, next) => {
  const username = c.req.header('X-Username') || ''
  const adminUsers = getAdminUsers()

  c.set('user', {
    username,
    isAdmin: adminUsers.has(username),
  } as UserContext)

  await next()
})

// API 路由
app.route('/api/auth', authRoutes)
app.route('/api/config', configRoutes)
app.route('/api/ticker', tickerRoutes)
app.route('/api/sessions', sessionRoutes)

// 静态文件
app.use('/static/*', serveStatic({ root: './' }))

// 首页
app.get('/', serveStatic({ path: './static/index.html' }))

// Favicon
app.get('/favicon.ico', serveStatic({ path: './static/favicon.ico' }))

// 健康检查
app.get('/health', (c) => c.json({ status: 'ok', service: 'web' }))

export default app
