/**
 * Auth Routes - 认证相关 API
 */

import { Hono } from 'hono'
import type { LoginRequest, LoginResponse } from '../types'
import { getInviteCodes } from '../config'

export const authRoutes = new Hono()

/**
 * POST /api/auth/login
 * 用户登录
 */
authRoutes.post('/login', async (c) => {
  const body = await c.req.json<LoginRequest>()
  const { username, password } = body

  const trimmedUsername = username?.trim() || ''
  const trimmedPassword = password?.trim() || ''

  if (!trimmedUsername || !trimmedPassword) {
    const res: LoginResponse = {
      success: false,
      message: '请输入用户名和密码',
    }
    return c.json(res)
  }

  const inviteCodes = getInviteCodes()
  const storedPassword = inviteCodes.get(trimmedUsername)

  if (storedPassword && storedPassword === trimmedPassword) {
    const res: LoginResponse = {
      success: true,
      message: `欢迎，${trimmedUsername}`,
      username: trimmedUsername,
    }
    return c.json(res)
  }

  const res: LoginResponse = {
    success: false,
    message: '用户名或密码错误',
  }
  return c.json(res)
})

/**
 * POST /api/auth/logout
 * 用户登出
 */
authRoutes.post('/logout', (c) => {
  return c.json({ success: true })
})
