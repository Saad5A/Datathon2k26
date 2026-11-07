import * as DM from '@radix-ui/react-dropdown-menu'
import { Check } from 'lucide-react'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '@/lib/utils'

export const DropdownMenu = DM.Root
export const DropdownMenuTrigger = DM.Trigger

export function DropdownMenuContent({ className, ...props }: ComponentPropsWithoutRef<typeof DM.Content>) {
  return (
    <DM.Portal>
      <DM.Content
        sideOffset={6}
        align="end"
        className={cn(
          'z-50 min-w-44 animate-fade-in rounded-md border border-line-strong bg-surface p-1 text-sm text-fg shadow-xl',
          className,
        )}
        {...props}
      />
    </DM.Portal>
  )
}

export function DropdownMenuLabel({ className, ...props }: ComponentPropsWithoutRef<typeof DM.Label>) {
  return (
    <DM.Label
      className={cn('px-2 py-1.5 text-[11px] font-medium uppercase tracking-wider text-fg-subtle', className)}
      {...props}
    />
  )
}

export function DropdownMenuItem({ className, ...props }: ComponentPropsWithoutRef<typeof DM.Item>) {
  return (
    <DM.Item
      className={cn(
        'flex cursor-default select-none items-center gap-2 rounded px-2 py-1.5 outline-none data-[highlighted]:bg-raised [&_svg]:size-4',
        className,
      )}
      {...props}
    />
  )
}

export const DropdownMenuRadioGroup = DM.RadioGroup

export function DropdownMenuRadioItem({ className, children, ...props }: ComponentPropsWithoutRef<typeof DM.RadioItem>) {
  return (
    <DM.RadioItem
      className={cn(
        'relative flex cursor-default select-none items-center rounded py-1.5 pl-7 pr-2 outline-none data-[highlighted]:bg-raised',
        className,
      )}
      {...props}
    >
      <DM.ItemIndicator className="absolute left-2 inline-flex">
        <Check className="size-3.5" />
      </DM.ItemIndicator>
      {children}
    </DM.RadioItem>
  )
}

export function DropdownMenuSeparator() {
  return <DM.Separator className="my-1 h-px bg-line" />
}
