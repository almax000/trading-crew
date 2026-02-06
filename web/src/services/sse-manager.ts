/**
 * SSE Manager - Server-Sent Events 管理器
 *
 * 管理 SSE 连接，支持订阅和发布 Session 状态更新。
 */

import type { Session } from '../types'

type SSEController = ReadableStreamDefaultController<Uint8Array>

export class SSEManager {
  private subscribers = new Map<string, Set<SSEController>>()

  /**
   * 创建 SSE 订阅流
   */
  subscribe(sessionId: string): ReadableStream<Uint8Array> {
    return new ReadableStream({
      start: (controller) => {
        if (!this.subscribers.has(sessionId)) {
          this.subscribers.set(sessionId, new Set())
        }
        this.subscribers.get(sessionId)!.add(controller)
      },
      cancel: () => {
        const controllers = this.subscribers.get(sessionId)
        if (controllers) {
          // 注意：cancel 回调中无法直接获取 controller 引用
          // 这里通过清理空集合来处理
          if (controllers.size === 0) {
            this.subscribers.delete(sessionId)
          }
        }
      },
    })
  }

  /**
   * 取消订阅（手动调用）
   */
  unsubscribe(sessionId: string, controller: SSEController): void {
    const controllers = this.subscribers.get(sessionId)
    if (controllers) {
      controllers.delete(controller)
      if (controllers.size === 0) {
        this.subscribers.delete(sessionId)
      }
    }
  }

  /**
   * 发布更新到所有订阅者
   */
  publish(sessionId: string, data: Session): void {
    const controllers = this.subscribers.get(sessionId)
    if (!controllers || controllers.size === 0) {
      return
    }

    const message = new TextEncoder().encode(
      `data: ${JSON.stringify(data)}\n\n`
    )

    for (const controller of controllers) {
      try {
        controller.enqueue(message)
      } catch {
        // 连接可能已关闭，忽略错误
        controllers.delete(controller)
      }
    }
  }

  /**
   * 发送心跳包到所有订阅者
   */
  sendHeartbeat(sessionId: string): void {
    const controllers = this.subscribers.get(sessionId)
    if (!controllers || controllers.size === 0) {
      return
    }

    const message = new TextEncoder().encode(': heartbeat\n\n')

    for (const controller of controllers) {
      try {
        controller.enqueue(message)
      } catch {
        controllers.delete(controller)
      }
    }
  }

  /**
   * 关闭指定 Session 的所有连接
   */
  closeSession(sessionId: string): void {
    const controllers = this.subscribers.get(sessionId)
    if (!controllers) {
      return
    }

    for (const controller of controllers) {
      try {
        controller.close()
      } catch {
        // 忽略关闭错误
      }
    }

    this.subscribers.delete(sessionId)
  }

  /**
   * 获取订阅者数量
   */
  getSubscriberCount(sessionId: string): number {
    return this.subscribers.get(sessionId)?.size || 0
  }
}

// 全局单例
export const sseManager = new SSEManager()
