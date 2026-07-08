import type { RunEvent } from '../types'

export const STREAM_EVENTS = [
  'run.started',
  'agent.updated',
  'token.delta',
  'run.item',
  'tool.called',
  'tool.output',
  'message.completed',
  'run.completed',
  'run.error',
  'connection.error',
  'client.stop',
]

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

export function createRunEvent(event: string, rawData: string): RunEvent {
  return {
    id: `${event}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
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
