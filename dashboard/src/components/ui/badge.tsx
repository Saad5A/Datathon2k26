import type { HTMLAttributes } from 'react'
import { priorityColor, priorityLabel, priorityText, type Priority } from '@/theme/tokens'
import { cn } from '@/lib/utils'

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded border border-line-strong px-1.5 py-0.5 font-mono text-[11px] font-medium leading-none text-fg-muted',
        className,
      )}
      {...props}
    />
  )
}

/** Solid severity chip: colour plus text, never colour alone. */
export function PriorityBadge({ priority, showLabel = false }: { priority: Priority; showLabel?: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 font-mono text-[11px] font-semibold leading-none"
      style={{ backgroundColor: priorityColor[priority], color: priorityText[priority] }}
      title={priorityLabel[priority]}
    >
      {priority}
      {showLabel && <span className="font-sans font-medium">{priorityLabel[priority]}</span>}
    </span>
  )
}
