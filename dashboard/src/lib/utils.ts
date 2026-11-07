import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const intFmt = new Intl.NumberFormat('en-US')
export const fmtInt = (n: number) => intFmt.format(n)

export const fmtCompact = (n: number) =>
  new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(n)

export const fmtPct = (n: number, digits = 1) => `${n.toFixed(digits)}%`

export const fmtScore = (n: number) => n.toFixed(3)

const monthFmt = new Intl.DateTimeFormat('en-US', { month: 'short', timeZone: 'UTC' })
export const fmtMonth = (ym: string) => {
  const [y, m] = ym.split('-').map(Number)
  if (!y || !m) return ym
  return monthFmt.format(new Date(Date.UTC(y, m - 1, 1)))
}

/** Deterministic PRNG so the sample dataset is identical on every load. */
export function mulberry32(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export const humanizeSignal = (s: string) =>
  s
    .replace(/_/g, ' ')
    .replace(/\bkev\b/gi, 'KEV')
    .replace(/\bepss\b/gi, 'EPSS')
    .replace(/\bcvss\b/gi, 'CVSS')
    .replace(/\bcwe\b/gi, 'CWE')
    .replace(/\bpoc\b/gi, 'PoC')
    .replace(/\brce\b/gi, 'RCE')
    .replace(/^./, (c) => c.toUpperCase())
