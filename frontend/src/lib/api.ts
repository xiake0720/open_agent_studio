import type {
  AgentRun,
  AgentRunCreatePayload,
  AgentRunCreateResult,
  AgentRunCancelResult,
  ApiEnvelope,
  Asset,
  AuthResult,
  AuthUser,
  CaptchaChallenge,
  ChatRequest,
  ChatResponse,
  Conversation,
  ConversationCreatePayload,
  Message,
  MessageCreatePayload,
  ModelCompare,
  ModelConfig,
  NormalizedModel,
  PersistedRunEvent,
  ToolCall,
  AdminConversation,
  AdminConversationDetail,
  AdminException,
  AdminManagedUser,
  AdminModel,
  AdminModelPayload,
  AdminOverview,
  AdminTokenStats,
  AdminUser,
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
    credentials: 'include',
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
    if (error instanceof ApiError && (
      error.status === 404 ||
      error.status === 405 ||
      error.code === 404 ||
      (error.code >= 40400 && error.code < 40500)
    )) {
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
  me(): Promise<AuthUser> {
    return request<AuthUser>('/auth/me')
  },

  register(payload: { username: string; password: string; password_confirm: string }): Promise<AuthResult> {
    return request<AuthResult>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  login(payload: { username: string; password: string; captcha_id?: string; captcha_code?: string }): Promise<AuthResult> {
    return request<AuthResult>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  logout(): Promise<boolean> {
    return request<boolean>('/auth/logout', { method: 'POST' })
  },

  getCaptcha(): Promise<CaptchaChallenge> {
    return request<CaptchaChallenge>('/auth/captcha')
  },

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

  cancelAgentRun(runId: string): Promise<AgentRunCancelResult> {
    return request<AgentRunCancelResult>(`/agent-runs/${runId}/cancel`, { method: 'POST' })
  },

  listRunEvents(runId: string): Promise<PersistedRunEvent[]> {
    return requestOptional<PersistedRunEvent[]>(`/agent-runs/${runId}/events`, {}, [])
  },

  listToolCalls(runId: string): Promise<ToolCall[]> {
    return requestOptional<ToolCall[]>(`/agent-runs/${runId}/tool-calls`, {}, [])
  },

  getCompareResults(runId: string): Promise<ModelCompare | null> {
    return requestOptional<ModelCompare | null>(`/agent-runs/${runId}/compare-results`, {}, null)
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

}

export const adminApi = {
  login(payload: { username: string; password: string }): Promise<{ user: AdminUser; expires_at: string }> {
    return request('/admin/auth/login', { method: 'POST', body: JSON.stringify(payload) })
  },
  me(): Promise<AdminUser> {
    return request('/admin/auth/me')
  },
  logout(): Promise<boolean> {
    return request('/admin/auth/logout', { method: 'POST' })
  },
  overview(): Promise<AdminOverview> {
    return request('/admin/overview')
  },
  users(query = ''): Promise<AdminManagedUser[]> {
    return request(`/admin/users?query=${encodeURIComponent(query)}`)
  },
  updateUser(userId: string, isActive: boolean): Promise<{ id: string; is_active: boolean }> {
    return request(`/admin/users/${userId}`, { method: 'PATCH', body: JSON.stringify({ is_active: isActive }) })
  },
  tokenStats(dateFrom?: string, dateTo?: string): Promise<AdminTokenStats> {
    const params = new URLSearchParams()
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    return request(`/admin/token-stats${params.size ? `?${params}` : ''}`)
  },
  models(): Promise<AdminModel[]> {
    return request('/admin/models')
  },
  createModel(payload: AdminModelPayload): Promise<AdminModel> {
    return request('/admin/models', { method: 'POST', body: JSON.stringify(payload) })
  },
  updateModel(modelId: string, payload: AdminModelPayload): Promise<AdminModel> {
    return request(`/admin/models/${modelId}`, { method: 'PUT', body: JSON.stringify(payload) })
  },
  conversations(query = ''): Promise<AdminConversation[]> {
    return request(`/admin/conversations?query=${encodeURIComponent(query)}`)
  },
  conversation(conversationId: string): Promise<AdminConversationDetail> {
    return request(`/admin/conversations/${conversationId}`)
  },
  exceptions(resolved?: boolean): Promise<AdminException[]> {
    return request(`/admin/exceptions${resolved === undefined ? '' : `?resolved=${resolved}`}`)
  },
  updateException(exceptionId: string, resolved: boolean): Promise<{ id: string; resolved: boolean }> {
    return request(`/admin/exceptions/${exceptionId}`, { method: 'PATCH', body: JSON.stringify({ resolved }) })
  },
}
