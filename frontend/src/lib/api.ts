import type {
  AgentRun,
  AgentRunCreatePayload,
  AgentRunCreateResult,
  ApiEnvelope,
  Asset,
  ChatRequest,
  ChatResponse,
  Conversation,
  ConversationCreatePayload,
  Message,
  MessageCreatePayload,
  ModelConfig,
  NormalizedModel,
  PersistedRunEvent,
  ToolCall,
} from '../types'

const DEFAULT_API_BASE = '/api'

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE).replace(/\/$/, '')

export class ApiError extends Error {
  code: number
  data?: unknown
  status?: number

  constructor(message: string, code = 500, data?: unknown, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.data = data
    this.status = status
  }
}

function toUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

async function parseEnvelope<T>(response: Response): Promise<ApiEnvelope<T> | null> {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text) as ApiEnvelope<T>
  } catch {
    throw new ApiError('接口没有返回合法 JSON', response.status, text, response.status)
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(toUrl(path), {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  })

  const body = await parseEnvelope<T>(response)

  if (!response.ok) {
    throw new ApiError(body?.message || `HTTP ${response.status}`, body?.code ?? response.status, body?.data, response.status)
  }

  if (!body) {
    throw new ApiError('接口返回为空', response.status, undefined, response.status)
  }

  if (typeof body.code === 'number' && body.code !== 0) {
    throw new ApiError(body.message || '业务请求失败', body.code, body.data, response.status)
  }

  return body.data
}

async function requestOptional<T>(path: string, options: RequestInit = {}, fallback: T): Promise<T> {
  try {
    return await request<T>(path, options)
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 405 || error.code === 404 || error.code === 40404)) {
      return fallback
    }
    throw error
  }
}

export function normalizeModel(item: ModelConfig): NormalizedModel {
  const displayName = item.display_name || item.name || item.model_id || item.id
  const modelId = item.model_id || item.name || item.id
  return {
    id: item.id,
    displayName,
    modelId,
    provider: item.provider || inferProvider(displayName, modelId),
    apiShape: item.api_shape || 'chat_completions',
    supportStreaming: item.support_streaming ?? true,
    supportTools: item.support_tools ?? false,
    supportImage: item.support_image ?? false,
    enabled: item.enabled ?? true,
  }
}

function inferProvider(displayName: string, modelId: string): string {
  const value = `${displayName} ${modelId}`.toLowerCase()
  if (value.includes('glm')) return 'glm'
  if (value.includes('qwen')) return 'qwen'
  if (value.includes('deepseek')) return 'deepseek'
  if (value.includes('minimax')) return 'minimax'
  if (value.includes('flux')) return 'flux'
  return 'custom'
}

export function getApiOrigin(): string {
  if (API_BASE_URL.startsWith('http://') || API_BASE_URL.startsWith('https://')) {
    return new URL(API_BASE_URL).origin
  }
  return window.location.origin
}

export function buildStreamUrl(streamUrl: string): string {
  if (streamUrl.startsWith('http://') || streamUrl.startsWith('https://')) return streamUrl
  if (streamUrl.startsWith('/api/')) return `${getApiOrigin()}${streamUrl}`
  if (streamUrl.startsWith('/')) return `${API_BASE_URL}${streamUrl}`
  return `${API_BASE_URL}/${streamUrl}`
}

export const api = {
  health(): Promise<unknown> {
    return requestOptional<unknown>('/health', {}, { ok: true })
  },

  listConversations(): Promise<Conversation[]> {
    return request<Conversation[]>('/conversations')
  },

  getConversation(conversationId: string): Promise<Conversation> {
    return request<Conversation>(`/conversations/${conversationId}`)
  },

  createConversation(payload: ConversationCreatePayload): Promise<Conversation> {
    return request<Conversation>('/conversations', {
      method: 'POST',
      body: JSON.stringify({
        title: payload.title || '新会话',
        agent_mode: payload.agent_mode || 'general',
        default_model: payload.default_model ?? null,
      }),
    })
  },

  deleteConversation(conversationId: string): Promise<boolean> {
    return request<boolean>(`/conversations/${conversationId}`, { method: 'DELETE' })
  },

  listMessages(conversationId: string): Promise<Message[]> {
    return request<Message[]>(`/conversations/${conversationId}/messages`)
  },

  createMessage(conversationId: string, payload: MessageCreatePayload): Promise<Message> {
    return request<Message>(`/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  listModels(enabledOnly = true): Promise<ModelConfig[]> {
    return request<ModelConfig[]>(`/models?enabled_only=${enabledOnly ? 'true' : 'false'}`)
  },

  createAgentRun(payload: AgentRunCreatePayload): Promise<AgentRunCreateResult> {
    return request<AgentRunCreateResult>('/agent-runs', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getAgentRun(runId: string): Promise<AgentRun> {
    return request<AgentRun>(`/agent-runs/${runId}`)
  },

  listRunEvents(runId: string): Promise<PersistedRunEvent[]> {
    return requestOptional<PersistedRunEvent[]>(`/agent-runs/${runId}/events`, {}, [])
  },

  listToolCalls(runId: string): Promise<ToolCall[]> {
    return requestOptional<ToolCall[]>(`/agent-runs/${runId}/tool-calls`, {}, [])
  },

  chat(payload: ChatRequest): Promise<ChatResponse> {
    return request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  generateImage(payload: { conversation_id?: string | null; prompt: string; model_config_id?: string | null }): Promise<Asset> {
    return request<Asset>('/images/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  listAssets(conversationId?: string): Promise<Asset[]> {
    const query = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : ''
    return requestOptional<Asset[]>(`/assets${query}`, {}, [])
  },

  compareModels(payload: { conversation_id: string; content: string; model_config_ids: string[] }): Promise<unknown> {
    return request<unknown>('/model-compare', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
}
