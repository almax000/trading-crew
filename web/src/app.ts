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

// Create Hono application
const app = new Hono()

// CORS middleware
app.use('/*', cors({
  origin: '*',
  allowMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'X-Username'],
}))

// User context middleware
app.use('/api/*', async (c, next) => {
  const username = c.req.header('X-Username') || ''
  const adminUsers = getAdminUsers()

  c.set('user', {
    username,
    isAdmin: adminUsers.has(username),
  } as UserContext)

  await next()
})

// API routes
app.route('/api/auth', authRoutes)
app.route('/api/config', configRoutes)
app.route('/api/ticker', tickerRoutes)
app.route('/api/sessions', sessionRoutes)

// Static files
app.use('/static/*', serveStatic({ root: './' }))

// Homepage
app.get('/', serveStatic({ path: './static/index.html' }))

// Favicon
app.get('/favicon.ico', serveStatic({ path: './static/favicon.ico' }))

// Health check
app.get('/health', (c) => c.json({ status: 'ok', service: 'web' }))

export default app
