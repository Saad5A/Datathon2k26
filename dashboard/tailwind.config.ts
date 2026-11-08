import type { Config } from 'tailwindcss'
import { fonts, severity } from './src/theme/tokens'

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: { sans: fonts.sans, mono: fonts.mono },
      colors: {
        sev: {
          p0: severity.critical,
          p1: severity.high,
          p2: severity.medium,
          low: severity.low,
          neutral: severity.neutral,
        },
        sevfg: {
          p0: 'rgb(var(--sevfg-p0) / <alpha-value>)',
          p1: 'rgb(var(--sevfg-p1) / <alpha-value>)',
          p2: 'rgb(var(--sevfg-p2) / <alpha-value>)',
          low: 'rgb(var(--sevfg-low) / <alpha-value>)',
        },
        // Surfaces resolve through CSS variables so one class works in both themes.
        bg: 'rgb(var(--bg) / <alpha-value>)',
        surface: 'rgb(var(--surface) / <alpha-value>)',
        raised: 'rgb(var(--surface-raised) / <alpha-value>)',
        line: 'rgb(var(--border) / <alpha-value>)',
        'line-strong': 'rgb(var(--border-strong) / <alpha-value>)',
        fg: {
          DEFAULT: 'rgb(var(--fg) / <alpha-value>)',
          muted: 'rgb(var(--fg-muted) / <alpha-value>)',
          subtle: 'rgb(var(--fg-subtle) / <alpha-value>)',
        },
      },
      keyframes: {
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'pop-in': {
          from: { opacity: '0', transform: 'translate(-50%, -48%) scale(0.98)' },
          to: { opacity: '1', transform: 'translate(-50%, -50%) scale(1)' },
        },
        'row-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 150ms ease-out',
        'pop-in': 'pop-in 180ms cubic-bezier(0.16, 1, 0.3, 1)',
        'row-in': 'row-in 220ms cubic-bezier(0.16, 1, 0.3, 1) both',
      },
    },
  },
  plugins: [],
} satisfies Config
