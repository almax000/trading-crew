/**
 * Ticker Routes - 股票代码验证 API
 */

import { Hono } from 'hono'
import type { TickerValidateRequest, TickerValidateResponse, Market } from '../types'
import { MARKET_OPTIONS } from '../config'
import { validateTickerFormat, validateAndGetName } from '../services/ticker-validator'

export const tickerRoutes = new Hono()

/**
 * POST /api/ticker/validate
 * 验证股票代码并获取名称
 */
tickerRoutes.post('/validate', async (c) => {
  const body = await c.req.json<TickerValidateRequest>()
  const { ticker, market: marketName } = body

  // 将中文市场名转换为内部代码
  const market = (MARKET_OPTIONS[marketName] || marketName) as Market

  // 先做格式验证
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

  // 尝试获取名称
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
    // 名称查询失败，但格式正确
    const res: TickerValidateResponse = {
      valid: true,
      normalized: formatResult.normalized,
      name: '',
      error: '',
    }
    return c.json(res)
  }
})
