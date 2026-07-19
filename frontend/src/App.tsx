import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { api, ApiError, buildStreamUrl, normalizeModel } from './lib/api'
import {
  createRunEvent,
  persistedToRunEvent,
  readNumber,
  readString,
  STREAM_EVENTS,
} from './lib/events'
import type { AgentMode, AgentRunStatus, AuthResult, AuthUser, CompareCandidate, Conversation, JudgeReport, Message, NormalizedModel, RunEvent, ThemeMode, Toast as ToastType, ToolCall } from './types'
import { Sidebar } from './components/Sidebar'
import { TopBar } from './components/TopBar'
import { ChatWindow } from './components/ChatWindow'
import { Composer } from './components/Composer'
import { Inspector } from './components/Inspector'
import { Toast } from './components/Toast'
import { AuthScreen } from './components/AuthScreen'

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
  if (error instanceof ApiError) return error.message
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
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [connected, setConnected] = useState(false)
  const [loading, setLoading] = useState(true)
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [streaming, setStreaming] = useState(false)

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [models, setModels] = useState<NormalizedModel[]>([])
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([])
  const [compareCandidates, setCompareCandidates] = useState<CompareCandidate[]>([])
  const [judgeReport, setJudgeReport] = useState<JudgeReport | null>(null)

  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null)
  const [selectedAgentMode, setSelectedAgentMode] = useState<AgentMode>('general')
  const [selectedCompareModelIds, setSelectedCompareModelIds] = useState<string[]>([])
  const [sidebarQuery, setSidebarQuery] = useState('')
  const [input, setInput] = useState('')

  const [events, setEvents] = useState<RunEvent[]>([])
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [activeRunStatus, setActiveRunStatus] = useState<AgentRunStatus | null>(null)
  const [cancelledAt, setCancelledAt] = useState<string | null>(null)
  const [draftContent, setDraftContent] = useState('')
  const [draftModel, setDraftModel] = useState<string | null>(null)
  const [draftAgent, setDraftAgent] = useState<string | null>('GeneralAgent')
  const [inspectorOpen, setInspectorOpen] = useState(true)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
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

  const syncCompletedMessages = useCallback(async (conversationId: string) => {
    const data = await api.listMessages(conversationId)
    // 同一批更新完成持久化消息替换，避免聊天区进入 loading 或短暂显示重复回答。
    setMessages(data)
    setDraftContent('')
  }, [])

  const loadRunDetails = useCallback(async (runId: string) => {
    try {
      const [run, persistedToolCalls, persistedEvents, persistedCompare] = await Promise.all([
        api.getAgentRun(runId),
        api.listToolCalls(runId),
        api.listRunEvents(runId),
        api.getCompareResults(runId),
      ])

      setToolCalls(persistedToolCalls)
      setActiveRunStatus(run.status)
      setCancelledAt(run.cancelled_at || null)
      if (run.final_output || run.partial_output) {
        setDraftContent(run.final_output || run.partial_output || '')
      } else if (run.status !== 'running' && run.status !== 'pending') {
        setDraftContent('')
      }

      if (persistedEvents.length > 0) {
        setEvents(
          persistedEvents.map(persistedToRunEvent),
        )
      }
      if (persistedCompare) {
        setCompareCandidates(persistedCompare.results)
        setJudgeReport(persistedCompare.judge_report || null)
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
      setSelectedCompareModelIds(
        modelData
          .filter((item) => item.enabled && item.apiShape === 'chat_completions')
          .slice(0, 2)
          .map((item) => item.id),
      )

      const firstConversation = conversationData[0]
      if (firstConversation) {
        setActiveConversationId(firstConversation.id)
        setSelectedAgentMode((firstConversation.agent_mode as AgentMode) || 'general')
        if (firstConversation.default_model) setSelectedModelId(firstConversation.default_model)
        await loadMessages(firstConversation.id)
        const savedRunId = window.localStorage.getItem('oas-active-run-id')
        if (savedRunId) {
          try {
            const savedRun = await api.getAgentRun(savedRunId)
            if (savedRun.conversation_id === firstConversation.id) {
              setActiveRunId(savedRunId)
              setDraftModel(savedRun.model)
              setDraftAgent(savedRun.agent_name)
              await loadRunDetails(savedRunId)
            }
          } catch {
            window.localStorage.removeItem('oas-active-run-id')
          }
        }
      }
    } catch (error) {
      setConnected(false)
      showToast('error', '初始化失败', errorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [loadMessages, loadRunDetails, showToast])

  useEffect(() => {
    let cancelled = false
    const restoreSession = async () => {
      setAuthLoading(true)
      try {
        const user = await api.me()
        if (cancelled) return
        setCurrentUser(user)
        await bootstrap()
      } catch (error) {
        if (cancelled) return
        setCurrentUser(null)
        setConnected(false)
        setLoading(false)
        if (!(error instanceof ApiError && (error.status === 401 || error.code === 40100))) {
          showToast('error', '认证服务连接失败', errorMessage(error))
        }
      } finally {
        if (!cancelled) setAuthLoading(false)
      }
    }
    void restoreSession()
    return () => {
      cancelled = true
      sourceRef.current?.close()
    }
  }, [bootstrap, showToast])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [messages, draftContent, streaming])

  const handleCreateConversation = useCallback(async () => {
    try {
      const conversation = await api.createConversation({
        title: '新会话',
        agent_mode: selectedAgentMode,
        default_model: selectedModelId,
      })
      const data = await refreshConversations()
      setActiveConversationId(conversation.id)
      setMessages([])
      setEvents([])
      setToolCalls([])
      setCompareCandidates([])
      setJudgeReport(null)
      setDraftContent('')
      setActiveRunId(null)
      setActiveRunStatus(null)
      setCancelledAt(null)
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
    setCompareCandidates([])
    setJudgeReport(null)
    setActiveRunId(null)
    setActiveRunStatus(null)
    setCancelledAt(null)
    window.localStorage.removeItem('oas-active-run-id')
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
        setCompareCandidates([])
        setJudgeReport(null)
        setActiveRunStatus(null)
        setCancelledAt(null)
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
      agent_mode: selectedAgentMode,
      default_model: selectedModelId,
    })
    await refreshConversations()
    setActiveConversationId(conversation.id)
    return conversation.id
  }, [activeConversationId, refreshConversations, selectedAgentMode, selectedModelId])

  const fallbackChat = useCallback(async (conversationId: string, content: string) => {
    const result = await api.chat({
      conversation_id: conversationId,
      content,
      primary_model_id: selectedModelId,
      agent_mode: selectedAgentMode,
    })
    setDraftContent(result.final_output)
    setDraftModel(result.model)
    setDraftAgent(result.agent_name)
    setActiveRunId(result.run_id)
    setActiveRunStatus('completed')
    window.localStorage.setItem('oas-active-run-id', result.run_id)
    appendEvent(createRunEvent('run.completed', JSON.stringify({
      run_id: result.run_id,
      final_output: result.final_output,
      mode: 'standard-chat',
    })))
    window.setTimeout(() => {
      void (async () => {
        try {
          await syncCompletedMessages(conversationId)
        } catch {
          // 保留已经显示的完整回答，避免后台同步失败时消息从页面消失。
        }
      })()
      void refreshConversations()
    }, 280)
  }, [appendEvent, refreshConversations, selectedAgentMode, selectedModelId, syncCompletedMessages])

  const handleCompareModelToggle = useCallback((modelId: string) => {
    setSelectedCompareModelIds((current) => {
      if (current.includes(modelId)) return current.filter((item) => item !== modelId)
      if (current.length >= 3) return current
      return [...current, modelId]
    })
  }, [])

  const handleSend = useCallback(async () => {
    const content = input.trim()
    if (!content || streaming) return

    setInput('')
    setDraftContent('')
    setEvents([])
    setToolCalls([])
    setCompareCandidates([])
    setJudgeReport(null)

    if (selectedAgentMode === 'compare' && (selectedCompareModelIds.length < 2 || selectedCompareModelIds.length > 3)) {
      showToast('warning', '请选择 2-3 个模型', 'Compare 模式会并发运行所选模型，然后由 JudgeAgent 评分。')
      setInput(content)
      return
    }

    try {
      const conversationId = await ensureConversation(content)
      setMessages((current) => [...current, localMessage('user', content)])

      let run
      try {
        run = await api.createAgentRun({
          conversation_id: conversationId,
          content,
          primary_model_id: selectedModelId || null,
          agent_mode: selectedAgentMode,
          compare_model_ids: selectedAgentMode === 'compare' ? selectedCompareModelIds : [],
        })
      } catch (error) {
        if (error instanceof ApiError && (error.status === 404 || error.status === 405 || error.code === 404)) {
          showToast('info', '已切换为标准响应模式')
          await fallbackChat(conversationId, content)
          return
        }
        throw error
      }

      setActiveRunId(run.run_id)
      setActiveRunStatus(run.status)
      setCancelledAt(null)
      window.localStorage.setItem('oas-active-run-id', run.run_id)
      setDraftModel(run.model)
      setDraftAgent(run.agent_name)
      setStreaming(true)
      setConnected(true)

      const streamUrl = buildStreamUrl(run.stream_url)
      const source = new EventSource(streamUrl, { withCredentials: true })
      sourceRef.current = source

      STREAM_EVENTS.forEach((eventName) => {
        source.addEventListener(eventName, (messageEvent) => {
          const event = createRunEvent(eventName, messageEvent.data, messageEvent.lastEventId)
          appendEvent(event)

          if (eventName === 'run.started') setActiveRunStatus('running')

          if (eventName === 'run.snapshot') {
            const partialOutput = readString(event.data, 'partial_output')
            const status = readString(event.data, 'status') as AgentRunStatus | undefined
            if (partialOutput !== undefined) setDraftContent(partialOutput)
            if (status) setActiveRunStatus(status)
          }

          if (eventName === 'token.delta') {
            const delta = readString(event.data, 'delta')
            const offsetStart = readNumber(event.data, 'offset_start')
            if (delta) setDraftContent((current) => {
              if (offsetStart === undefined) return current + delta
              if (current.length > offsetStart) return current
              return current + delta
            })
          }

          if (eventName === 'token.chunk') {
            const chunk = readString(event.data, 'chunk')
            const offsetStart = readNumber(event.data, 'offset_start')
            if (chunk && offsetStart !== undefined) {
              setDraftContent((current) => {
                if (current.length >= offsetStart + chunk.length) return current
                if (current.length <= offsetStart) return current + chunk
                return current + chunk.slice(current.length - offsetStart)
              })
            }
          }

          if (eventName === 'agent.updated') {
            const agentName = readString(event.data, 'agent_name')
            if (agentName) setDraftAgent(agentName)
          }

          if (eventName === 'compare.model.started') {
            const candidate = event.data as unknown as CompareCandidate
            setCompareCandidates((current) => {
              if (current.some((item) => item.model_config_id === candidate.model_config_id)) return current
              return [...current, { ...candidate, status: 'running' }]
            })
          }

          if (eventName === 'compare.model.completed' || eventName === 'compare.model.failed') {
            const candidate = event.data as unknown as CompareCandidate
            setCompareCandidates((current) => {
              const exists = current.some((item) => item.model_config_id === candidate.model_config_id)
              if (!exists) return [...current, candidate]
              return current.map((item) => item.model_config_id === candidate.model_config_id ? candidate : item)
            })
          }

          if (eventName === 'judge.completed') {
            setJudgeReport(event.data as unknown as JudgeReport)
            setDraftAgent('ModelJudgeAgent')
          }

          if (eventName === 'run.completed') {
            const finalOutput = readString(event.data, 'final_output')
            source.close()
            sourceRef.current = null
            setStreaming(false)
            setActiveRunStatus('completed')
            if (finalOutput) setDraftContent(finalOutput)
            void loadRunDetails(run.run_id)
            window.setTimeout(() => {
              void (async () => {
                try {
                  await syncCompletedMessages(conversationId)
                } catch {
                  // 保留已经显示的完整回答，避免后台同步失败时消息从页面消失。
                }
              })()
              void refreshConversations()
            }, 320)
          }

          if (eventName === 'run.cancel.requested') {
            showToast('info', '正在停止 Agent', '服务端已收到取消请求。')
          }

          if (eventName === 'run.cancelled' || eventName === 'run.timeout' || eventName === 'run.interrupted' || eventName === 'run.failed') {
            source.close()
            sourceRef.current = null
            setStreaming(false)
            const status = eventName.replace('run.', '') as AgentRunStatus
            setActiveRunStatus(status)
            const partialOutput = readString(event.data, 'partial_output')
            if (partialOutput !== undefined) setDraftContent(partialOutput)
            const eventCancelledAt = readString(event.data, 'cancelled_at')
            if (eventCancelledAt) setCancelledAt(eventCancelledAt)
            const message = readString(event.data, 'message')
            if (eventName === 'run.timeout') showToast('warning', 'Agent 运行超时', message)
            if (eventName === 'run.interrupted') showToast('warning', 'Agent 运行已中断', message)
            if (eventName === 'run.failed') showToast('error', 'Agent 执行失败', message)
            void loadRunDetails(run.run_id)
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
        void api.getAgentRun(run.run_id).then((state) => {
          setActiveRunStatus(state.status)
          if (state.status !== 'pending' && state.status !== 'running') {
            source.close()
            sourceRef.current = null
            setStreaming(false)
            setDraftContent(state.final_output || state.partial_output || '')
            setCancelledAt(state.cancelled_at || null)
          }
        }).catch(() => {
          source.close()
          sourceRef.current = null
          setStreaming(false)
        })
      }
    } catch (error) {
      setStreaming(false)
      setDraftContent('')
      showToast('error', '发送失败', errorMessage(error))
    }
  }, [appendEvent, ensureConversation, fallbackChat, input, loadRunDetails, selectedAgentMode, selectedCompareModelIds, refreshConversations, selectedModelId, showToast, streaming, syncCompletedMessages])

  const handleStop = useCallback(async () => {
    if (!activeRunId) return
    try {
      const result = await api.cancelAgentRun(activeRunId)
      setActiveRunStatus(result.status)
      setCancelledAt(result.cancelled_at || null)
      appendEvent(createRunEvent('run.cancel.requested', JSON.stringify(result)))
    } catch (error) {
      showToast('error', '停止失败', errorMessage(error))
      return
    }
    sourceRef.current?.close()
    sourceRef.current = null
    setStreaming(false)
    void loadRunDetails(activeRunId)
  }, [activeRunId, appendEvent, loadRunDetails, showToast])

  const handleExampleClick = useCallback((text: string) => setInput(text), [])

  const handleAuthenticated = useCallback(async (result: AuthResult) => {
    setCurrentUser(result.user)
    setConnected(false)
    await bootstrap()
    showToast('success', `欢迎，${result.user.username}`)
  }, [bootstrap, showToast])

  const handleLogout = useCallback(async () => {
    sourceRef.current?.close()
    sourceRef.current = null
    try {
      await api.logout()
    } catch {
      // 即使服务端会话已过期，也要立即清理当前界面状态。
    }
    setCurrentUser(null)
    setConnected(false)
    setStreaming(false)
    setConversations([])
    setMessages([])
    setEvents([])
    setToolCalls([])
    setCompareCandidates([])
    setJudgeReport(null)
    setActiveConversationId(null)
    setActiveRunId(null)
    setActiveRunStatus(null)
    setCancelledAt(null)
    window.localStorage.removeItem('oas-active-run-id')
    setDraftContent('')
  }, [])

  if (authLoading) {
    return <div className="auth-loading"><Loader2 className="spin" size={26} /><span>正在验证登录状态…</span></div>
  }

  if (!currentUser) {
    return <AuthScreen onAuthenticated={handleAuthenticated} />
  }

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
        mobileOpen={mobileSidebarOpen}
        onClose={() => setMobileSidebarOpen(false)}
      />

      <main className="workspace">
        <TopBar
          conversation={activeConversation}
          models={models}
          selectedModelId={selectedModelId}
          selectedAgentMode={selectedAgentMode}
          selectedCompareModelIds={selectedCompareModelIds}
          inspectorOpen={inspectorOpen}
          streaming={streaming}
          theme={theme}
          user={currentUser}
          onModelChange={setSelectedModelId}
          onAgentModeChange={setSelectedAgentMode}
          onCompareModelToggle={handleCompareModelToggle}
          onToggleInspector={() => setInspectorOpen((value) => !value)}
          onToggleTheme={() => setTheme((value) => value === 'dark' ? 'light' : 'dark')}
          onLogout={() => void handleLogout()}
          onOpenSidebar={() => setMobileSidebarOpen(true)}
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
              compareCandidates={compareCandidates}
              judgeReport={judgeReport}
              compareRunning={streaming && compareCandidates.some((item) => item.status === 'running')}
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
          onStop={() => void handleStop()}
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
          runStatus={activeRunStatus}
          cancelledAt={cancelledAt}
          persistedToolCalls={toolCalls}
          onClear={() => setEvents([])}
        />
      ) : null}

      <Toast toast={toast} />
    </div>
  )
}
