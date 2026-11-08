import { useCallback, useEffect, useState } from 'react'
import { dataNeutral, surfaces, type ThemeMode } from './tokens'

const KEY = 'btb-theme'

/** The kitchen uses a light palette, including sessions with an old dark preference. */
export function useTheme() {
  const [mode, setMode] = useState<ThemeMode>('light')

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
