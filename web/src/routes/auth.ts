/**
 * Auth Routes - Authentication API
 */

import { Hono } from 'hono'
import type { LoginRequest, LoginResponse } from '../types'
import { getInviteCodes } from '../config'

export const authRoutes = new Hono()

/**
 * POST /api/auth/login
 * User login
 */
authRoutes.post('/login', async (c) => {
  const body = await c.req.json<LoginRequest>()
  const { username, password } = body

  const trimmedUsername = username?.trim() || ''
  const trimmedPassword = password?.trim() || ''

  if (!trimmedUsername || !trimmedPassword) {
    const res: LoginResponse = {
      success: false,
      message: 'Please enter username and password',
    }
    return c.json(res)
  }

  const inviteCodes = getInviteCodes()
  const storedPassword = inviteCodes.get(trimmedUsername)

  if (storedPassword && storedPassword === trimmedPassword) {
    const res: LoginResponse = {
      success: true,
      message: `Welcome, ${trimmedUsername}`,
      username: trimmedUsername,
    }
    return c.json(res)
  }

  const res: LoginResponse = {
    success: false,
    message: 'Invalid username or password',
  }
  return c.json(res)
})

/**
 * POST /api/auth/logout
 * User logout
 */
authRoutes.post('/logout', (c) => {
  return c.json({ success: true })
})
