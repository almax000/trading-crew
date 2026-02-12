/**
 * TradingCrew Web UI - Configuration
 */

import type { DatePreset } from './types'

// Server port
export const WEB_PORT = parseInt(process.env.PORT || process.env.WEB_PORT || '1788', 10)

// Python analysis service URL
export const ANALYSIS_SERVICE_URL = process.env.ANALYSIS_SERVICE_URL || 'http://127.0.0.1:8000'

// Data directory (for session persistence)
export const DATA_DIR = process.env.DATA_DIR || './data'

// Read invite codes from environment variables
export function getInviteCodes(): Map<string, string> {
  const codes = new Map<string, string>()

  // Format: INVITE_CODES=user1:pass1,user2:pass2
  const codesStr = process.env.INVITE_CODES || ''
  if (codesStr) {
    for (const pair of codesStr.split(',')) {
      const [user, pwd] = pair.trim().split(':', 2)
      if (user && pwd) {
        codes.set(user.trim(), pwd.trim())
      }
    }
  }

  // Legacy format: INVITE_CODE_N=user:pass
  for (const [key, value] of Object.entries(process.env)) {
    if (key.startsWith('INVITE_CODE_') && value) {
      const [user, pwd] = value.split(':', 2)
      if (user && pwd) {
        codes.set(user.trim(), pwd.trim())
      }
    }
  }

  if (codes.size === 0) {
    console.warn('[config] WARNING: No INVITE_CODES configured. Set INVITE_CODES env var to enable login.')
  }

  return codes
}

// Read admin users from environment variables
export function getAdminUsers(): Set<string> {
  const admins = new Set<string>()

  // Format: ADMIN_USERS=user1,user2,user3
  const adminStr = process.env.ADMIN_USERS || ''
  if (adminStr) {
    for (const user of adminStr.split(',')) {
      if (user.trim()) {
        admins.add(user.trim())
      }
    }
  }

  return admins
}

// Market options
export const MARKET_OPTIONS: Record<string, string> = {
  'A-Share': 'A-share',
  'US Stock': 'US',
  'HK Stock': 'HK',
}

// Analyst options
export const ANALYST_OPTIONS: Record<string, string> = {
  'Market Analyst': 'market',
  'Sentiment Analyst': 'social',
  'News Analyst': 'news',
  'Fundamentals Analyst': 'fundamentals',
}

// Agent display name mapping
export const AGENT_DISPLAY_NAMES: Record<string, string> = {
  'Market Analyst': 'Market Analyst',
  'Social Analyst': 'Sentiment Analyst',
  'News Analyst': 'News Analyst',
  'Fundamentals Analyst': 'Fundamentals Analyst',
  'Bull Researcher': 'Bull Researcher',
  'Bear Researcher': 'Bear Researcher',
  'Research Manager': 'Research Manager',
  'Trader': 'Trader',
  'Risky Analyst': 'Aggressive Risk',
  'Safe Analyst': 'Conservative Risk',
  'Neutral Analyst': 'Neutral Risk',
  'Risk Manager': 'Risk Manager',
  'Portfolio Manager': 'Portfolio Manager',
}

// Agent execution order
export const AGENT_ORDER: string[] = [
  'Market Analyst',
  'Social Analyst',
  'News Analyst',
  'Fundamentals Analyst',
  'Bull Researcher',
  'Bear Researcher',
  'Research Manager',
  'Trader',
  'Risky Analyst',
  'Safe Analyst',
  'Neutral Analyst',
  'Risk Manager',
  'Portfolio Manager',
]

// Get date presets
export function getDatePresets(): DatePreset[] {
  const today = new Date()
  const formatDate = (d: Date) => d.toISOString().split('T')[0]

  const weekAgo = new Date(today)
  weekAgo.setDate(today.getDate() - 7)

  const monthAgo = new Date(today)
  monthAgo.setDate(today.getDate() - 30)

  const threeMonthsAgo = new Date(today)
  threeMonthsAgo.setDate(today.getDate() - 90)

  const yearStart = new Date(today.getFullYear(), 0, 1)

  return [
    { label: 'Last Week', start: formatDate(weekAgo), end: formatDate(today) },
    { label: 'Last Month', start: formatDate(monthAgo), end: formatDate(today) },
    { label: 'Last 3 Months', start: formatDate(threeMonthsAgo), end: formatDate(today) },
    { label: 'Year to Date', start: formatDate(yearStart), end: formatDate(today) },
    { label: 'Single Day Analysis', start: formatDate(today), end: formatDate(today) },
  ]
}

// Get default dates
export function getDefaultDates(): { start: string; end: string } {
  const today = new Date()
  const weekAgo = new Date(today)
  weekAgo.setDate(today.getDate() - 7)

  return {
    start: weekAgo.toISOString().split('T')[0],
    end: today.toISOString().split('T')[0],
  }
}
