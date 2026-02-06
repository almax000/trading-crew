/**
 * Ticker Validator - 股票代码验证服务
 *
 * 使用 HTTP API 验证股票代码并获取股票名称。
 * - A股: 东方财富 HTTP API
 * - 美股/港股: Yahoo Finance API
 */

import type { Market } from '../types'

interface ValidationResult {
  valid: boolean
  normalized: string
  name: string
  error: string
}

// A股代码格式验证
function validateAShareFormat(code: string): boolean {
  code = code.trim()
  if (!/^\d{6}$/.test(code)) {
    return false
  }

  const prefix = code.substring(0, 3)
  const validPrefixes = ['600', '601', '603', '605', '688', '000', '001', '002', '300']
  return validPrefixes.includes(prefix)
}

// 美股代码格式验证
function validateUSFormat(code: string): boolean {
  code = code.trim().toUpperCase()
  // 标准股票代码: 1-5 个字母
  if (/^[A-Z]{1,5}$/.test(code)) {
    return true
  }
  // 带类别的代码: 如 BRK.B, BRK-B
  if (/^[A-Z]{1,4}[.\-][A-Z]$/.test(code)) {
    return true
  }
  return false
}

// 港股代码格式验证
function validateHKFormat(code: string): boolean {
  code = code.trim().toUpperCase()
  // 标准格式: 数字.HK
  if (/^\d{4,5}\.HK$/.test(code)) {
    return true
  }
  // 也接受纯数字 (自动补 .HK)
  if (/^\d{1,5}$/.test(code)) {
    return true
  }
  return false
}

// 标准化股票代码
function normalizeTicker(code: string, market: Market): string {
  code = code.trim()

  if (market === 'US') {
    return code.toUpperCase()
  } else if (market === 'HK') {
    code = code.toUpperCase()
    const cleanCode = code.replace('.HK', '')
    const paddedCode = cleanCode.padStart(4, '0')
    return `${paddedCode}.HK`
  } else {
    // A股保持原样
    return code
  }
}

/**
 * 验证 A股代码并获取名称
 * 使用东方财富 HTTP API
 */
async function validateAShare(ticker: string): Promise<ValidationResult> {
  const normalized = ticker

  // 尝试上海 (secid=1.xxx)
  try {
    const url = `https://push2.eastmoney.com/api/qt/stock/get?secid=1.${ticker}&fields=f58`
    const res = await fetch(url, { signal: AbortSignal.timeout(5000) })
    const data = await res.json() as any

    if (data.data?.f58) {
      return {
        valid: true,
        normalized,
        name: data.data.f58,
        error: '',
      }
    }
  } catch {
    // 继续尝试深圳
  }

  // 尝试深圳 (secid=0.xxx)
  try {
    const url = `https://push2.eastmoney.com/api/qt/stock/get?secid=0.${ticker}&fields=f58`
    const res = await fetch(url, { signal: AbortSignal.timeout(5000) })
    const data = await res.json() as any

    if (data.data?.f58) {
      return {
        valid: true,
        normalized,
        name: data.data.f58,
        error: '',
      }
    }
  } catch {
    // API 调用失败
  }

  // 东方财富 API 可能不稳定，尝试新浪财经作为 fallback
  try {
    // 判断是上海还是深圳
    const prefix = ticker.substring(0, 1)
    const marketCode = ['6'].includes(prefix) ? 'sh' : 'sz'
    const url = `https://hq.sinajs.cn/list=${marketCode}${ticker}`

    const res = await fetch(url, {
      signal: AbortSignal.timeout(5000),
      headers: {
        'Referer': 'https://finance.sina.com.cn',
      },
    })
    const text = await res.text()

    // 解析新浪财经返回格式: var hq_str_sh600519="贵州茅台,..."
    const match = text.match(/="([^"]+)"/)
    if (match && match[1]) {
      const parts = match[1].split(',')
      if (parts.length > 0 && parts[0]) {
        return {
          valid: true,
          normalized,
          name: parts[0],
          error: '',
        }
      }
    }
  } catch {
    // 新浪 API 也失败了
  }

  // 如果格式正确但无法获取名称，仍然认为有效
  return {
    valid: true,
    normalized,
    name: '',
    error: '',
  }
}

/**
 * 验证美股/港股代码并获取名称
 * 使用 Yahoo Finance API
 */
async function validateUSHK(ticker: string, market: Market): Promise<ValidationResult> {
  const normalized = normalizeTicker(ticker, market)

  try {
    const url = `https://query1.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(normalized)}&quotesCount=5&newsCount=0`
    const res = await fetch(url, { signal: AbortSignal.timeout(5000) })
    const data = await res.json() as any

    if (data.quotes && data.quotes.length > 0) {
      // 查找精确匹配
      const exactMatch = data.quotes.find((q: any) =>
        q.symbol?.toUpperCase() === normalized.toUpperCase()
      )

      if (exactMatch) {
        return {
          valid: true,
          normalized,
          name: exactMatch.shortname || exactMatch.longname || '',
          error: '',
        }
      }

      // 如果没有精确匹配，使用第一个结果
      const first = data.quotes[0]
      return {
        valid: true,
        normalized,
        name: first.shortname || first.longname || '',
        error: '',
      }
    }
  } catch (e) {
    // API 调用失败
    console.error('Yahoo Finance API error:', e)
  }

  // 如果格式正确但无法获取名称，仍然认为有效
  return {
    valid: true,
    normalized,
    name: '',
    error: '',
  }
}

/**
 * 仅验证股票代码格式（不查询名称，速度快）
 */
export function validateTickerFormat(ticker: string, market: Market): ValidationResult {
  ticker = ticker.trim()

  if (!ticker) {
    return { valid: false, normalized: '', name: '', error: '请输入股票代码' }
  }

  if (market === 'A-share') {
    if (!validateAShareFormat(ticker)) {
      return {
        valid: false,
        normalized: '',
        name: '',
        error: 'A股代码应为6位数字（如 600519、000001）',
      }
    }
    return {
      valid: true,
      normalized: normalizeTicker(ticker, market),
      name: '',
      error: '',
    }
  }

  if (market === 'US') {
    if (!validateUSFormat(ticker)) {
      return {
        valid: false,
        normalized: '',
        name: '',
        error: '美股代码应为1-5位字母（如 AAPL、TSLA）',
      }
    }
    return {
      valid: true,
      normalized: normalizeTicker(ticker, market),
      name: '',
      error: '',
    }
  }

  if (market === 'HK') {
    if (!validateHKFormat(ticker)) {
      return {
        valid: false,
        normalized: '',
        name: '',
        error: '港股代码应为4-5位数字（如 0700、9988）',
      }
    }
    return {
      valid: true,
      normalized: normalizeTicker(ticker, market),
      name: '',
      error: '',
    }
  }

  return {
    valid: false,
    normalized: '',
    name: '',
    error: `不支持的市场类型: ${market}`,
  }
}

/**
 * 验证股票代码并获取名称
 */
export async function validateAndGetName(ticker: string, market: Market): Promise<ValidationResult> {
  // 先做格式验证
  const formatResult = validateTickerFormat(ticker, market)
  if (!formatResult.valid) {
    return formatResult
  }

  const normalized = formatResult.normalized

  // 根据市场调用不同的 API
  if (market === 'A-share') {
    return validateAShare(normalized)
  } else if (market === 'US' || market === 'HK') {
    return validateUSHK(normalized, market)
  }

  return formatResult
}
