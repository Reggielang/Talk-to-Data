<template>
  <div class="message-item" :class="`message-${message.role}`">
    <!-- 用户消息 -->
    <div v-if="message.role === 'user'" class="user-message">
      <div class="message-content">
        {{ message.content }}
      </div>
      <div class="message-time">
        {{ formatTime(message.timestamp) }}
      </div>
    </div>

    <!-- 助手消息 -->
    <div v-else class="assistant-message">
      <div class="message-header">
        <el-icon class="avatar"><User /></el-icon>
        <span class="role">AI 助手</span>
        <el-tag
          v-if="message.status === 'processing'"
          type="warning"
          size="small"
          effect="plain"
        >
          处理中
        </el-tag>
        <el-tag
          v-else-if="message.status === 'error'"
          type="danger"
          size="small"
          effect="plain"
        >
          错误
        </el-tag>
      </div>

      <!-- 错误状态 -->
      <div v-if="message.status === 'error'" class="error-state">
        <el-icon><CircleClose /></el-icon>
        <span>{{ message.error || '处理出错，请重试' }}</span>
      </div>

      <!-- 处理中状态提示（仅在还没有事件时显示） -->
      <div v-else-if="message.status === 'processing' && (!message.events || message.events.length === 0)" class="processing-state">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在分析您的需求...</span>
      </div>

      <!-- 显示事件详情（处理中或完成状态，有事件时） -->
      <div v-if="message.events && message.events.length > 0" class="events-container">
        <!-- 处理中状态指示器 -->
        <div v-if="message.status === 'processing'" class="processing-indicator">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>处理中...</span>
        </div>

        <!-- 按阶段显示事件 -->
        <template v-for="(event, index) in groupedEvents" :key="index">
          <!-- Block 阶段 -->
          <div v-if="event.Stage === 'Block'" class="event-section">
            <div class="event-header">
              <el-icon><WarningFilled /></el-icon>
              <span>问题检查</span>
            </div>
            <div class="event-content">
              <div v-if="event.StageOutput?.Blocked" class="blocked-message">
                <el-alert type="warning" :closable="false" show-icon>
                  <template #title>问题被拦截</template>
                  <div>{{ event.StageOutput.BlockReason }}</div>
                </el-alert>
              </div>
              <div v-else class="info-item">
                <el-icon color="#67c23a"><CircleCheck /></el-icon>
                <span class="value">问题检查通过</span>
              </div>
            </div>
          </div>

          <!-- Understand 阶段 -->
          <div v-if="event.Stage === 'Understand'" class="event-section">
            <div class="event-header">
              <el-icon><View /></el-icon>
              <span>理解阶段</span>
            </div>
            <div class="event-content">
              <div v-if="event.StageOutput?.RephrasedUserQuery" class="info-item">
                <span class="label">重新表述的问题：</span>
                <span class="value">{{ event.StageOutput.RephrasedUserQuery }}</span>
              </div>
              <div v-if="event.StageOutput?.intent" class="info-item">
                <span class="label">意图识别：</span>
                <el-tag size="small" type="info">{{ event.StageOutput.intent }}</el-tag>
              </div>
            </div>
          </div>

          <!-- DataQuery 阶段 -->
          <div v-if="event.Stage === 'DataQuery'" class="event-section">
            <div class="event-header">
              <el-icon><DataAnalysis /></el-icon>
              <span>数据查询</span>
            </div>
            <div class="event-content">
              <div v-if="event.StageOutput?.GeneratedSql" class="sql-block">
                <div class="sql-header">
                  <span>生成的 SQL</span>
                  <el-button
                    size="small"
                    text
                    @click="copyToClipboard(event.StageOutput.GeneratedSql)"
                  >
                    <el-icon><CopyDocument /></el-icon>
                    复制
                  </el-button>
                </div>
                <pre class="sql-content" v-html="highlightSql(event.StageOutput.GeneratedSql)"></pre>
              </div>
              <div v-if="event.StageOutput?.DataQueryResult" class="query-result">
                <span class="label">查询结果：</span>
                <span class="value">{{ event.StageOutput.DataQueryResult.AffectRows }} 行数据</span>
              </div>
            </div>
          </div>

          <!-- PostProcess 阶段 -->
          <div v-if="event.Stage === 'PostProcess'" class="event-section">
            <div class="event-header">
              <el-icon><Operation /></el-icon>
              <span>数据处理</span>
            </div>
            <div class="event-content">
              <el-text type="info" size="small">已完成数据处理操作</el-text>
            </div>
          </div>

          <!-- Summary 阶段 - 文本 delta -->
          <div v-if="event.Type === 'text-delta'" class="event-section summary-section">
            <div class="event-header">
              <el-icon><ChatDotRound /></el-icon>
              <span>总结回答</span>
            </div>
            <div class="event-content">
              <div class="summary-content" v-html="renderMarkdown(event.Message?.Content || '')"></div>
            </div>
          </div>
        </template>
      </div>

      <div class="message-time">
        {{ formatTime(message.timestamp) }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  User, Loading, CircleClose, View, DataAnalysis, Operation,
  ChatDotRound, CopyDocument, WarningFilled, CircleCheck
} from '@element-plus/icons-vue'
import type { ChatMessage, EventItem } from '@/types'

interface Props {
  message: ChatMessage
}

const props = defineProps<Props>()

// 按阶段分组事件
const groupedEvents = computed(() => {
  if (!props.message.events) return []

  // 返回所有有 Stage 或 Type 的事件
  return props.message.events.filter(e =>
    e.Stage || e.Type
  )
})

// 格式化时间
function formatTime(timestamp: Date | string): string {
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) {
    return '刚刚'
  } else if (diff < 3600000) {
    return `${Math.floor(diff / 60000)} 分钟前`
  } else if (diff < 86400000) {
    return `${Math.floor(diff / 3600000)} 小时前`
  } else {
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  }
}

// 复制到剪贴板
async function copyToClipboard(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

// SQL 语法高亮
function highlightSql(sql: string): string {
  const keywords = [
    'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'BETWEEN',
    'ORDER BY', 'GROUP BY', 'HAVING', 'LIMIT', 'OFFSET',
    'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'OUTER JOIN',
    'AS', 'ON', 'ASC', 'DESC', 'DISTINCT',
    'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
    'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER', 'TABLE'
  ]

  let highlighted = sql

  // 高亮关键词
  keywords.forEach(keyword => {
    const regex = new RegExp(`\\b${keyword}\\b`, 'gi')
    highlighted = highlighted.replace(regex, `<span class="keyword">${keyword}</span>`)
  })

  // 高亮字符串
  highlighted = highlighted.replace(/'([^']*)'/g, `<span class="string">'$1'</span>`)

  // 高亮数字
  highlighted = highlighted.replace(/\b(\d+)\b/g, `<span class="number">$1</span>`)

  // 高亮注释
  highlighted = highlighted.replace(/--.*$/gm, `<span class="comment">$&</span>`)

  return highlighted
}

// 简单的 Markdown 渲染
function renderMarkdown(text: string): string {
  if (!text) return ''

  let html = text

  // 转义 HTML
  html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  // 代码块
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="code-block">$2</code></pre>')

  // 行内代码
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')

  // 粗体
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')

  // 斜体
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')

  // 换行
  html = html.replace(/\n/g, '<br>')

  return html
}
</script>

<style scoped lang="scss">
.message-item {
  margin-bottom: 24px;
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

// ============== 用户消息 ==============
.user-message {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  max-width: 70%;
  margin-left: auto;
}

.user-message .message-content {
  background: #409eff;
  color: #ffffff;
  padding: 12px 16px;
  border-radius: 12px;
  border-bottom-right-radius: 4px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.user-message .message-time {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}

// ============== 助手消息 ==============
.assistant-message {
  display: flex;
  flex-direction: column;
  max-width: 85%;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.avatar {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
}

.role {
  font-weight: 500;
  color: #303133;
}

.processing-state,
.error-state {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  color: #606266;
}

.processing-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  margin-bottom: 12px;
  background: #f0f9ff;
  border-radius: 6px;
  color: #409eff;
  font-size: 13px;
}

.error-state {
  background: #fef0f0;
  color: #f56c6c;
}

// ============== 事件容器 ==============
.events-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.event-section {
  background: #ffffff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}

.event-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  font-weight: 500;
  color: #303133;
}

.event-content {
  padding: 16px;
}

// 信息项
.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;

  &:last-child {
    margin-bottom: 0;
  }

  .label {
    color: #909399;
    font-size: 13px;
  }

  .value {
    color: #303133;
    font-size: 13px;
  }
}

// SQL 代码块
.sql-block {
  background: #1e1e1e;
  border-radius: 6px;
  overflow: hidden;
  margin-top: 8px;
}

.sql-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #2d2d2d;
  color: #9cdcfe;
  font-size: 12px;
}

.sql-content {
  padding: 12px;
  margin: 0;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #d4d4d4;
  overflow-x: auto;

  :deep(.keyword) {
    color: #569cd6;
    font-weight: bold;
  }

  :deep(.string) {
    color: #ce9178;
  }

  :deep(.number) {
    color: #b5cea8;
  }

  :deep(.comment) {
    color: #6a9955;
  }

  :deep(.function) {
    color: #dcdcaa;
  }
}

.query-result {
  margin-top: 8px;

  .label {
    color: #909399;
    font-size: 13px;
  }

  .value {
    color: #67c23a;
    font-weight: 500;
    font-size: 13px;
  }
}

// 总结区域
.summary-section {
  .event-content {
    padding: 16px 20px;
  }
}

.summary-content {
  font-size: 14px;
  line-height: 1.8;
  color: #303133;

  :deep(.code-block) {
    background: #f6f8fa;
    border-radius: 6px;
    padding: 12px;
    margin: 8px 0;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
    overflow-x: auto;
  }

  :deep(.inline-code) {
    background: #f6f8fa;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
    color: #e83e8c;
  }

  :deep(strong) {
    font-weight: 600;
  }

  :deep(em) {
    font-style: italic;
  }
}

.message-time {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}
</style>
