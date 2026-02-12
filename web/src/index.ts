/**
 * TradingCrew Web UI - Entry Point
 *
 * Usage:
 *   bun run src/index.ts
 *   or
 *   bun run dev (watch mode)
 */

import app from './app'
import { WEB_PORT, ANALYSIS_SERVICE_URL, getInviteCodes } from './config'
import { sessionManager } from './services/session-manager'

// Wait for Python analysis service to be ready
async function waitForAnalysisService(maxRetries = 30, intervalMs = 1000): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(`${ANALYSIS_SERVICE_URL}/health`)
      if (res.ok) {
        console.log('✓ Python Analysis Service is ready')
        return true
      }
    } catch {
      // Continue retrying
    }
    console.log(`Waiting for Python Analysis Service... (${i + 1}/${maxRetries})`)
    await new Promise(resolve => setTimeout(resolve, intervalMs))
  }
  console.warn('⚠ Python Analysis Service not available, continuing anyway...')
  return false
}

// Main function
async function main() {
  console.log('\n┌─────────────────────────────────────────────┐')
  console.log('│     TradingCrew Web UI (Bun + Hono)         │')
  console.log('└─────────────────────────────────────────────┘\n')

  // Wait for analysis service (only in non-local-dev environments)
  if (process.env.RAILWAY_ENVIRONMENT || process.env.WAIT_FOR_ANALYSIS) {
    await waitForAnalysisService()
  }

  // Load session data
  sessionManager.loadSessions()

  const inviteCodes = getInviteCodes()
  console.log(`📝 Invite codes: ${inviteCodes.size}`)
  console.log(`🔗 Analysis service: ${ANALYSIS_SERVICE_URL}`)
  console.log(`🌐 Starting server on port ${WEB_PORT}...\n`)

  // Start server
  // idleTimeout: Bun supports max 255 seconds (~4 minutes)
  const server = Bun.serve({
    port: WEB_PORT,
    fetch: app.fetch,
    idleTimeout: 255,  // Max value
  })

  console.log(`✓ Server running at http://localhost:${server.port}`)
  console.log(`✓ API docs: http://localhost:${server.port}/api/config\n`)

  // Graceful shutdown handler (mark interrupted sessions on deploy)
  const shutdown = () => {
    console.log('\n🛑 Shutting down gracefully...')
    sessionManager.gracefulShutdown()
    process.exit(0)
  }

  process.on('SIGTERM', shutdown)
  process.on('SIGINT', shutdown)
}

main().catch(console.error)
