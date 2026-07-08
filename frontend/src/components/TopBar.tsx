import { Activity, Bot, Braces, Eye, EyeOff, Image, Layers3, Route, ShoppingBag, Wrench } from 'lucide-react'
import type { ReactNode } from 'react'
import type { AgentMode, Conversation, NormalizedModel, ThemeMode } from '../types'
import { ThemeToggle } from './ThemeToggle'

const AGENT_OPTIONS: Array<{ value: AgentMode; label: string; icon: ReactNode; note: string }> = [
  { value: 'auto', label: '智能路由', icon: <Route size={15} />, note: 'Triage Agent' },
  { value: 'general', label: '通用助手', icon: <Bot size={15} />, note: 'General' },
  { value: 'tech', label: '技术助手', icon: <Braces size={15} />, note: 'Day23' },
  { value: 'ecommerce', label: '电商运营', icon: <ShoppingBag size={15} />, note: 'Day24' },
  { value: 'image', label: '图片生成', icon: <Image size={15} />, note: 'Day31' },
  { value: 'compare', label: '模型对比', icon: <Layers3 size={15} />, note: 'Day28' },
]

type Props = {
  conversation: Conversation | null
  models: NormalizedModel[]
  selectedModelId: string | null
  selectedAgentMode: AgentMode
  inspectorOpen: boolean
  streaming: boolean
  theme: ThemeMode
  onModelChange: (value: string | null) => void
  onAgentModeChange: (value: AgentMode) => void
  onToggleInspector: () => void
  onToggleTheme: () => void
}

export function TopBar({ conversation, models, selectedModelId, selectedAgentMode, inspectorOpen, streaming, theme, onModelChange, onAgentModeChange, onToggleInspector, onToggleTheme }: Props) {
  const selectedModel = models.find((item) => item.id === selectedModelId) || null

  return (
    <header className="topbar">
      <div className="topbar__main">
        <div className="topbar__eyebrow">当前会话</div>
        <h1>{conversation?.title || '新会话'}</h1>
        <div className="topbar__meta">
          <span><Activity size={13} /> {streaming ? 'Agent 正在运行' : '等待输入'}</span>
          <span><Wrench size={13} /> {selectedModel?.supportTools ? '支持工具调用' : '工具能力待验证'}</span>
        </div>
      </div>

      <div className="topbar__controls">
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
              <option key={item.value} value={item.value}>{item.label} · {item.note}</option>
            ))}
          </select>
        </label>

        <ThemeToggle theme={theme} onToggle={onToggleTheme} />

        <button className="icon-action" type="button" onClick={onToggleInspector} title="切换执行面板">
          {inspectorOpen ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
    </header>
  )
}
