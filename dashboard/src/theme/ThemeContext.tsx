import { createContext, useContext, type ReactNode } from 'react'
import { useTheme } from './useTheme'

type Ctx = ReturnType<typeof useTheme>
const ThemeCtx = createContext<Ctx | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const value = useTheme()
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useThemeContext() {
  const v = useContext(ThemeCtx)
  if (!v) throw new Error('useThemeContext must be used inside <ThemeProvider>')
  return v
}
