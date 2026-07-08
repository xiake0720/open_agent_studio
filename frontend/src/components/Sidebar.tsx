import { MessageSquarePlus, Search, Trash2, Sparkles, Wifi, WifiOff } from 'lucide-react'
import clsx from 'clsx'
import type { Conversation } from '../types'
import { formatDateTime, truncate } from '../utils/format'

type Props = {
  conversations: Conversation[]
  activeConversationId: string | null
  query: string
  connected: boolean
  loading: boolean
  onQueryChange: (value: string) => void
  onCreate: () => void
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}

export function Sidebar({ conversations, activeConversationId, query, connected, loading, onQueryChange, onCreate, onSelect, onDelete }: Props) {
  const filtered = conversations.filter((item) => item.title.toLowerCase().includes(query.toLowerCase()))

  return (
    <aside className="sidebar">
      <div className="brand-card">
        <div className="brand-card__mark"><Sparkles size={22} /></div>
        <div>
          <div className="brand-card__title">OpenAgent Studio</div>
          <div className="brand-card__sub">多模型智能体工作台</div>
        </div>
      </div>

      <button className="new-chat-btn" type="button" onClick={onCreate} disabled={loading}>
        <MessageSquarePlus size={18} /> 新建会话
      </button>

      <label className="search-box">
        <Search size={16} />
        <input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="搜索会话" />
      </label>

      <div className="conversation-list" aria-label="会话列表">
        {filtered.length === 0 ? (
          <div className="empty-list">暂无会话。点击上方按钮创建一个新会话。</div>
        ) : filtered.map((item) => (
          <button
            key={item.id}
            className={clsx('conversation-item', item.id === activeConversationId && 'conversation-item--active')}
            type="button"
            onClick={() => onSelect(item.id)}
          >
            <span className="conversation-item__main">
              <span className="conversation-item__title">{truncate(item.title || '新会话', 26)}</span>
              <span className="conversation-item__meta">{formatDateTime(item.updated_at)} · {item.agent_mode || 'general'}</span>
            </span>
            <span
              role="button"
              tabIndex={0}
              className="conversation-item__delete"
              title="删除会话"
              onClick={(event) => { event.stopPropagation(); onDelete(item.id) }}
              onKeyDown={(event) => { if (event.key === 'Enter') { event.stopPropagation(); onDelete(item.id) } }}
            >
              <Trash2 size={15} />
            </span>
          </button>
        ))}
      </div>

      <div className={clsx('backend-state', connected ? 'backend-state--ok' : 'backend-state--bad')}>
        {connected ? <Wifi size={16} /> : <WifiOff size={16} />}
        <span>{connected ? '后端连接正常' : '后端未连接'}</span>
      </div>
    </aside>
  )
}
