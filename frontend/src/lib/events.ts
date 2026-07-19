import type {
  PersistedRunEvent,
  RunEvent,
} from '../types'


export const STREAM_EVENTS = [
  'run.started',
  'route.started',
  'route.decision',
  'agent.updated',
  'run.snapshot',
  'token.delta',
  'token.chunk',
  'run.item',
  'tool.called',
  'tool.output',
  'message.completed',
  'compare.model.started',
  'compare.model.completed',
  'compare.model.failed',
  'judge.started',
  'judge.completed',
  'run.completed',
  'run.failed',
  'run.cancel.requested',
  'run.cancelled',
  'run.timeout',
  'run.interrupted',
  'run.error',
  'connection.error',
  'client.stop',
]

export function persistedToRunEvent(
  item: PersistedRunEvent,
): RunEvent {
  const data =
    typeof item.payload_json === 'string'
      ? parseEventData(item.payload_json)
      : item.payload_json || {}

  return {
    id: item.id,
    event:
      item.event_type ||
      item.event_name ||
      'run.item',
    data,
    createdAt: new Date(item.created_at).getTime(),
  }
}

export function parseEventData(raw: string): Record<string, unknown> {
  if (!raw) return {}
  try {
    const parsed = JSON.parse(raw) as unknown
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>
    }
    return { value: parsed }
  } catch {
    return { value: raw }
  }
}

export function createRunEvent(event: string, rawData: string, eventId?: string): RunEvent {
  return {
    id: eventId ? `${event}-${eventId}` : `${event}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    event,
    data: parseEventData(rawData),
    createdAt: Date.now(),
  }
}

export function readString(data: Record<string, unknown>, key: string): string | undefined {
  const value = data[key]
  return typeof value === 'string' ? value : undefined
}

export function readNumber(data: Record<string, unknown>, key: string): number | undefined {
  const value = data[key]
  return typeof value === 'number' ? value : undefined
}
