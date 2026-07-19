import { Activity, Bot, CheckCircle2, Clock, Copy, Database, ListTree, Terminal, Trash2, XCircle } from 'lucide-react'
import clsx from 'clsx'
import type { AgentRunStatus, RunEvent, ToolCall } from '../types'
import { formatDuration, safeJson } from '../utils/format'
import { ToolEventCard } from './ToolEventCard'

type Props = {
  events: RunEvent[]
  activeRunId: string | null
  streaming: boolean
  tokenCount: number
  model?: string | null
  agentName?: string | null
  runStatus?: AgentRunStatus | null
  cancelledAt?: string | null
  persistedToolCalls: ToolCall[]
  onClear: () => void
}

function eventTone(event: string): string {
  if (event.includes('error')) return 'danger'
  if (event.includes('completed')) return 'success'
  if (event.includes('tool')) return 'warning'
  if (event.includes('token')) return 'muted'
  return 'info'
}

function EventIcon({ event }: { event: string }) {
  if (event.includes('error')) return <XCircle size={16} />
  if (event.includes('completed')) return <CheckCircle2 size={16} />
  if (event.includes('tool')) return <Terminal size={16} />
  if (event.includes('token')) return <Activity size={16} />
  return <ListTree size={16} />
}

export function Inspector({ events, activeRunId, streaming, tokenCount, model, agentName, runStatus, cancelledAt, persistedToolCalls, onClear }: Props) {
  const started = events.find((item) => item.event === 'run.started')
  const terminal = [...events].reverse().find((item) => [
    'run.completed', 'run.failed', 'run.cancelled', 'run.timeout', 'run.interrupted',
  ].includes(item.event))
  const duration = typeof terminal?.data.duration_ms === 'number' ? terminal.data.duration_ms : undefined
  const visibleEvents = events.filter((item) => item.event !== 'token.delta',)
  return (
    <aside className="inspector">
      <div className="inspector__header">
        <div>
          <div className="eyebrow">Agent Trace</div>
          <h2>执行过程</h2>
        </div>
        <button className="icon-action" type="button" onClick={onClear} title="清空事件"><Trash2 size={17} /></button>
      </div>

      <div className="trace-grid">
        <div className="trace-card"><Database size={17} /><span>Run ID</span><strong>{activeRunId || '--'}</strong></div>
        <div className="trace-card"><Bot size={17} /><span>Agent</span><strong>{agentName || '--'}</strong></div>
        <div className="trace-card"><Activity size={17} /><span>流式片段</span><strong>{tokenCount}</strong></div>
        <div className="trace-card"><Clock size={17} /><span>耗时</span><strong>{formatDuration(duration)}</strong></div>
      </div>

      <div className={clsx('runtime-banner', streaming && 'runtime-banner--live')}>
        <span />
        {streaming ? 'SSE 连接中，正在接收 token.delta' : started ? '本次运行已结束或空闲' : '等待一次新的 AgentRun'}
      </div>

      <div className="trace-meta">
        <span>模型：{model || '--'}</span>
        <span>最终状态：{runStatus || '--'}</span>
        {cancelledAt ? <span>取消时间：{new Date(cancelledAt).toLocaleString()}</span> : null}
        <span>已持久化工具调用：{persistedToolCalls.length}</span>
      </div>

      <div className="event-list">
          {visibleEvents.length === 0 ? (
            <div className="empty-events">
              还没有执行事件。发送消息后，这里会展示
              run.started、agent.updated、tool.called、
              tool.output、message.completed、run.completed
              等执行过程。
            </div>
          ) : (
            visibleEvents.map((item, index) => {
              // 工具调用和工具返回使用专用卡片
              if (
                item.event === 'tool.called' ||
                item.event === 'tool.output'
              ) {
                return (
                  <ToolEventCard
                    key={item.id}
                    event={item}
                  />
                )
              }

              // 其他事件继续使用通用事件卡片
              return (
                <details
                  key={item.id}
                  className={clsx(
                    'event-card',
                    `event-card--${eventTone(item.event)}`,
                  )}
                  open={
                    index >= visibleEvents.length - 3 ||
                    item.event.includes('error')
                  }
                >
                  <summary>
                    <span className="event-card__icon">
                      <EventIcon event={item.event} />
                    </span>

                    <span className="event-card__name">
                      {item.event}
                    </span>

                    <span className="event-card__time">
                      {new Date(
                        item.createdAt,
                      ).toLocaleTimeString()}
                    </span>

                    <button
                      type="button"
                      className="copy-btn"
                      onClick={(event) => {
                        event.preventDefault()

                        void navigator.clipboard.writeText(
                          safeJson(item.data),
                        )
                      }}
                      title="复制 JSON"
                    >
                      <Copy size={13} />
                    </button>
                  </summary>

                  <pre>{safeJson(item.data)}</pre>
                </details>
              )
            })
          )}
        </div>
    </aside>
  )
}
