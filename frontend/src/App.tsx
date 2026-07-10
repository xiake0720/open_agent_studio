import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { api, ApiError, buildStreamUrl, normalizeModel } from './lib/api'
import {
  createRunEvent,
  persistedToRunEvent,
  readString,
  STREAM_EVENTS,
} from './lib/events'
import type { AgentMode, Conversation, Message, NormalizedModel, RunEvent, ThemeMode, Toast as ToastType, ToolCall } from './types'
import { Sidebar } from './components/Sidebar'
import { TopBar } from './components/TopBar'
import { ChatWindow } from './components/ChatWindow'
import { Composer } from './components/Composer'
import { Inspector } from './components/Inspector'
import { Toast } from './components/Toast'

function localMessage(role: 'user' | 'assistant', content: string, model?: string | null, agentName?: string | null): Message {
  return {
    id: `local-${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    conversation_id: 'local',
    role,
    content,
    model,
    agent_name: agentName,
    created_at: new Date().toISOString(),
  }
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return `${error.message}${error.code ? `（code=${error.code}）` : ''}`
  if (error instanceof Error) return error.message
  return '未知错误'
}

function readTheme(): ThemeMode {
  const saved = window.localStorage.getItem('oas-theme')
  if (saved === 'light' || saved === 'dark') return saved
  return 'dark'
}

export default function App() {
  const [theme, setTheme] = useState<ThemeMode>(() => readTheme())
  const [connected, setConnected] = useState(false)
  const [loading, setLoading] = useState(true)
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [streaming, setStreaming] = useState(false)

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [models, setModels] = useState<NormalizedModel[]>([])
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([])

  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null)
  const [selectedAgentMode, setSelectedAgentMode] = useState<AgentMode>('general')
  const [sidebarQuery, setSidebarQuery] = useState('')
  const [input, setInput] = useState('')

  const [events, setEvents] = useState<RunEvent[]>([])
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [draftContent, setDraftContent] = useState('')
  const [draftModel, setDraftModel] = useState<string | null>(null)
  const [draftAgent, setDraftAgent] = useState<string | null>('GeneralAgent')
  const [inspectorOpen, setInspectorOpen] = useState(true)
  const [toast, setToast] = useState<ToastType | null>(null)

  const sourceRef = useRef<EventSource | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem('oas-theme', theme)
  }, [theme])

  const activeConversation = useMemo(
    () => conversations.find((item) => item.id === activeConversationId) || null,
    [activeConversationId, conversations],
  )

  const selectedModel = useMemo(
    () => models.find((item) => item.id === selectedModelId) || null,
    [models, selectedModelId],
  )

  const tokenCount = useMemo(() => events.filter((item) => item.event === 'token.delta').length, [events])

  const showToast = useCallback((type: ToastType['type'], title: string, description?: string) => {
    const next = { id: `${Date.now()}`, type, title, description }
    setToast(next)
    window.setTimeout(() => setToast((current) => current?.id === next.id ? null : current), 4600)
  }, [])

  const appendEvent = useCallback((event: RunEvent) => {
    setEvents((current) => [...current, event])
  }, [])

  const refreshConversations = useCallback(async () => {
    const data = await api.listConversations()
    setConversations(data)
    return data
  }, [])

  const loadMessages = useCallback(async (conversationId: string) => {
    setMessagesLoading(true)
    try {
      const data = await api.listMessages(conversationId)
      setMessages(data)
    } finally {
      setMessagesLoading(false)
    }
  }, [])

  const loadRunDetails = useCallback(async (runId: string) => {
    try {
      const [
        persistedToolCalls,
        persistedEvents,
      ] = await Promise.all([
        api.listToolCalls(runId),
        api.listRunEvents(runId),
      ])

      setToolCalls(persistedToolCalls)

      if (persistedEvents.length > 0) {
        setEvents(
          persistedEvents.map(persistedToRunEvent),
        )
      }
    } catch {
      setToolCalls([])
    }
  }, [])

  const bootstrap = useCallback(async () => {
    setLoading(true)
    try {
      await api.health()
      setConnected(true)
      const [conversationData, rawModels] = await Promise.all([
        api.listConversations(),
        api.listModels(),
      ])
      const modelData = rawModels.map(normalizeModel)
      setConversations(conversationData)
      setModels(modelData)
      setSelectedModelId(modelData.find((item) => item.enabled && item.supportStreaming)?.id || modelData[0]?.id || null)

      const firstConversation = conversationData[0]
      if (firstConversation) {
        setActiveConversationId(firstConversation.id)
        setSelectedAgentMode((firstConversation.agent_mode as AgentMode) || 'general')
        if (firstConversation.default_model) setSelectedModelId(firstConversation.default_model)
        await loadMessages(firstConversation.id)
      }
    } catch (error) {
      setConnected(false)
      showToast('error', '初始化失败', errorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [loadMessages, showToast])

  useEffect(() => {
    void bootstrap()
    return () => sourceRef.current?.close()
  }, [bootstrap])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [messages, draftContent, streaming])

  const handleCreateConversation = useCallback(async () => {
    try {
      const conversation = await api.createConversation({
        title: '新会话',
        agent_mode: selectedAgentMode === 'auto' ? 'general' : selectedAgentMode,
        default_model: selectedModelId,
      })
      const data = await refreshConversations()
      setActiveConversationId(conversation.id)
      setMessages([])
      setEvents([])
      setToolCalls([])
      setDraftContent('')
      setActiveRunId(null)
      const created = data.find((item) => item.id === conversation.id)
      if (created?.agent_mode) setSelectedAgentMode(created.agent_mode as AgentMode)
      showToast('success', '已创建新会话')
    } catch (error) {
      showToast('error', '创建会话失败', errorMessage(error))
    }
  }, [refreshConversations, selectedAgentMode, selectedModelId, showToast])

  const handleSelectConversation = useCallback(async (id: string) => {
    sourceRef.current?.close()
    sourceRef.current = null
    setStreaming(false)
    setActiveConversationId(id)
    setDraftContent('')
    setEvents([])
    setToolCalls([])
    setActiveRunId(null)
    const conversation = conversations.find((item) => item.id === id)
    if (conversation?.agent_mode) setSelectedAgentMode(conversation.agent_mode as AgentMode)
    if (conversation?.default_model) setSelectedModelId(conversation.default_model)
    try {
      await loadMessages(id)
    } catch (error) {
      showToast('error', '加载消息失败', errorMessage(error))
    }
  }, [conversations, loadMessages, showToast])

  const handleDeleteConversation = useCallback(async (id: string) => {
    if (!window.confirm('确认删除这个会话吗？删除后会同时移除消息历史。')) return
    try {
      await api.deleteConversation(id)
      const data = await refreshConversations()
      if (activeConversationId === id) {
        const next = data[0]
        setActiveConversationId(next?.id || null)
        setMessages([])
        setEvents([])
        setToolCalls([])
        if (next) await loadMessages(next.id)
      }
      showToast('success', '会话已删除')
    } catch (error) {
      showToast('error', '删除失败', errorMessage(error))
    }
  }, [activeConversationId, loadMessages, refreshConversations, showToast])

  const ensureConversation = useCallback(async (content: string): Promise<string> => {
    if (activeConversationId) return activeConversationId
    const conversation = await api.createConversation({
      title: content.slice(0, 32) || '新会话',
      agent_mode: selectedAgentMode === 'auto' ? 'general' : selectedAgentMode,
      default_model: selectedModelId,
    })
    await refreshConversations()
    setActiveConversationId(conversation.id)
    return conversation.id
  }, [activeConversationId, refreshConversations, selectedAgentMode, selectedModelId])

  const fallbackChat = useCallback(async (conversationId: string, content: string) => {
    const result = await api.chat({ conversation_id: conversationId, content, model_config_id: selectedModelId })
    setDraftContent(result.final_output)
    setDraftModel(result.model)
    setDraftAgent(result.agent_name)
    setActiveRunId(result.run_id)
    appendEvent(createRunEvent('run.completed', JSON.stringify({
      run_id: result.run_id,
      final_output: result.final_output,
      mode: 'legacy-chat',
    })))
    window.setTimeout(() => {
      setDraftContent('')
      void loadMessages(conversationId)
      void refreshConversations()
    }, 280)
  }, [appendEvent, loadMessages, refreshConversations, selectedModelId])

  const handleSend = useCallback(async () => {
    const content = input.trim()
    if (!content || streaming) return

    setInput('')
    setDraftContent('')
    setEvents([])
    setToolCalls([])

    try {
      const conversationId = await ensureConversation(content)
      setMessages((current) => [...current, localMessage('user', content)])

      let run
      try {
        run = await api.createAgentRun({
          conversation_id: conversationId,
          content,
          model_config_id: selectedModelId || null,
        })
      } catch (error) {
        if (error instanceof ApiError && (error.status === 404 || error.status === 405 || error.code === 404)) {
          showToast('warning', '流式接口未就绪，已回退到 /chat', '后端补齐 /api/agent-runs 后会自动使用 SSE。')
          await fallbackChat(conversationId, content)
          return
        }
        throw error
      }

      setActiveRunId(run.run_id)
      setDraftModel(run.model)
      setDraftAgent(run.agent_name)
      setStreaming(true)
      setConnected(true)

      const streamUrl = buildStreamUrl(run.stream_url)
      const source = new EventSource(streamUrl)
      sourceRef.current = source

      STREAM_EVENTS.forEach((eventName) => {
        source.addEventListener(eventName, (messageEvent) => {
          const event = createRunEvent(eventName, messageEvent.data)
          appendEvent(event)

          if (eventName === 'token.delta') {
            const delta = readString(event.data, 'delta')
            if (delta) setDraftContent((current) => current + delta)
          }

          if (eventName === 'agent.updated') {
            const agentName = readString(event.data, 'agent_name')
            if (agentName) setDraftAgent(agentName)
          }

          if (eventName === 'run.completed') {
            const finalOutput = readString(event.data, 'final_output')
            source.close()
            sourceRef.current = null
            setStreaming(false)
            if (finalOutput) setDraftContent(finalOutput)
            void loadRunDetails(run.run_id)
            window.setTimeout(() => {
              setDraftContent('')
              void loadMessages(conversationId)
              void refreshConversations()
            }, 320)
          }

          if (eventName === 'run.error') {
            source.close()
            sourceRef.current = null
            setStreaming(false)
            const message = readString(event.data, 'message') || 'Agent 执行失败'
            setDraftContent(`执行失败：${message}`)
            showToast('error', 'Agent 执行失败', message)
            void loadRunDetails(run.run_id)
          }
        })
      })

      source.onmessage = (messageEvent) => appendEvent(createRunEvent('message', messageEvent.data))
      source.onerror = () => {
        appendEvent(createRunEvent('connection.error', JSON.stringify({ message: 'SSE 连接异常或已关闭' })))
        source.close()
        sourceRef.current = null
        setStreaming(false)
      }
    } catch (error) {
      setStreaming(false)
      setDraftContent('')
      showToast('error', '发送失败', errorMessage(error))
    }
  }, [appendEvent, ensureConversation, fallbackChat, input, loadMessages, loadRunDetails, refreshConversations, selectedModelId, showToast, streaming])

  const handleStop = useCallback(() => {
    sourceRef.current?.close()
    sourceRef.current = null
    setStreaming(false)
    appendEvent(createRunEvent('client.stop', JSON.stringify({ message: '用户手动停止流式连接' })))
  }, [appendEvent])

  const handleExampleClick = useCallback((text: string) => setInput(text), [])

  return (
    <div className={`app-shell ${inspectorOpen ? 'app-shell--with-inspector' : ''}`}>
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        query={sidebarQuery}
        connected={connected}
        loading={loading}
        onQueryChange={setSidebarQuery}
        onCreate={handleCreateConversation}
        onSelect={handleSelectConversation}
        onDelete={handleDeleteConversation}
      />

      <main className="workspace">
        <TopBar
          conversation={activeConversation}
          models={models}
          selectedModelId={selectedModelId}
          selectedAgentMode={selectedAgentMode}
          inspectorOpen={inspectorOpen}
          streaming={streaming}
          theme={theme}
          onModelChange={setSelectedModelId}
          onAgentModeChange={setSelectedAgentMode}
          onToggleInspector={() => setInspectorOpen((value) => !value)}
          onToggleTheme={() => setTheme((value) => value === 'dark' ? 'light' : 'dark')}
        />

        <div className="chat-area" ref={scrollRef}>
          {loading || messagesLoading ? (
            <div className="loading-panel"><Loader2 className="spin" size={20} /> 正在加载工作台...</div>
          ) : (
            <ChatWindow
              messages={messages}
              draftContent={draftContent}
              draftModel={draftModel || selectedModel?.modelId}
              draftAgent={draftAgent}
              streaming={streaming}
              onExampleClick={handleExampleClick}
            />
          )}
        </div>

        <Composer
          value={input}
          disabled={loading || !connected}
          streaming={streaming}
          onChange={setInput}
          onSend={handleSend}
          onStop={handleStop}
        />
      </main>

      {inspectorOpen ? (
        <Inspector
          events={events}
          activeRunId={activeRunId}
          streaming={streaming}
          tokenCount={tokenCount}
          model={draftModel || selectedModel?.modelId}
          agentName={draftAgent}
          persistedToolCalls={toolCalls}
          onClear={() => setEvents([])}
        />
      ) : null}

      <Toast toast={toast} />
    </div>
  )
}
