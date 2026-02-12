/**
 * Analysis Client - Python Analysis Service Client
 *
 * Calls the Python FastAPI analysis service via HTTP to get streaming analysis results.
 */

import type { AnalyzeRequest, AnalyzeStreamChunk, AnalyzeStreamTokenChunk } from '../types'
import { ANALYSIS_SERVICE_URL } from '../config'

export class AnalysisClient {
  private baseUrl: string

  constructor(baseUrl: string = ANALYSIS_SERVICE_URL) {
    this.baseUrl = baseUrl
  }

  /**
   * Stream stock analysis
   *
   * Calls the Python service's /analyze endpoint, returns NDJSON stream.
   * Analysis may take 10+ minutes, set 15-minute timeout.
   */
  async *stream(params: AnalyzeRequest): AsyncGenerator<AnalyzeStreamChunk> {
    // Create AbortController with 15-minute timeout
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

          // Split NDJSON by lines
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''  // Keep incomplete line

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

        // Process any remaining data
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
   * Token-level streaming analysis (new endpoint)
   *
   * Calls the Python service's /analyze/stream endpoint, returns token-level streaming output.
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
   * Health check
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

// Global singleton
export const analysisClient = new AnalysisClient()
