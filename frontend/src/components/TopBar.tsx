import { Activity, ChevronDown, Eye, EyeOff, LogOut, Menu, SlidersHorizontal, UserRound, Wrench } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { AgentMode, AuthUser, Conversation, NormalizedModel, ThemeMode } from '../types'
import { displayConversationTitle } from '../utils/format'
import { ThemeToggle } from './ThemeToggle'

const AGENT_OPTIONS: Array<{ value: AgentMode; label: string }> = [
  { value: 'auto', label: '智能路由' },
  { value: 'general', label: '通用助手' },
  { value: 'tech', label: '技术助手' },
  { value: 'ecommerce', label: '电商运营' },
  { value: 'image', label: '视觉策划' },
  { value: 'compare', label: '多模型对比' },
]

type Props = {
  conversation: Conversation | null
  models: NormalizedModel[]
  selectedModelId: string | null
  selectedAgentMode: AgentMode
  selectedCompareModelIds: string[]
  inspectorOpen: boolean
  streaming: boolean
  theme: ThemeMode
  user: AuthUser
  onModelChange: (value: string | null) => void
  onAgentModeChange: (value: AgentMode) => void
  onCompareModelToggle: (modelId: string) => void
  onToggleInspector: () => void
  onToggleTheme: () => void
  onLogout: () => void
  onOpenSidebar: () => void
}

export function TopBar({ conversation, models, selectedModelId, selectedAgentMode, selectedCompareModelIds, inspectorOpen, streaming, theme, user, onModelChange, onAgentModeChange, onCompareModelToggle, onToggleInspector, onToggleTheme, onLogout, onOpenSidebar }: Props) {
  const [mobileControlsOpen, setMobileControlsOpen] = useState(false)
  const selectedModel = models.find((item) => item.id === selectedModelId) || null
  const selectedAgent = AGENT_OPTIONS.find((item) => item.value === selectedAgentMode)

  useEffect(() => setMobileControlsOpen(false), [conversation?.id])

  return (
    <header className={`topbar ${mobileControlsOpen ? 'topbar--mobile-expanded' : ''}`}>
      <div className="topbar__mobile-header">
        <button className="icon-action" type="button" onClick={onOpenSidebar} aria-label="打开会话列表">
          <Menu size={19} />
        </button>
        <div className="topbar__mobile-title">
          <strong>{displayConversationTitle(conversation?.title)}</strong>
          <span>{selectedAgent?.label || '智能体'} · {selectedModel?.displayName || '选择模型'}</span>
        </div>
        <button
          className="icon-action topbar__settings-toggle"
          type="button"
          onClick={() => setMobileControlsOpen((value) => !value)}
          aria-expanded={mobileControlsOpen}
          aria-label={mobileControlsOpen ? '收起会话设置' : '展开会话设置'}
        >
          <SlidersHorizontal size={18} />
          <ChevronDown size={14} />
        </button>
      </div>

      <div className="topbar__main">
        <div className="topbar__eyebrow">当前会话</div>
        <h1>{displayConversationTitle(conversation?.title)}</h1>
        <div className="topbar__meta">
          <span><Activity size={13} /> {streaming ? 'Agent 正在运行' : '等待输入'}</span>
          <span><Wrench size={13} /> {selectedModel ? (selectedModel.supportTools ? '工具已启用' : '标准对话') : '正在加载模型'}</span>
        </div>
      </div>

      <div className={`topbar__controls ${mobileControlsOpen ? 'topbar__controls--open' : ''}`}>
        <label className="select-card">
          <span>模型</span>
          <select value={selectedModelId || ''} onChange={(event) => onModelChange(event.target.value || null)}>
            {models.length === 0 ? <option value="">暂无模型</option> : null}
            {models.map((item) => (
              <option key={item.id} value={item.id}>{item.displayName}</option>
            ))}
          </select>
        </label>

        <label className="select-card select-card--agent">
          <span>Agent 模式</span>
          <select value={selectedAgentMode} onChange={(event) => onAgentModeChange(event.target.value as AgentMode)}>
            {AGENT_OPTIONS.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </label>

        <ThemeToggle theme={theme} onToggle={onToggleTheme} />

        <div className="user-menu" title={`当前账号：${user.username}`}>
          <UserRound size={16} />
          <span>{user.username}</span>
          <button type="button" onClick={onLogout} title="退出登录"><LogOut size={16} /></button>
        </div>

        <button className="icon-action inspector-action" type="button" onClick={onToggleInspector} title="切换执行面板">
          {inspectorOpen ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>

      {selectedAgentMode === 'compare' ? (
        <div className={`compare-model-picker ${mobileControlsOpen ? 'compare-model-picker--open' : ''}`}>
          <span>并发模型（选择 2-3 个）</span>
          <div>
            {models.filter((item) => item.enabled && item.apiShape === 'chat_completions').map((item) => {
              const checked = selectedCompareModelIds.includes(item.id)
              const disabled = !checked && selectedCompareModelIds.length >= 3
              return (
                <label key={item.id} className={checked ? 'model-check model-check--selected' : 'model-check'}>
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={disabled}
                    onChange={() => onCompareModelToggle(item.id)}
                  />
                  {item.displayName}
                </label>
              )
            })}
          </div>
        </div>
      ) : null}
    </header>
  )
}
