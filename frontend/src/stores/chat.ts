import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ChatMessage, Session } from '@/types'

// 生成 UUID 作为 ID（去掉连字符，限制在30字符以内）
function generateId(): string {
  // 生成 UUID 并去掉连字符，然后截断到30字符
  return 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'.replace(/[x]/g, () => {
    return Math.random().toString(16)[2]
  }).substring(0, 30)
}

export const useChatStore = defineStore('chat', () => {
  // ============== 状态 ==============

  const sessions = ref<Map<string, Session>>(new Map())
  const currentSessionId = ref<string | null>(null)
  const isProcessing = ref(false)
  const abortController = ref<AbortController | null>(null)

  // ============== 计算属性 ==============

  const currentSession = computed(() => {
    if (!currentSessionId.value) return null
    return sessions.value.get(currentSessionId.value) || null
  })

  const currentMessages = computed(() => {
    return currentSession.value?.messages || []
  })

  const allSessions = computed(() => {
    return Array.from(sessions.value.values()).sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    )
  })

  // ============== 方法 ==============

  /**
   * 创建新会话
   */
  function createSession(note?: string): Session {
    const session: Session = {
      session_id: generateId(),
      user_sid: generateId(),
      user_email: 'user@example.com',
      note,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      expired_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
      messages: []
    }

    sessions.value.set(session.session_id, session)
    currentSessionId.value = session.session_id

    return session
  }

  /**
   * 切换会话
   */
  function switchSession(sessionId: string) {
    if (sessions.value.has(sessionId)) {
      currentSessionId.value = sessionId
    }
  }

  /**
   * 删除会话
   */
  function deleteSession(sessionId: string) {
    sessions.value.delete(sessionId)
    if (currentSessionId.value === sessionId) {
      const sessionsList = Array.from(sessions.value.keys())
      currentSessionId.value = sessionsList.length > 0 ? sessionsList[0] : null
    }
  }

  /**
   * 添加用户消息
   */
  function addUserMessage(content: string): ChatMessage {
    console.log('[ChatStore] addUserMessage called:', {
      contentLength: content?.length || 0,
      content: content?.substring(0, 50) || '(empty)',
      currentMessageCount: currentSession.value?.messages?.length || 0,
      sessionId: currentSessionId.value
    })

    const message: ChatMessage = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date(),
      status: 'completed'
    }

    if (currentSession.value) {
      if (!currentSession.value.messages) {
        currentSession.value.messages = []
      }
      currentSession.value.messages.push(message)
      console.log('[ChatStore] User message added, new count:', currentSession.value.messages.length)
    }

    return message
  }

  /**
   * 添加助手消息（处理中）
   */
  function addAssistantMessage(): ChatMessage {
    const message: ChatMessage = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      status: 'processing',
      events: []
    }

    if (currentSession.value) {
      if (!currentSession.value.messages) {
        currentSession.value.messages = []
      }
      currentSession.value.messages.push(message)
    }

    return message
  }

  /**
   * 更新助手消息
   */
  function updateAssistantMessage(messageId: string, updates: Partial<ChatMessage>) {
    console.log('[ChatStore] updateAssistantMessage called:', {
      messageId,
      status: updates.status,
      hasContent: !!updates.content,
      contentLength: updates.content?.length || 0
    })

    if (!currentSession.value) return

    const message = currentSession.value.messages?.find(m => m.id === messageId)
    if (message) {
      Object.assign(message, updates)
      console.log('[ChatStore] Assistant message updated')
    } else {
      console.warn('[ChatStore] Assistant message not found:', messageId)
    }
  }

  /**
   * 添加事件到消息（确保响应式更新）
   */
  function addEventToMessage(messageId: string, event: any) {
    if (!currentSession.value) return

    const messages = currentSession.value.messages
    if (!messages) return

    const messageIndex = messages.findIndex(m => m.id === messageId)
    if (messageIndex >= 0) {
      const message = messages[messageIndex]
      if (!message.events) {
        message.events = []
      }
      // 使用 concat 触发响应式更新
      message.events = [...message.events, event]
    }
  }

  /**
   * 设置处理状态
   */
  function setProcessing(processing: boolean, controller?: AbortController) {
    isProcessing.value = processing
    if (controller) {
      abortController.value = controller
    } else if (!processing) {
      abortController.value = null
    }
  }

  /**
   * 取消当前请求
   */
  function abortRequest() {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    isProcessing.value = false
  }

  /**
   * 清空当前会话的消息
   */
  function clearCurrentMessages() {
    console.log('[ChatStore] clearCurrentMessages called')
    if (currentSession.value) {
      const oldCount = currentSession.value.messages?.length || 0
      currentSession.value.messages = []
      currentSession.value.updated_at = new Date().toISOString()
      console.log('[ChatStore] Cleared', oldCount, 'messages from current session')
    }
  }

  /**
   * 更新当前会话 ID（用于同步后端生成的 session_id）
   */
  function updateCurrentSessionId(newSessionId: string) {
    console.log('[ChatStore] updateCurrentSessionId called:', {
      oldId: currentSessionId.value,
      newId: newSessionId,
      hasCurrentSession: !!currentSession.value,
      currentMessagesCount: currentSession.value?.messages?.length || 0
    })

    if (currentSessionId.value && currentSession.value && currentSessionId.value !== newSessionId) {
      // 后端返回了不同的 session_id，需要迁移会话数据
      const oldSession = currentSession.value
      const oldMessages = oldSession.messages || []

      console.log('[ChatStore] Migrating session, messages:', oldMessages.map((m, i) => ({
        index: i,
        role: m.role,
        content: m.content?.substring(0, 30) || '(empty)'
      })))

      // 删除旧的 session
      sessions.value.delete(currentSessionId.value)

      // 使用后端的 session_id 重新存储会话
      const newSession: Session = {
        ...oldSession,
        session_id: newSessionId,
        updated_at: new Date().toISOString()
      }
      sessions.value.set(newSessionId, newSession)
      currentSessionId.value = newSessionId

      console.log('[ChatStore] Session ID migrated, new session has', newSession.messages?.length || 0, 'messages')
    } else if (!currentSessionId.value) {
      // 如果没有当前会话，设置新的 session_id
      currentSessionId.value = newSessionId
      console.log('[ChatStore] Set new session ID:', newSessionId)
    } else {
      console.log('[ChatStore] Session ID unchanged:', currentSessionId.value)
    }
  }

  /**
   * 重置状态
   */
  function reset() {
    sessions.value.clear()
    currentSessionId.value = null
    isProcessing.value = false
    abortController.value = null
  }

  return {
    // 状态
    sessions,
    currentSessionId,
    isProcessing,
    abortController,

    // 计算属性
    currentSession,
    currentMessages,
    allSessions,

    // 方法
    createSession,
    switchSession,
    deleteSession,
    addUserMessage,
    addAssistantMessage,
    updateAssistantMessage,
    addEventToMessage,
    setProcessing,
    abortRequest,
    clearCurrentMessages,
    updateCurrentSessionId,
    reset
  }
})
