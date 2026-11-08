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
  critical: '#DC2626', // red-600    → P0
  high: '#EA580C', //     orange-600 → P1
  medium: '#D97706', //   amber-600  → P2
  low: '#2563EB', //      blue-600   → informational / low
  neutral: '#64748B', //  slate-500  → no signal
} as const

export const priorityColor: Record<Priority, string> = {
  P0: severity.critical,
  P1: severity.high,
  P2: severity.medium,
}

/** Text on a solid priority fill. White fails AA on orange/amber, so those use near-black. */
export const priorityText: Record<Priority, string> = {
  P0: '#FFFFFF', // 4.83:1
  P1: '#09090B', // 5.59:1
  P2: '#09090B', // 6.24:1
}

export const priorityLabel: Record<Priority, string> = {
  P0: 'Critical',
  P1: 'High',
  P2: 'Medium',
}

/** Surfaces & text. Dark is the default; light is opt-in via the toggle. */
export const surfaces: Record<ThemeMode, {
  bg: string
  surface: string
  surfaceRaised: string
  border: string
  borderStrong: string
  fg: string
  fgMuted: string
  fgSubtle: string
  grid: string
}> = {
  dark: {
    bg: '#09090B', //            zinc-950
    surface: '#18181B', //       zinc-900
    surfaceRaised: '#27272A', // zinc-800
    border: '#27272A', //        zinc-800
    borderStrong: '#3F3F46', //  zinc-700
    fg: '#F1F5F9', //            slate-100
    fgMuted: '#94A3B8', //       slate-400
    fgSubtle: '#8B9AB0', //      4.5:1+ on surface, bg and raised
    grid: '#27272A',
  },
  light: {
    bg: '#F4F4F5', //            zinc-100
    surface: '#FFFFFF',
    surfaceRaised: '#F4F4F5',
    border: '#E4E4E7', //        zinc-200
    borderStrong: '#D4D4D8', //  zinc-300
    fg: '#0F172A', //            slate-900
    fgMuted: '#475569', //       slate-600
    fgSubtle: '#566275', //      4.5:1+ on white and zinc-100
    grid: '#E4E4E7',
  },
}

/** Non-severity data colour (volumes, neutral series). */
export const dataNeutral: Record<ThemeMode, string> = {
  dark: '#94A3B8',
  light: '#64748B',
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
