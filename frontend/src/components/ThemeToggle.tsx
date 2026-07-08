import { Moon, Sun } from 'lucide-react'
import type { ThemeMode } from '../types'

type Props = {
  theme: ThemeMode
  onToggle: () => void
}

export function ThemeToggle({ theme, onToggle }: Props) {
  const isLight = theme === 'light'
  return (
    <button className="theme-toggle" type="button" onClick={onToggle} aria-label="切换明暗主题">
      <span className={`theme-toggle__thumb ${isLight ? 'theme-toggle__thumb--light' : ''}`}>
        {isLight ? <Sun size={17} /> : <Moon size={17} />}
      </span>
      <span className="theme-toggle__label">{isLight ? '白天' : '夜间'}</span>
    </button>
  )
}
