/**
 * Analysis Client - Python 分析服务客户端
 *
 * 通过 HTTP 调用 Python FastAPI 分析服务，获取流式分析结果。
 */

import type { AnalyzeRequest, AnalyzeStreamChunk, AnalyzeStreamTokenChunk } from '../types'
import { ANALYSIS_SERVICE_URL } from '../config'

export class AnalysisClient {
  private baseUrl: string

  constructor(baseUrl: string = ANALYSIS_SERVICE_URL) {
    this.baseUrl = baseUrl
  }

  /**
   * 流式分析股票
   *
   * 调用 Python 服务的 /analyze 端点，返回 NDJSON 流。
   * 分析可能需要 10+ 分钟，设置 15 分钟超时。
   */
  async *stream(params: AnalyzeRequest): AsyncGenerator<AnalyzeStreamChunk> {
    // 创建 15 分钟超时的 AbortController
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 15 * 60 * 1000)

    try {
      const res = await fetch(`${this.baseUrl}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
        signal: controller.signal,
      })

      if (!res.ok) {
        throw new Error(`Analysis service error: ${res.status} ${res.statusText}`)
      }

      if (!res.body) {
        throw new Error('No response body from analysis service')
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          // 按行分割 NDJSON
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''  // 保留不完整的行

          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed) continue

            try {
              const chunk: AnalyzeStreamChunk = JSON.parse(trimmed)
              yield chunk
            } catch (e) {
              console.error('Failed to parse NDJSON line:', trimmed, e)
            }
          }
        }

        // 处理最后可能剩余的数据
        if (buffer.trim()) {
          try {
            const chunk: AnalyzeStreamChunk = JSON.parse(buffer.trim())
            yield chunk
          } catch (e) {
            console.error('Failed to parse final NDJSON:', buffer, e)
          }
        }
      } finally {
        reader.releaseLock()
      }
    } finally {
      clearTimeout(timeoutId)
    }
  }

  /**
   * Token-level streaming analysis (新端点)
   *
   * 调用 Python 服务的 /analyze/stream 端点，返回 token 级别的流式输出。
   */
  async *streamTokens(params: AnalyzeRequest): AsyncGenerator<AnalyzeStreamTokenChunk> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 15 * 60 * 1000)

    try {
      const res = await fetch(`${this.baseUrl}/analyze/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
        signal: controller.signal,
      })

      if (!res.ok) {
        throw new Error(`Analysis service error: ${res.status} ${res.statusText}`)
      }

      if (!res.body) {
        throw new Error('No response body from analysis service')
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed) continue

            try {
              const chunk: AnalyzeStreamTokenChunk = JSON.parse(trimmed)
              yield chunk
            } catch (e) {
              console.error('Failed to parse NDJSON line:', trimmed, e)
            }
          }
        }

        if (buffer.trim()) {
          try {
            const chunk: AnalyzeStreamTokenChunk = JSON.parse(buffer.trim())
            yield chunk
          } catch (e) {
            console.error('Failed to parse final NDJSON:', buffer, e)
          }
        }
      } finally {
        reader.releaseLock()
      }
    } finally {
      clearTimeout(timeoutId)
    }
  }

  /**
   * 健康检查
   */
  async healthCheck(): Promise<boolean> {
    try {
      const res = await fetch(`${this.baseUrl}/health`)
      return res.ok
    } catch {
      return false
    }
  }
}

// 全局单例
export const analysisClient = new AnalysisClient()
