import client from './client'
import type {
  ChatRequest,
  ChatResponse,
  SessionCreateRequest,
  SessionResponse,
  MessageResponse,
  EventResponse
} from '@/types'

// ============== 聊天 API ==============

export const chatApi = {
  /**
   * 执行查询（非流式）
   */
  async query(request: ChatRequest): Promise<ChatResponse> {
    const response = await client.post<ChatResponse>('/chat/query', request)
    return response.data
  },

  /**
   * 执行查询（流式）
   * 返回 EventSource 和用于手动关闭的函数
   */
  stream(
    request: ChatRequest,
    onMessage: (event: MessageEvent) => void,
    onError: (error: Error) => void,
    onComplete: () => void
  ): () => void {
    const url = new URL('/chat/stream', client.defaults.baseURL || window.location.origin)

    // 使用 fetch 获取可读流
    fetch(url.toString(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(request)
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error('No reader available')
        }

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()

          if (done) {
            onComplete()
            break
          }

          buffer += decoder.decode(value, { stream: true })

          // 处理 SSE 格式
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('event:')) {
              const event = line.substring(6).trim()
              continue
            }
            if (line.startsWith('data:')) {
              const data = line.substring(5).trim()
              try {
                const parsed = JSON.parse(data)
                onMessage({ data: parsed } as MessageEvent)
              } catch (e) {
                // 忽略解析错误
              }
            }
          }
        }
      })
      .catch((error) => {
        onError(error)
      })

    // 返回取消函数（fetch 不支持直接取消，这里返回空函数）
    return () => {
      // 实际取消需要使用 AbortController
    }
  },

  /**
   * 带取消功能的流式请求
   */
  streamWithAbort(
    request: ChatRequest,
    onMessage: (event: MessageEvent) => void,
    onError: (error: Error) => void,
    onComplete: () => void
  ): { abort: () => void } {
    const controller = new AbortController()
    const url = new URL('/chat/stream', client.defaults.baseURL || window.location.origin)

    fetch(url.toString(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(request),
      signal: controller.signal
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error('No reader available')
        }

        const decoder = new TextDecoder()
        let buffer = ''
        let currentEvent = ''

        while (true) {
          const { done, value } = await reader.read()

          if (done) {
            onComplete()
            break
          }

          buffer += decoder.decode(value, { stream: true })

          // 处理 SSE 格式
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed) continue

            if (trimmed.startsWith('event:')) {
              // 保存事件类型
              currentEvent = trimmed.substring(6).trim()
            } else if (trimmed.startsWith('data:')) {
              // 解析数据并附加事件类型
              const dataStr = trimmed.substring(5).trim()
              try {
                const parsed = JSON.parse(dataStr)
                // 将 SSE 事件类型附加到数据上
                parsed._sseEvent = currentEvent
                onMessage({ data: parsed } as MessageEvent)
              } catch (e) {
                // 忽略解析错误
              }
              // 重置事件类型
              currentEvent = ''
            }
          }
        }
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          onError(error)
        }
      })

    return { abort: () => controller.abort() }
  }
}

// ============== 会话 API ==============

export const sessionApi = {
  /**
   * 创建新会话
   */
  async create(request: SessionCreateRequest): Promise<SessionResponse> {
    const response = await client.post<SessionResponse>('/chat/sessions', request)
    return response.data
  },

  /**
   * 获取会话信息
   */
  async get(sessionId: string): Promise<SessionResponse> {
    const response = await client.get<SessionResponse>(`/chat/sessions/${sessionId}`)
    return response.data
  },

  /**
   * 获取会话消息历史
   */
  async getMessages(sessionId: string, limit = 100): Promise<MessageResponse[]> {
    const response = await client.get<MessageResponse[]>(
      `/chat/sessions/${sessionId}/messages`,
      { params: { limit } }
    )
    return response.data
  },

  /**
   * 获取会话事件
   */
  async getEvents(sessionId: string, messageId?: string): Promise<EventResponse[]> {
    const response = await client.get<EventResponse[]>(
      `/chat/sessions/${sessionId}/events`,
      { params: { message_id: messageId } }
    )
    return response.data
  }
}

// ============== 健康检查 API ==============

export const healthApi = {
  async check(): Promise<{ status: string; timestamp: string; version: string }> {
    const response = await client.get('/health')
    return response.data
  }
}
