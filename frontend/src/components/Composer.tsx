import { CornerDownLeft, Square, Zap } from 'lucide-react'
import { useEffect, useRef } from 'react'

type Props = {
  value: string
  disabled: boolean
  streaming: boolean
  onChange: (value: string) => void
  onSend: () => void
  onStop: () => void
}

export function Composer({ value, disabled, streaming, onChange, onSend, onStop }: Props) {
  const ref = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`
  }, [value])

  return (
    <footer className="composer-wrap">
      <div className="composer-hint"><Zap size={14} /> Enter 发送，Shift + Enter 换行。Auto 可自动分流，Compare 可并发评测 2-3 个模型。</div>
      <div className="composer">
        <textarea
          ref={ref}
          value={value}
          disabled={disabled}
          placeholder="输入你的问题，例如：古文有哪些经典佛语"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              onSend()
            }
          }}
        />
        <button className={streaming ? 'send-btn send-btn--stop' : 'send-btn'} type="button" onClick={streaming ? onStop : onSend} disabled={disabled || (!streaming && !value.trim())}>
          {streaming ? <Square size={18} /> : <CornerDownLeft size={19} />}
        </button>
      </div>
    </footer>
  )
}
