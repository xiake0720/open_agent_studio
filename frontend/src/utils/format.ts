export function formatDateTime(value?: string | null): string {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDuration(ms?: number | null): string {
  if (ms === null || ms === undefined) return '--'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

export function truncate(text: string, max = 42): string {
  if (text.length <= max) return text
  return `${text.slice(0, max)}…`
}

export function displayConversationTitle(title?: string | null): string {
  const value = title?.trim() || ''
  if (!value || (/day\s*\d+/i.test(value) && /测试/.test(value))) return '新会话'
  return value
}

export function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}
