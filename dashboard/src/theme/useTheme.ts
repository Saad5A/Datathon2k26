import { useCallback, useEffect, useState } from 'react'
import { dataNeutral, surfaces, type ThemeMode } from './tokens'

const KEY = 'btb-theme'

function initial(): ThemeMode {
  if (typeof document === 'undefined') return 'dark'
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

/** Dark-first theme state; also exposes resolved hex values for Recharts. */
export function useTheme() {
  const [mode, setMode] = useState<ThemeMode>(initial)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', mode === 'dark')
    try {
      localStorage.setItem(KEY, mode)
    } catch {
      /* storage unavailable: theme still works for this session */
    }
  }, [mode])

  const toggle = useCallback(() => setMode((m) => (m === 'dark' ? 'light' : 'dark')), [])
  return { mode, toggle, palette: { ...surfaces[mode], neutral: dataNeutral[mode] } }
}
