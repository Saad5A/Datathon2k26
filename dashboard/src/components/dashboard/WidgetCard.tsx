import { Info, MoreHorizontal } from 'lucide-react'
import type { ReactNode } from 'react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Tooltip } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

export interface WidgetCardProps {
  title: string
  /** Short context line under the title (scope, unit, time window). */
  subtitle?: ReactNode
  /** Explains the metric/method; rendered behind an info icon. */
  info?: ReactNode
  /** Dropdown content (DropdownMenuItem / RadioGroup …). Renders the ⋯ trigger. */
  menu?: ReactNode
  /** Inline controls rendered at the right of the header. */
  actions?: ReactNode
  className?: string
  bodyClassName?: string
  children: ReactNode
}

export function WidgetCard({ title, subtitle, info, menu, actions, className, bodyClassName, children }: WidgetCardProps) {
  return (
    <section className={cn('flex h-full flex-col rounded-lg border border-line bg-surface', className)}>
      <header className="flex items-start gap-2 px-4 pb-2 pt-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <h2 className="truncate text-[11px] font-semibold uppercase tracking-wider text-fg-muted">{title}</h2>
            {info && (
              <Tooltip content={info}>
                <button
                  type="button"
                  className="rounded text-fg-subtle hover:text-fg"
                  aria-label={`About ${title}`}
                >
                  <Info className="size-3.5" />
                </button>
              </Tooltip>
            )}
          </div>
          {subtitle && <p className="mt-0.5 text-xs text-fg-subtle">{subtitle}</p>}
        </div>
        {actions}
        {menu && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="-mr-1 -mt-1 rounded p-1 text-fg-subtle hover:bg-raised hover:text-fg"
                aria-label={`${title} options`}
              >
                <MoreHorizontal className="size-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>{menu}</DropdownMenuContent>
          </DropdownMenu>
        )}
      </header>
      <div className={cn('flex-1 px-4 pb-4', bodyClassName)}>{children}</div>
    </section>
  )
}
