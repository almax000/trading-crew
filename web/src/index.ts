/**
 * TradingCrew Web UI - Entry Point
 *
 * 启动方式:
 *   bun run src/index.ts
 *   或
 *   bun run dev (watch mode)
 */

import app from './app'
import { WEB_PORT, ANALYSIS_SERVICE_URL, getInviteCodes } from './config'
import { sessionManager } from './services/session-manager'

// 等待 Python 分析服务就绪
async function waitForAnalysisService(maxRetries = 30, intervalMs = 1000): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(`${ANALYSIS_SERVICE_URL}/health`)
      if (res.ok) {
        console.log('✓ Python Analysis Service is ready')
        return true
      }
    } catch {
      // 继续重试
    }
    console.log(`Waiting for Python Analysis Service... (${i + 1}/${maxRetries})`)
    await new Promise(resolve => setTimeout(resolve, intervalMs))
  }
  console.warn('⚠ Python Analysis Service not available, continuing anyway...')
  return false
}

// 主函数
async function main() {
  console.log('\n┌─────────────────────────────────────────────┐')
  console.log('│     TradingCrew Web UI (Bun + Hono)         │')
  console.log('└─────────────────────────────────────────────┘\n')

  // 等待分析服务（仅在非本地开发时）
  if (process.env.RAILWAY_ENVIRONMENT || process.env.WAIT_FOR_ANALYSIS) {
    await waitForAnalysisService()
  }

  // 加载 Session 数据
  sessionManager.loadSessions()

  const inviteCodes = getInviteCodes()
  console.log(`📝 Invite codes: ${inviteCodes.size}`)
  console.log(`🔗 Analysis service: ${ANALYSIS_SERVICE_URL}`)
  console.log(`🌐 Starting server on port ${WEB_PORT}...\n`)

  // 启动服务器
  // idleTimeout: Bun 最大支持 255 秒（约 4 分钟）
  const server = Bun.serve({
    port: WEB_PORT,
    fetch: app.fetch,
    idleTimeout: 255,  // 最大值
  })

  console.log(`✓ Server running at http://localhost:${server.port}`)
  console.log(`✓ API docs: http://localhost:${server.port}/api/config\n`)

  // 优雅关闭处理（部署时标记中断的会话）
  const shutdown = () => {
    console.log('\n🛑 Shutting down gracefully...')
    sessionManager.gracefulShutdown()
    process.exit(0)
  }

  process.on('SIGTERM', shutdown)
  process.on('SIGINT', shutdown)
}

main().catch(console.error)
