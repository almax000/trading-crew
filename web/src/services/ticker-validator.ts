/**
 * Ticker Validator - Stock Code Validation Service
 *
 * Validates stock codes and retrieves stock names via HTTP APIs.
 * - A-Share: Eastmoney HTTP API
 * - US/HK: Yahoo Finance API
 */

import type { Market } from '../types'

interface ValidationResult {
  valid: boolean
  normalized: string
  name: string
  error: string
}

// A-Share code format validation
function validateAShareFormat(code: string): boolean {
  code = code.trim()
  if (!/^\d{6}$/.test(code)) {
    return false
  }

  const prefix = code.substring(0, 3)
  const validPrefixes = ['600', '601', '603', '605', '688', '000', '001', '002', '300']
  return validPrefixes.includes(prefix)
}

// US stock code format validation
function validateUSFormat(code: string): boolean {
  code = code.trim().toUpperCase()
  // Standard ticker: 1-5 letters
  if (/^[A-Z]{1,5}$/.test(code)) {
    return true
  }
  // Class-based ticker: e.g. BRK.B, BRK-B
  if (/^[A-Z]{1,4}[.\-][A-Z]$/.test(code)) {
    return true
  }
  return false
}

// HK stock code format validation
function validateHKFormat(code: string): boolean {
  code = code.trim().toUpperCase()
  // Standard format: number.HK
  if (/^\d{4,5}\.HK$/.test(code)) {
    return true
  }
  // Also accept plain number (auto-append .HK)
  if (/^\d{1,5}$/.test(code)) {
    return true
  }
  return false
}

// Normalize ticker code
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
    // A-Share: keep as-is
    return code
  }
}

/**
 * Validate A-Share code and get name
 * Uses Eastmoney HTTP API
 */
async function validateAShare(ticker: string): Promise<ValidationResult> {
  const normalized = ticker

  // Try Shanghai (secid=1.xxx)
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
    // Continue trying Shenzhen
  }

  // Try Shenzhen (secid=0.xxx)
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
    // API call failed
  }

  // Eastmoney API may be unstable, try Sina Finance as fallback
  try {
    // Determine Shanghai or Shenzhen
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

    // Parse Sina Finance response format: var hq_str_sh600519="Kweichow Moutai,..."
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
    // Sina API also failed
  }

  // If format is correct but name unavailable, still consider valid
  return {
    valid: true,
    normalized,
    name: '',
    error: '',
  }
}

/**
 * Validate US/HK stock code and get name
 * Uses Yahoo Finance API
 */
async function validateUSHK(ticker: string, market: Market): Promise<ValidationResult> {
  const normalized = normalizeTicker(ticker, market)

  try {
    const url = `https://query1.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(normalized)}&quotesCount=5&newsCount=0`
    const res = await fetch(url, { signal: AbortSignal.timeout(5000) })
    const data = await res.json() as any

    if (data.quotes && data.quotes.length > 0) {
      // Find exact match
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

      // If no exact match, use first result
      const first = data.quotes[0]
      return {
        valid: true,
        normalized,
        name: first.shortname || first.longname || '',
        error: '',
      }
    }
  } catch (e) {
    // API call failed
    console.error('Yahoo Finance API error:', e)
  }

  // If format is correct but name unavailable, still consider valid
  return {
    valid: true,
    normalized,
    name: '',
    error: '',
  }
}

/**
 * Validate ticker format only (no name lookup, fast)
 */
export function validateTickerFormat(ticker: string, market: Market): ValidationResult {
  ticker = ticker.trim()

  if (!ticker) {
    return { valid: false, normalized: '', name: '', error: 'Please enter a stock code' }
  }

  if (market === 'A-share') {
    if (!validateAShareFormat(ticker)) {
      return {
        valid: false,
        normalized: '',
        name: '',
        error: 'A-Share code should be 6 digits (e.g. 600519, 000001)',
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
        error: 'US stock code should be 1-5 letters (e.g. AAPL, TSLA)',
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
        error: 'HK stock code should be 4-5 digits (e.g. 0700, 9988)',
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
    error: `Unsupported market type: ${market}`,
  }
}

/**
 * Validate ticker and get stock name
 */
export async function validateAndGetName(ticker: string, market: Market): Promise<ValidationResult> {
  // Format validation first
  const formatResult = validateTickerFormat(ticker, market)
  if (!formatResult.valid) {
    return formatResult
  }

  const normalized = formatResult.normalized

  // Call different APIs based on market
  if (market === 'A-share') {
    return validateAShare(normalized)
  } else if (market === 'US' || market === 'HK') {
    return validateUSHK(normalized, market)
  }

  return formatResult
}
