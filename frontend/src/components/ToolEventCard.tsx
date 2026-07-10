import {
  CheckCircle2,
  PlayCircle,
  Terminal,
} from 'lucide-react'

import type { RunEvent } from '../types'
import { safeJson } from '../utils/format'

type Props = {
  event: RunEvent
}

function readText(
  data: Record<string, unknown>,
  key: string,
): string {
  const value = data[key]

  if (typeof value === 'string') {
    return value
  }

  if (value === undefined || value === null) {
    return '--'
  }

  return safeJson(value)
}

export function ToolEventCard({ event }: Props) {
  const isCalled = event.event === 'tool.called'

  const toolName = readText(
    event.data,
    'tool_name',
  )

  return (
    <div className="tool-event-card">
      <div className="tool-event-card__header">
        <span className="tool-event-card__icon">
          {isCalled
            ? <PlayCircle size={17} />
            : <CheckCircle2 size={17} />
          }
        </span>

        <div>
          <strong>
            {isCalled ? '调用工具' : '工具返回'}
          </strong>

          <span>{toolName}</span>
        </div>

        <Terminal size={16} />
      </div>

      <div className="tool-event-card__body">
        <span>
          {isCalled ? '调用参数' : '返回结果'}
        </span>

        <pre>
          {isCalled
            ? readText(event.data, 'arguments')
            : readText(event.data, 'output')
          }
        </pre>
      </div>
    </div>
  )
}