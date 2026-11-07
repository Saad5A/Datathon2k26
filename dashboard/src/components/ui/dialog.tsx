import * as D from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ComponentPropsWithoutRef, ReactNode } from 'react'
import { cn } from '@/lib/utils'

export const Dialog = D.Root
export const DialogTrigger = D.Trigger
export const DialogClose = D.Close

export function DialogContent({
  className,
  children,
  ...props
}: ComponentPropsWithoutRef<typeof D.Content> & { children: ReactNode }) {
  return (
    <D.Portal>
      <D.Overlay className="fixed inset-0 z-40 animate-fade-in bg-black/70 backdrop-blur-[2px]" />
      <D.Content
        className={cn(
          'fixed left-1/2 top-1/2 z-50 flex max-h-[calc(100dvh-32px)] w-[calc(100vw-32px)] max-w-3xl -translate-x-1/2 -translate-y-1/2 animate-pop-in flex-col overflow-hidden rounded-lg border border-line-strong bg-surface text-fg shadow-2xl',
          className,
        )}
        {...props}
      >
        {children}
        <D.Close
          className="absolute right-3 top-3 rounded p-1 text-fg-muted hover:bg-raised hover:text-fg"
          aria-label="Close"
        >
          <X className="size-4" />
        </D.Close>
      </D.Content>
    </D.Portal>
  )
}

export const DialogTitle = ({ className, ...p }: ComponentPropsWithoutRef<typeof D.Title>) => (
  <D.Title className={cn('text-base font-semibold', className)} {...p} />
)
export const DialogDescription = ({ className, ...p }: ComponentPropsWithoutRef<typeof D.Description>) => (
  <D.Description className={cn('text-sm text-fg-muted', className)} {...p} />
)
