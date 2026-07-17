export type ApiEnvelope<T> = {
  code: number
  message: string
  data: T
}

export type ThemeMode = 'dark' | 'light'

export type AuthUser = {
  id: string
  username: string
  created_at: string
}

export type AuthResult = {
  user: AuthUser
  expires_at: string
}

export type CaptchaChallenge = {
  captcha_id: string
  image_data_uri: string
  expires_in: number
}

export type AgentMode = 'auto' | 'general' | 'tech' | 'ecommerce' | 'image' | 'compare'

export type Conversation = {
  id: string
  title: string
  agent_mode: string
  default_model?: string | null
  created_at: string
  updated_at: string
}

export type ConversationCreatePayload = {
  title?: string
  agent_mode?: string
  default_model?: string | null
}

export type MessageRole = 'user' | 'assistant' | 'tool' | 'system'

export type Message = {
  id: string
  conversation_id: string
  role: MessageRole
  content: string
  model?: string | null
  agent_name?: string | null
  sequence_no?: number
  created_at: string
}

export type MessageCreatePayload = {
  role: MessageRole
  content: string
  model?: string | null
  agent_name?: string | null
}

export type ModelConfig = {
  id: string
  name?: string
  provider?: string
  display_name?: string
  model_id?: string
  api_shape?: string
  support_streaming?: boolean
  support_tools?: boolean
  support_image?: boolean
  enabled?: boolean
  created_at?: string
  updated_at?: string
}

export type NormalizedModel = {
  id: string
  displayName: string
  modelId: string
  provider: string
  apiShape: string
  supportStreaming: boolean
  supportTools: boolean
  supportImage: boolean
  enabled: boolean
}

export type AgentRunCreatePayload = {
  conversation_id: string
  content: string
  primary_model_id?: string | null
  agent_mode?: AgentMode | null
  compare_model_ids?: string[]
}

export type AgentRunCreateResult = {
  run_id: string
  conversation_id: string
  user_message_id: string
  model_config_id: string
  model: string
  agent_name: string
  stream_url: string
}

export type AgentRun = {
  id: string
  conversation_id: string
  user_message_id?: string | null
  model_config_id?: string | null
  agent_name: string
  model: string
  status: 'running' | 'completed' | 'failed' | string
  input_text: string
  final_output?: string | null
  error_message?: string | null
  duration_ms?: number | null
  started_at: string
  finished_at?: string | null
  created_at: string
}

export type RunEvent = {
  id: string
  event: string
  data: Record<string, unknown>
  createdAt: number
}

export type PersistedRunEvent = {
  id: string
  run_id: string
  seq?: number
  event_type?: string
  event_name?: string
  payload_json?: string | Record<string, unknown>
  created_at: string
}

export type ToolCall = {
  id: string
  run_id: string
  tool_name: string
  arguments_json?: string | Record<string, unknown> | null
  output?: string | null
  status?: string | null
  duration_ms?: number | null
  created_at?: string | null
}

export type ChatRequest = {
  conversation_id: string
  content: string
  primary_model_id?: string | null
  agent_mode?: AgentMode | null
}

export type ChatResponse = {
  run_id: string
  conversation_id: string
  user_message_id: string
  assistant_message_id: string
  model_config_id: string
  model: string
  agent_name: string
  final_output: string
}

export type Toast = {
  id: string
  type: 'success' | 'error' | 'info' | 'warning'
  title: string
  description?: string
}

export type Asset = {
  id: string
  conversation_id?: string | null
  run_id?: string | null
  asset_type: string
  prompt?: string | null
  model?: string | null
  file_path?: string | null
  url?: string | null
  created_at?: string | null
}

export type CompareCandidate = {
  model_config_id: string
  display_name: string
  model_id: string
  status: 'running' | 'completed' | 'failed' | string
  output_text?: string | null
  error_message?: string | null
  duration_ms?: number | null
}

export type JudgeScore = {
  model_config_id: string
  display_name: string
  accuracy: number
  structure: number
  actionability: number
  expression: number
  recommendation: number
  total: number
  strengths: string[]
  weaknesses: string[]
}

export type JudgeReport = {
  winner_model_config_id: string
  winner_display_name: string
  scores: JudgeScore[]
  summary: string
  fallback_used?: boolean
}

export type ModelCompare = {
  id: string
  run_id: string
  model_config_ids: string[]
  status: string
  winner_model_config_id?: string | null
  judge_report?: JudgeReport | null
  results: CompareCandidate[]
  created_at: string
}
