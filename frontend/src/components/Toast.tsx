import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'
import type { Toast as ToastType } from '../types'

type Props = {
  toast: ToastType | null
}

export function Toast({ toast }: Props) {
  if (!toast) return null
  const Icon = toast.type === 'success' ? CheckCircle2 : toast.type === 'error' ? XCircle : toast.type === 'warning' ? AlertTriangle : Info
  return (
    <div className={`toast toast--${toast.type}`}>
      <Icon size={18} />
      <div>
        <strong>{toast.title}</strong>
        {toast.description ? <span>{toast.description}</span> : null}
      </div>
    </div>
  )
}
