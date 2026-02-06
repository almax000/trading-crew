/**
 * TradingCrew Web UI - Configuration
 */

import type { DatePreset } from './types'

// 服务端口
export const WEB_PORT = parseInt(process.env.PORT || process.env.WEB_PORT || '1788', 10)

// Python 分析服务地址
export const ANALYSIS_SERVICE_URL = process.env.ANALYSIS_SERVICE_URL || 'http://127.0.0.1:8000'

// 数据目录（用于 Session 持久化）
export const DATA_DIR = process.env.DATA_DIR || './data'

// 从环境变量读取邀请码
export function getInviteCodes(): Map<string, string> {
  const codes = new Map<string, string>()

  // 格式: INVITE_CODES=user1:pass1,user2:pass2
  const codesStr = process.env.INVITE_CODES || ''
  if (codesStr) {
    for (const pair of codesStr.split(',')) {
      const [user, pwd] = pair.trim().split(':', 2)
      if (user && pwd) {
        codes.set(user.trim(), pwd.trim())
      }
    }
  }

  // 兼容旧格式: INVITE_CODE_N=user:pass
  for (const [key, value] of Object.entries(process.env)) {
    if (key.startsWith('INVITE_CODE_') && value) {
      const [user, pwd] = value.split(':', 2)
      if (user && pwd) {
        codes.set(user.trim(), pwd.trim())
      }
    }
  }

  // 本地开发默认用户
  if (codes.size === 0 && !process.env.RAILWAY_ENVIRONMENT) {
    codes.set('demo', 'tradingcrew2024')
  }

  return codes
}

// 从环境变量读取管理员用户
export function getAdminUsers(): Set<string> {
  const admins = new Set<string>()

  // 格式: ADMIN_USERS=user1,user2,user3
  const adminStr = process.env.ADMIN_USERS || ''
  if (adminStr) {
    for (const user of adminStr.split(',')) {
      if (user.trim()) {
        admins.add(user.trim())
      }
    }
  }

  // 本地开发默认管理员
  if (admins.size === 0 && !process.env.RAILWAY_ENVIRONMENT) {
    admins.add('demo')
  }

  return admins
}

// 市场选项
export const MARKET_OPTIONS: Record<string, string> = {
  'A股': 'A-share',
  '美股': 'US',
  '港股': 'HK',
}

// 分析师选项
export const ANALYST_OPTIONS: Record<string, string> = {
  '市场分析师': 'market',
  '舆情分析师': 'social',
  '新闻分析师': 'news',
  '基本面分析师': 'fundamentals',
}

// Agent 显示名称映射
export const AGENT_DISPLAY_NAMES: Record<string, string> = {
  'Market Analyst': '市场分析师',
  'Social Analyst': '舆情分析师',
  'News Analyst': '新闻分析师',
  'Fundamentals Analyst': '基本面分析师',
  'Bull Researcher': '看多研究员',
  'Bear Researcher': '看空研究员',
  'Research Manager': '研究主管',
  'Trader': '交易员',
  'Risky Analyst': '激进风控',
  'Safe Analyst': '保守风控',
  'Neutral Analyst': '中性风控',
  'Risk Manager': '风控主管',
  'Portfolio Manager': '组合经理',
}

// Agent 执行顺序
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

// 获取日期预设
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
    { label: '最近一周', start: formatDate(weekAgo), end: formatDate(today) },
    { label: '最近一月', start: formatDate(monthAgo), end: formatDate(today) },
    { label: '最近三月', start: formatDate(threeMonthsAgo), end: formatDate(today) },
    { label: '今年以来', start: formatDate(yearStart), end: formatDate(today) },
    { label: '单日分析', start: formatDate(today), end: formatDate(today) },
  ]
}

// 获取默认日期
export function getDefaultDates(): { start: string; end: string } {
  const today = new Date()
  const weekAgo = new Date(today)
  weekAgo.setDate(today.getDate() - 7)

  return {
    start: weekAgo.toISOString().split('T')[0],
    end: today.toISOString().split('T')[0],
  }
}
