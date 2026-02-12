/**
 * Ticker Routes - Stock Code Validation API
 */

import { Hono } from 'hono'
import type { TickerValidateRequest, TickerValidateResponse, Market } from '../types'
import { MARKET_OPTIONS } from '../config'
import { validateTickerFormat, validateAndGetName } from '../services/ticker-validator'

export const tickerRoutes = new Hono()

/**
 * POST /api/ticker/validate
 * Validate stock code and get name
 */
tickerRoutes.post('/validate', async (c) => {
  const body = await c.req.json<TickerValidateRequest>()
  const { ticker, market: marketName } = body

  // Convert market display name to internal code
  const market = (MARKET_OPTIONS[marketName] || marketName) as Market

  // Format validation first
  const formatResult = validateTickerFormat(ticker, market)
  if (!formatResult.valid) {
    const res: TickerValidateResponse = {
      valid: false,
      normalized: '',
      name: '',
      error: formatResult.error,
    }
    return c.json(res)
  }

  // Try to get name
  try {
    const result = await validateAndGetName(ticker, market)
    const res: TickerValidateResponse = {
      valid: result.valid,
      normalized: result.normalized,
      name: result.name,
      error: result.error,
    }
    return c.json(res)
  } catch (e) {
    // Name lookup failed, but format is valid
    const res: TickerValidateResponse = {
      valid: true,
      normalized: formatResult.normalized,
      name: '',
      error: '',
    }
    return c.json(res)
  }
})
