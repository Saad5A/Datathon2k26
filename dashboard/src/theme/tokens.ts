/**
 * Design tokens — the single source of truth for colour, spacing and layout.
 *
 * Consumed by:
 *  - tailwind.config.ts (utility classes: `bg-sev-p0`, `text-fg-muted`, …)
 *  - src/index.css      (surface/text CSS variables per theme)
 *  - chart components   (Recharts needs raw hex values, not classes)
 */

export type Priority = 'P0' | 'P1' | 'P2'
export type ThemeMode = 'dark' | 'light'

/** Severity scale. Reserved for risk meaning only — never decoration. */
export const severity = {
  critical: '#B45B49',
  high: '#B67C38',
  medium: '#C4A64D',
  low: '#3C998E',
  neutral: '#718C79',
} as const

export const priorityColor: Record<Priority, string> = {
  P0: severity.critical,
  P1: severity.high,
  P2: severity.medium,
}

/** Priority badges use dark ink on warm fills; labels retain risk meaning. */
export const priorityText: Record<Priority, string> = {
  P0: '#FFFFFF',
  P1: '#14251E',
  P2: '#233934',
}

export const priorityLabel: Record<Priority, string> = {
  P0: 'Critical',
  P1: 'High',
  P2: 'Medium',
}

/** Kitchen palette shared by CSS surfaces and chart tooltips. */
const kitchenSurfaces = {
  bg: '#F7F8F1', surface: '#FFFFFA', surfaceRaised: '#EEF2E9',
  border: '#DAE2D8', borderStrong: '#B5C7BC',
  fg: '#233934', fgMuted: '#546C63', fgSubtle: '#5E746A', grid: '#DAE2D8',
}
export const surfaces: Record<ThemeMode, typeof kitchenSurfaces> = {
  light: kitchenSurfaces,
  dark: kitchenSurfaces,
}
export const dataNeutral: Record<ThemeMode, string> = {
  dark: '#597D76', light: '#597D76',
}

/** 4px spacing scale — maps 1:1 onto Tailwind's default `p-1` … `p-12`. */
export const space = {
  1: '4px',
  2: '8px',
  3: '12px',
  4: '16px',
  5: '20px',
  6: '24px',
  8: '32px',
  10: '40px',
  12: '48px',
} as const

/** 12-column layout engine. */
export const layout = {
  columns: 12,
  gutter: space[4],
  maxWidth: '1600px',
} as const

export const fonts = {
  sans: ['"IBM Plex Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
  mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
}
