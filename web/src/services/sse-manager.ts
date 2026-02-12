/**
 * SSE Manager - Server-Sent Events Manager
 *
 * Manages SSE connections, supports subscribe and publish for session status updates.
 */

import type { Session } from '../types'

type SSEController = ReadableStreamDefaultController<Uint8Array>

export class SSEManager {
  private subscribers = new Map<string, Set<SSEController>>()

  /**
   * Create SSE subscription stream
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
          // Note: cannot directly get controller reference in cancel callback
          // Handle by cleaning up empty sets
          if (controllers.size === 0) {
            this.subscribers.delete(sessionId)
          }
        }
      },
    })
  }

  /**
   * Unsubscribe (manual call)
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
   * Publish update to all subscribers
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
        // Connection may already be closed, ignore error
        controllers.delete(controller)
      }
    }
  }

  /**
   * Send heartbeat to all subscribers
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
   * Close all connections for a session
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
        // Ignore close errors
      }
    }

    this.subscribers.delete(sessionId)
  }

  /**
   * Get subscriber count
   */
  getSubscriberCount(sessionId: string): number {
    return this.subscribers.get(sessionId)?.size || 0
  }
}

// Global singleton
export const sseManager = new SSEManager()
