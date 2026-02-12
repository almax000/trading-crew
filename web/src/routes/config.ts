/**
 * Config Routes - Configuration API
 */

import { Hono } from 'hono'
import type { ConfigResponse, UserContext } from '../types'
import {
  MARKET_OPTIONS,
  ANALYST_OPTIONS,
  AGENT_DISPLAY_NAMES,
  AGENT_ORDER,
  getDatePresets,
  getDefaultDates,
} from '../config'

export const configRoutes = new Hono()

/**
 * GET /api/config
 * Get frontend configuration
 */
configRoutes.get('/', (c) => {
  const user = c.get('user') as UserContext | undefined
  const { start, end } = getDefaultDates()

  const res: ConfigResponse = {
    markets: MARKET_OPTIONS,
    analysts: ANALYST_OPTIONS,
    agentNames: AGENT_DISPLAY_NAMES,
    agentOrder: AGENT_ORDER,
    datePresets: getDatePresets(),
    defaultDates: { start, end },
    isAdmin: user?.isAdmin || false,
  }

  return c.json(res)
})
