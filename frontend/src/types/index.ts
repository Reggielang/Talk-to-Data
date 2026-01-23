// ============== API 请求/响应类型 ==============

export interface ChatRequest {
  query: string
  session_id?: string
  user_email?: string
  model_name?: string
  stream?: boolean
}

export interface EventMeta {
  RequestId: string
}

export interface DataQueryResult {
  AffectRows: number
  JsonContent: string
  JsonContentRows: number
}

export interface StageOutput {
  // Block output
  Blocked?: boolean
  BlockReason?: string

  // Understand output
  RephrasedUserQuery?: string
  intent?: string
  entities?: string[]
  rephrase?: string
  tool?: string
  tool_arguments?: string

  // Supervisor output
  SupervisorToolCalls?: SupervisorToolCall[]

  // DataQuery output
  GeneratedSql?: string
  DataQueryResult?: DataQueryResult

  // PostProcess output
  PostProcessResult?: any
}

export interface SupervisorToolCall {
  Name: string
  Arguments: string
}

export interface EventMessage {
  Id: string
  Content: string
  Role: string
  Type: string
  FirstTokenAt: string
}

export interface EventItem {
  Stage: string
  Type: string
  SessionId: string
  SessionMessageId: string
  StageOutput?: StageOutput
  Message?: EventMessage
}

export interface EventData {
  SessionId: string
  SessionMessageId: string
  Events: EventItem[]
}

export interface ChatResponse {
  Meta: EventMeta
  Data: EventData
}

// ============== 会话相关类型 ==============

export interface SessionCreateRequest {
  user_sid: string
  user_email: string
  note?: string
}

export interface SessionResponse {
  session_id: string
  user_sid: string
  user_email: string
  note?: string
  created_at: string
  updated_at: string
  expired_at: string
}

export interface MessageResponse {
  id: string
  session_id: string
  role: string
  content: string
  created_at: string
  updated_at: string
}

export interface EventResponse {
  id: string
  session_id: string
  session_message_id: string
  node_name: string
  event_type: string
  event_body: Record<string, any>
  created_at: string
  has_error: boolean
  duration_ms: number
}

// ============== 前端状态类型 ==============

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  status: 'pending' | 'processing' | 'completed' | 'error'
  events?: EventItem[]
  error?: string
}

export interface Session {
  session_id: string
  user_sid: string
  user_email: string
  note?: string
  created_at: string
  updated_at: string
  expired_at: string
  messages?: ChatMessage[]
}

export interface SSEEvent {
  event: string
  data: any
}

// ============== 流式响应事件类型 ==============

export interface StreamStartEvent {
  type: 'start'
  request_id: string
  session_id: string
  message_id: string
}

export interface StreamProgressEvent {
  node: string
  type: string
}

export interface StreamCompleteEvent {
  Meta: EventMeta
  Data: EventData
}

export interface StreamErrorEvent {
  error: string
}
