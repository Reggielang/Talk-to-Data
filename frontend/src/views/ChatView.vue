<template>
  <div class="chat-view">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1 class="title">Talk to Data</h1>
        <el-button
          type="primary"
          :icon="Plus"
          circle
          @click="handleNewChat"
          :disabled="chatStore.isProcessing"
        />
      </div>

      <div class="sessions-list">
        <div
          v-for="session in chatStore.allSessions"
          :key="session.session_id"
          class="session-item"
          :class="{ active: session.session_id === chatStore.currentSessionId }"
          @click="handleSelectSession(session.session_id)"
        >
          <div class="session-info">
            <el-icon><ChatLineRound /></el-icon>
            <span class="session-title">{{ session.note || '新对话' }}</span>
          </div>
          <el-dropdown
            trigger="click"
            @command="(cmd) => handleSessionCommand(cmd, session.session_id)"
          >
            <el-icon :size="16" class="more-btn"><MoreFilled /></el-icon>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="delete">
                  <el-icon><Delete /></el-icon>
                  删除对话
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </aside>

    <!-- 主聊天区域 -->
    <main class="chat-main">
      <!-- 消息列表 -->
      <div ref="messagesContainer" class="messages-container">
        <div v-if="chatStore.currentMessages.length === 0" class="empty-state">
          <el-icon :size="64" color="#909399"><ChatDotRound /></el-icon>
          <p>开始提问，让 AI 帮你查询数据</p>
        </div>

        <MessageItem
          v-for="message in chatStore.currentMessages"
          :key="message.id"
          :message="message"
        />
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <div class="input-wrapper">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="1"
            :autosize="{ minRows: 1, maxRows: 6 }"
            placeholder="输入你的问题..."
            :disabled="chatStore.isProcessing"
            @keydown.enter.exact="handleSend"
            @keydown.enter.shift.prevent
          />
          <div class="input-actions">
            <span class="hint">Enter 发送，Shift + Enter 换行</span>
            <el-button
              text
              :disabled="chatStore.isProcessing || chatStore.currentMessages.length === 0"
              @click="handleClearMessages"
            >
              <el-icon><Delete /></el-icon>
              清空消息
            </el-button>
            <el-button
              type="primary"
              :icon="chatStore.isProcessing ? Loading : Promotion"
              :loading="chatStore.isProcessing"
              @click="handleSend"
              :disabled="!inputText.trim()"
            >
              {{ chatStore.isProcessing ? '处理中...' : '发送' }}
            </el-button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
import {
  Plus, ChatLineRound, MoreFilled, Delete, ChatDotRound, Promotion, Loading
} from '@element-plus/icons-vue'
import { useChatStore } from '@/stores'
import { chatApi } from '@/api'
import type { EventItem } from '@/types'
import MessageItem from '@/components/MessageItem.vue'

const chatStore = useChatStore()
const inputText = ref('')
const messagesContainer = ref<HTMLElement>()
const isCompleted = ref(false) // Track if current request is completed

// 滚动到底部
function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 创建新对话
function handleNewChat() {
  chatStore.createSession(`对话 ${chatStore.allSessions.length + 1}`)
}

// 选择会话
function handleSelectSession(sessionId: string) {
  if (chatStore.isProcessing) return
  chatStore.switchSession(sessionId)
}

// 会话操作
function handleSessionCommand(command: string, sessionId: string) {
  if (command === 'delete') {
    ElMessageBox.confirm('确定删除此对话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      chatStore.deleteSession(sessionId)
    })
  }
}

// 清空当前会话的消息
function handleClearMessages() {
  ElMessageBox.confirm('确定清空当前对话的所有消息吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    chatStore.clearCurrentMessages()
    inputText.value = ''
  })
}

// 发送消息
async function handleSend() {
  const text = inputText.value.trim()
  if (!text || chatStore.isProcessing) return

  console.log('[ChatView] handleSend called:', {
    text,
    isProcessing: chatStore.isProcessing,
    hasSession: !!chatStore.currentSession,
    currentMessageCount: chatStore.currentMessages.length
  })

  // 确保有当前会话
  if (!chatStore.currentSession) {
    console.log('[ChatView] Creating new session')
    chatStore.createSession()
  }

  // 添加用户消息
  chatStore.addUserMessage(text)
  inputText.value = ''
  scrollToBottom()

  // 添加助手消息
  const assistantMessage = chatStore.addAssistantMessage()
  scrollToBottom()

  console.log('[ChatView] After adding messages, current count:', chatStore.currentMessages.length)

  // 重置完成状态
  isCompleted.value = false

  try {
    // 创建 AbortController
    const controller = new AbortController()
    chatStore.setProcessing(true, controller)

    // 构建历史消息列表（排除当前正在发送的用户消息）
    console.log('[ChatView] All current messages before filtering:', chatStore.currentMessages.map((m, i) => ({
      index: i,
      role: m.role,
      content: m.content?.substring(0, 50) || '(empty)'
    })))

    const historyMessages = chatStore.currentMessages
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .slice(0, -2)  // 排除刚才添加的用户消息和助手消息
      .filter(m => m.content)  // 只保留有内容的消息
      .map(m => ({
        role: m.role,
        content: m.content
      }))

    // Debug logging
    console.log('[ChatView] Sending message:', {
      query: text,
      sessionId: chatStore.currentSessionId,
      currentMessageCount: chatStore.currentMessages.length,
      historyMessageCount: historyMessages.length,
      historyMessages: historyMessages.map((m, i) => ({
        index: i,
        role: m.role,
        content: m.content?.substring(0, 50) || '(empty)',
        contentLength: m.content?.length || 0
      }))
    })

    // 调用流式 API
    const { abort } = chatApi.streamWithAbort(
      {
        query: text,
        session_id: chatStore.currentSessionId || undefined,
        model_name: 'glm-4.6',
        stream: true,
        messages: historyMessages
      },
      // onMessage
      (event: MessageEvent) => {
        const data = event.data as any
        const eventType = data._sseEvent || data.type

        console.log('SSE Event:', { eventType, data })

        if (eventType === 'start') {
          // 开始事件 - 同步后端生成的 session_id
          console.log('Stream started:', data)
          if (data.session_id) {
            chatStore.updateCurrentSessionId(data.session_id)
            console.log('Session ID updated to:', data.session_id)
          }
        } else if (eventType === 'node') {
          // 节点事件 - 实时添加到消息中
          console.log('Node event:', data.Stage, data.Type)
          chatStore.addEventToMessage(assistantMessage.id, data)
          scrollToBottom()
        } else if (eventType === 'finish-step') {
          // 节点完成步骤
          console.log('Step finished:', data.node)
        } else if (eventType === 'complete') {
          // 完成事件 - 标记整个请求完成（只处理一次）
          if (!isCompleted.value) {
            isCompleted.value = true
            console.log('Complete event received:', data)
            const summary = extractSummaryFromMessage(assistantMessage.id)
            console.log('[ChatView] Extracted summary length:', summary.length)
            chatStore.updateAssistantMessage(assistantMessage.id, {
              status: 'completed',
              content: summary
            })
          } else {
            console.log('[ChatView] Complete event already processed, skipping')
          }
        } else if (eventType === 'error' || data.error) {
          // 错误事件
          console.error('Error event:', data)
          chatStore.updateAssistantMessage(assistantMessage.id, {
            status: 'error',
            error: data.error || 'Unknown error'
          })
        }
      },
      // onError
      (error: Error) => {
        console.error('Stream error:', error)
        chatStore.updateAssistantMessage(assistantMessage.id, {
          status: 'error',
          error: error.message
        })
        chatStore.setProcessing(false)
      },
      // onComplete
      () => {
        chatStore.setProcessing(false)
      }
    )

    // 保存 abort 函数到 store
    chatStore.setProcessing(true, controller as any)
  } catch (error: any) {
    console.error('Send message error:', error)
    chatStore.updateAssistantMessage(assistantMessage.id, {
      status: 'error',
      error: error.message || '发送失败'
    })
    chatStore.setProcessing(false)
  }
}

// 从事件中提取总结内容
function extractSummaryFromMessage(messageId: string): string {
  const message = chatStore.currentMessages.find(m => m.id === messageId)
  if (!message?.events) return ''

  const textDeltaEvent = message.events.find((e: any) => e.Type === 'text-delta')
  return textDeltaEvent?.Message?.Content || ''
}

onMounted(() => {
  scrollToBottom()
})
</script>

<style scoped lang="scss">
.chat-view {
  display: flex;
  height: 100%;
  background: #f5f7fa;
}

// ============== 侧边栏 ==============
.sidebar {
  width: 280px;
  background: #ffffff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;

  .title {
    font-size: 18px;
    font-weight: 600;
    color: #303133;
    margin: 0;
  }
}

.sessions-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.session-item {
  padding: 12px 16px;
  margin-bottom: 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: space-between;

  &:hover {
    background: #f5f7fa;
  }

  &.active {
    background: #ecf5ff;
    border: 1px solid #409eff;
  }

  .session-info {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1;
    min-width: 0;

    .session-title {
      font-size: 14px;
      color: #303133;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }

  .more-btn {
    color: #909399;
    padding: 4px;

    &:hover {
      color: #409eff;
    }
  }
}

// ============== 主聊天区域 ==============
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;

  p {
    margin-top: 16px;
    font-size: 14px;
  }
}

// ============== 输入区域 ==============
.input-area {
  border-top: 1px solid #e4e7ed;
  background: #ffffff;
  padding: 16px 24px;
}

.input-wrapper {
  max-width: 900px;
  margin: 0 auto;
}

:deep(.el-textarea__inner) {
  resize: none;
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.6;
}

.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  gap: 12px;
}

.hint {
  font-size: 12px;
  color: #909399;
  flex: 1;
}
</style>
