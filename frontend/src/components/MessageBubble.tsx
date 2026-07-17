import { Bot, Hammer, UserRound } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import clsx from 'clsx'
import type { Message } from '../types'
import { formatDateTime } from '../utils/format'

type Props = {
  message: Message
  streaming?: boolean
}

function roleLabel(role: string): string {
  if (role === 'user') return '你'
  if (role === 'tool') return '工具'
  if (role === 'system') return '系统'
  return '助手'
}

function RoleIcon({ role }: { role: string }) {
  if (role === 'user') return <UserRound size={18} />
  if (role === 'tool') return <Hammer size={18} />
  return <Bot size={18} />
}

export function MessageBubble({ message, streaming }: Props) {
  return (
    <article className={clsx('message-row', message.role === 'user' && 'message-row--user')}>
      <div className={clsx('message-avatar', `message-avatar--${message.role}`)}><RoleIcon role={message.role} /></div>
      <div className={clsx('message-card', message.role === 'user' && 'message-card--user')}>
        <div className="message-card__meta">
          <strong>{roleLabel(message.role)}</strong>
          {message.model ? <span>{message.model}</span> : null}
          {message.agent_name ? <span>{message.agent_name}</span> : null}
          <span>{formatDateTime(message.created_at)}</span>
          {streaming ? <em>正在思考</em> : null}
        </div>
        <div className="markdown-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || ' '}</ReactMarkdown>
        </div>
      </div>
    </article>
  )
}
